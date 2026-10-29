"""Encolado de trabajos de alertas. En modo "sync" se procesan en la misma petición."""

import anyio.from_thread
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings
from app.db import sesion
from app.services.alertas import procesar_reporte

_pool: ArqRedis | None = None


async def iniciar() -> None:
    global _pool
    s = get_settings()
    if s.alertas_modo == "cola" and _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(s.redis_url))


async def cerrar() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


def encolar_reporte(tenant_id: int, reporte_id: int) -> None:
    """Llamar desde endpoints síncronos (corren en el threadpool de FastAPI)."""
    if get_settings().alertas_modo == "sync" or _pool is None:
        with sesion(tenant_id) as db:
            procesar_reporte(db, reporte_id)
        return
    anyio.from_thread.run(
        lambda: _pool.enqueue_job(
            "tarea_procesar_reporte", tenant_id, reporte_id, _job_id=f"reporte:{reporte_id}"
        )
    )
