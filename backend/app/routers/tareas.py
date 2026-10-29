import hmac

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.services.resumen import enviar_resumenes

router = APIRouter(prefix="/v1/tareas", tags=["sistema"])


@router.post("/resumenes")
def disparar_resumenes(x_tarea_token: str = Header("")) -> dict:
    """Para hosting sin worker: un cron externo llama aquí cada 5-10 minutos.
    También mantiene despierto el servicio y la base de datos."""
    esperado = get_settings().tareas_token
    if not esperado or not hmac.compare_digest(x_tarea_token, esperado):
        raise HTTPException(403, "Token de tarea inválido")
    return {"resumenes_enviados": enviar_resumenes()}
