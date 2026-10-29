"""Worker de la cola de alertas (ARQ sobre Redis).

Ejecutar con:  uv run arq app.worker.WorkerSettings
"""

import asyncio

from arq import Retry
from arq.connections import RedisSettings

from app.config import get_settings
from app.db import sesion
from app.models import ReporteGuardia
from app.services.alertas import procesar_reporte
from app.services.storage import url_lectura


def _procesar(tenant_id: int, reporte_id: int) -> tuple[str, bool]:
    with sesion(tenant_id) as db:
        decision = procesar_reporte(db, reporte_id, url_evidencia=url_lectura)
        reporte = db.get(ReporteGuardia, reporte_id)
        todos_fallaron = reporte is not None and reporte.estado_notificacion == "PENDIENTE"
        return (decision.estado if decision else "NO_ENCONTRADO"), todos_fallaron


async def tarea_procesar_reporte(ctx, tenant_id: int, reporte_id: int) -> str:
    # El acceso a base de datos es síncrono: se ejecuta en un hilo para no bloquear el worker.
    estado, todos_fallaron = await asyncio.to_thread(_procesar, tenant_id, reporte_id)
    if todos_fallaron:
        raise Retry(defer=min(300, 15 * 2 ** ctx["job_try"]))  # espera creciente
    return estado


class WorkerSettings:
    functions = [tarea_procesar_reporte]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 6
