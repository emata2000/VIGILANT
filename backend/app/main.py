from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, alertas, auth, geocercas, push, reportes
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origenes,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

for r in (auth, admin, geocercas, reportes, alertas, push):
    app.include_router(r.router)


@app.get("/salud", tags=["sistema"])
def salud() -> dict:
    return {"ok": True}
