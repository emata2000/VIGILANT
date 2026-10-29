from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import admin, alertas, auth, geocercas, reportes
from app.services import cola


@asynccontextmanager
async def lifespan(_: FastAPI):
    await cola.iniciar()
    yield
    await cola.cerrar()


app = FastAPI(
    title="VIGILANT API",
    version="0.1.0",
    description="SaaS multi-tenant de patrullaje vehicular con geocercas y alertas.",
    lifespan=lifespan,
)

for r in (auth, admin, geocercas, reportes, alertas):
    app.include_router(r.router)


@app.get("/salud", tags=["sistema"])
def salud() -> dict:
    return {"ok": True}
