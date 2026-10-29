"""Canales de salida: push con Firebase Cloud Messaging y WhatsApp con la Cloud API de Meta.
Sin credenciales, `NotificadorLog` escribe en el log; `NotificadorMemoria` sirve para pruebas."""

import json
import logging
import threading
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx
import jwt

log = logging.getLogger("vigilant.notificaciones")


class ErrorEnvio(Exception):
    def __init__(self, mensaje: str, tokens_invalidos: list[str] | None = None):
        super().__init__(mensaje)
        self.tokens_invalidos = tokens_invalidos or []


class Notificador(Protocol):
    def enviar_push(
        self, tokens: list[str], titulo: str, cuerpo: str, datos: dict
    ) -> list[str] | None:
        """Devuelve los tokens que ya no sirven (para borrarlos), o None."""
        ...

    def enviar_whatsapp(self, telefono: str, plantilla: str, parametros: list[str]) -> None: ...


class NotificadorLog:
    def enviar_push(self, tokens: list[str], titulo: str, cuerpo: str, datos: dict) -> None:
        log.info("PUSH a %d dispositivo(s): %s | %s | %s", len(tokens), titulo, cuerpo, datos)

    def enviar_whatsapp(self, telefono: str, plantilla: str, parametros: list[str]) -> None:
        log.info("WHATSAPP a %s: %s %s", telefono, plantilla, parametros)


@dataclass
class NotificadorMemoria:
    push: list[dict] = field(default_factory=list)
    whatsapp: list[dict] = field(default_factory=list)
    fallar_whatsapp: bool = False

    def enviar_push(self, tokens: list[str], titulo: str, cuerpo: str, datos: dict) -> None:
        self.push.append({"tokens": tokens, "titulo": titulo, "cuerpo": cuerpo, "datos": datos})

    def enviar_whatsapp(self, telefono: str, plantilla: str, parametros: list[str]) -> None:
        if self.fallar_whatsapp:
            raise ErrorEnvio("WhatsApp no disponible")
        self.whatsapp.append(
            {"telefono": telefono, "plantilla": plantilla, "parametros": parametros}
        )


_notificador: Notificador | None = None


def obtener_notificador() -> Notificador:
    global _notificador
    if _notificador is None:
        _notificador = notificador_desde_config()
    return _notificador


def configurar_notificador(n: Notificador) -> None:
    global _notificador
    _notificador = n


# ---------- Canales reales ----------

# Errores de FCM que significan "este token ya no sirve": se borra del usuario.
_FCM_TOKEN_INVALIDO = {"UNREGISTERED", "INVALID_ARGUMENT", "NOT_FOUND"}


def _cargar_json(valor: str) -> dict:
    valor = valor.strip()
    if valor.startswith("{"):
        return json.loads(valor)
    return json.loads(Path(valor).read_text())


class PushFirebase:
    """Firebase Cloud Messaging (API HTTP v1) con una cuenta de servicio."""

    def __init__(self, credenciales: dict, panel_url: str, http: httpx.Client | None = None):
        self._cred = credenciales
        self._proyecto = credenciales["project_id"]
        self._panel = panel_url.rstrip("/")
        self._http = http or httpx.Client(timeout=10)
        self._token: tuple[str, float] | None = None
        self._lock = threading.Lock()

    def _token_acceso(self) -> str:
        with self._lock:
            if self._token and self._token[1] > _time.time() + 60:
                return self._token[0]
            ahora = int(_time.time())
            uri = self._cred.get("token_uri", "https://oauth2.googleapis.com/token")
            asercion = jwt.encode(
                {
                    "iss": self._cred["client_email"],
                    "scope": "https://www.googleapis.com/auth/firebase.messaging",
                    "aud": uri,
                    "iat": ahora,
                    "exp": ahora + 3600,
                },
                self._cred["private_key"],
                algorithm="RS256",
            )
            r = self._http.post(
                uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": asercion,
                },
            )
            if r.status_code != 200:
                raise ErrorEnvio(f"Firebase rechazó la cuenta de servicio: {r.text[:200]}")
            datos = r.json()
            self._token = (datos["access_token"], ahora + int(datos.get("expires_in", 3600)))
            return self._token[0]

    def enviar(self, tokens: list[str], titulo: str, cuerpo: str, datos: dict) -> list[str]:
        """Envía a cada token. Devuelve los tokens inválidos. Falla si ninguno se entregó."""
        url = f"https://fcm.googleapis.com/v1/projects/{self._proyecto}/messages:send"
        headers = {"Authorization": f"Bearer {self._token_acceso()}"}
        datos = {k: str(v) for k, v in datos.items()}
        urgente = datos.get("tipo") == "ALERTA_EMERGENCIA"
        invalidos: list[str] = []
        errores: list[str] = []
        entregados = 0
        for token in tokens:
            mensaje = {
                "token": token,
                "notification": {"title": titulo, "body": cuerpo},
                "data": datos,
                "android": {"priority": "high" if urgente else "normal"},
                "webpush": {
                    "headers": {"Urgency": "high" if urgente else "normal"},
                    "fcm_options": {"link": f"{self._panel}/bitacora"},
                },
            }
            r = self._http.post(url, headers=headers, json={"message": mensaje})
            if r.status_code == 200:
                entregados += 1
                continue
            try:
                err = r.json().get("error", {})
                detalles = [d.get("errorCode") for d in err.get("details", [])]
                codigo = next((d for d in detalles if d), err.get("status", ""))
            except ValueError:
                codigo = ""
            if codigo in _FCM_TOKEN_INVALIDO or r.status_code == 404:
                invalidos.append(token)
            else:
                errores.append(f"FCM {r.status_code} {codigo}".strip())
        if not entregados:
            motivo = errores[0] if errores else "Todos los dispositivos están dados de baja"
            raise ErrorEnvio(motivo, invalidos)
        return invalidos


class WhatsAppMeta:
    """WhatsApp Cloud API: mensajes de plantilla aprobados por Meta."""

    def __init__(
        self,
        token: str,
        phone_id: str,
        version: str = "v23.0",
        idioma: str = "es_MX",
        http: httpx.Client | None = None,
    ):
        self._url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._idioma = idioma
        self._http = http or httpx.Client(timeout=10)

    def enviar(self, telefono: str, plantilla: str, parametros: list[str]) -> None:
        cuerpo = {
            "messaging_product": "whatsapp",
            "to": telefono.lstrip("+"),
            "type": "template",
            "template": {
                "name": plantilla,
                "language": {"code": self._idioma},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in parametros],
                    }
                ],
            },
        }
        r = self._http.post(self._url, headers=self._headers, json=cuerpo)
        if r.status_code != 200:
            try:
                msg = r.json().get("error", {}).get("message", "")
            except ValueError:
                msg = r.text[:200]
            raise ErrorEnvio(f"WhatsApp {r.status_code}: {msg}")


class NotificadorReal:
    """Usa los canales configurados. Un canal sin configurar cuenta como envío fallido,
    para que la bitácora no diga "Notificado" cuando no se mandó nada."""

    def __init__(self, push: PushFirebase | None, whatsapp: WhatsAppMeta | None):
        self.push = push
        self.whatsapp = whatsapp
        # Sin WhatsApp configurado (lanzamiento solo con push) ese canal ni se intenta.
        self.whatsapp_disponible = whatsapp is not None

    def enviar_push(self, tokens: list[str], titulo: str, cuerpo: str, datos: dict) -> list[str]:
        if self.push is None:
            raise ErrorEnvio("Push no configurado (falta FIREBASE_CREDENCIALES)")
        return self.push.enviar(tokens, titulo, cuerpo, datos)

    def enviar_whatsapp(self, telefono: str, plantilla: str, parametros: list[str]) -> None:
        if self.whatsapp is None:
            raise ErrorEnvio("WhatsApp no configurado (faltan WHATSAPP_TOKEN y WHATSAPP_PHONE_ID)")
        self.whatsapp.enviar(telefono, plantilla, parametros)


def notificador_desde_config() -> Notificador:
    """Canales reales si hay credenciales; si no, solo el log (desarrollo)."""
    from app.config import get_settings

    s = get_settings()
    push = (
        PushFirebase(_cargar_json(s.firebase_credenciales), s.panel_url)
        if s.firebase_credenciales
        else None
    )
    wa = (
        WhatsAppMeta(
            s.whatsapp_token, s.whatsapp_phone_id, s.whatsapp_api_version, s.whatsapp_idioma
        )
        if s.whatsapp_token and s.whatsapp_phone_id
        else None
    )
    if push is None and wa is None:
        log.warning(
            "Sin credenciales de Firebase ni WhatsApp: los avisos solo se escriben en el log"
        )
        return NotificadorLog()
    return NotificadorReal(push, wa)
