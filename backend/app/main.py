import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select, text

from app.config import get_settings
from app.db import engine
from app.routers import admin, alertas, auth, geocercas, push, reportes, tareas
from app.services import cola

log = logging.getLogger("vigilant")


def _revisar_rol_bd() -> None:
    """Si el rol de la base se salta RLS, el aislamiento entre empresas no aplica."""
    try:
        with engine.connect() as c:
            peligroso = c.scalar(
                text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
            )
    except Exception as e:  # la API arranca aunque la base tarde en despertar
        log.warning("No se pudo revisar el rol de la base de datos: %s", e)
        return
    if peligroso:
        log.critical(
            "El rol de la base de datos es superusuario o tiene BYPASSRLS: "
            "Row-Level Security NO aísla a las empresas. Usa un rol propio (ver docs)."
        )


def _crear_superadmin_inicial() -> None:
    s = get_settings()
    if not (s.superadmin_email and s.superadmin_password):
        return
    from app.cli import crear_superadmin
    from app.db import sesion
    from app.models import Usuario

    try:
        with sesion(bypass_rls=True) as db:
            existe = db.scalar(select(Usuario.id).where(Usuario.rol == "SUPER_ADMIN").limit(1))
        if existe is None:
            crear_superadmin(s.superadmin_email, s.superadmin_password)
    except Exception as e:
        log.warning("No se pudo crear el super admin inicial: %s", e)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _revisar_rol_bd()
    _crear_superadmin_inicial()
    await cola.iniciar()
    yield
    await cola.cerrar()


app = FastAPI(
    title="VIGILANT API",
    version="0.1.0",
    description="SaaS multi-tenant de patrullaje vehicular con geocercas y alertas.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origenes,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

for r in (auth, admin, geocercas, reportes, alertas, push, tareas):
    app.include_router(r.router)


@app.get("/salud", tags=["sistema"])
def salud() -> dict:
    return {"ok": True}


# ---------- Panel web en el mismo servicio (opcional) ----------

_web = Path(get_settings().web_dir).resolve() if get_settings().web_dir else None

if _web and (_web / "index.html").is_file():

    @app.get("/{ruta:path}", include_in_schema=False)
    def panel(ruta: str) -> FileResponse:
        if ruta.startswith("v1/"):
            raise HTTPException(404, "No encontrado")
        archivo = (_web / ruta).resolve()
        if ruta and archivo.is_file() and archivo.is_relative_to(_web):
            # Los archivos de assets/ llevan hash en el nombre: se pueden guardar un año.
            cache = (
                "public, max-age=31536000, immutable" if ruta.startswith("assets/") else "no-cache"
            )
            return FileResponse(archivo, headers={"Cache-Control": cache})
        # Rutas de la app (/bitacora, /guardia, ...): siempre index.html.
        return FileResponse(_web / "index.html", headers={"Cache-Control": "no-cache"})
