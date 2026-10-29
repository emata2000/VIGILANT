import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/v1/push", tags=["notificaciones"])


class PushConfigOut(BaseModel):
    habilitado: bool
    whatsapp_habilitado: bool = False
    firebase: dict | None = None
    vapid_key: str | None = None


@router.get("/config", response_model=PushConfigOut)
def config_push() -> PushConfigOut:
    """Configuración pública de Firebase para que el navegador se suscriba a push.
    No incluye secretos: la configuración web y la clave VAPID son públicas por diseño."""
    s = get_settings()
    wa = bool(s.whatsapp_token and s.whatsapp_phone_id)
    if not (s.firebase_web_config and s.firebase_vapid_key):
        return PushConfigOut(habilitado=False, whatsapp_habilitado=wa)
    return PushConfigOut(
        habilitado=True,
        whatsapp_habilitado=wa,
        firebase=json.loads(s.firebase_web_config),
        vapid_key=s.firebase_vapid_key,
    )
