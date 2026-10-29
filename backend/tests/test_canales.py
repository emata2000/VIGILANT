"""Canales reales (Firebase y WhatsApp) contra servidores simulados con httpx.MockTransport."""

import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.notificadores import ErrorEnvio, NotificadorReal, PushFirebase, WhatsAppMeta


def _credenciales() -> dict:
    llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = llave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return {
        "project_id": "vigilant-prueba",
        "client_email": "push@vigilant-prueba.iam.gserviceaccount.com",
        "private_key": pem,
        "token_uri": "https://oauth2.googleapis.com/token",
    }


class ServidorFcm:
    def __init__(self, respuestas: dict[str, tuple[int, dict]]):
        self.respuestas = respuestas
        self.mensajes: list[dict] = []
        self.tokens_pedidos = 0

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if req.url.host == "oauth2.googleapis.com":
            self.tokens_pedidos += 1
            assert b"assertion=" in req.content
            return httpx.Response(200, json={"access_token": "ya29.prueba", "expires_in": 3600})
        assert req.url.path == "/v1/projects/vigilant-prueba/messages:send"
        assert req.headers["authorization"] == "Bearer ya29.prueba"
        msg = json.loads(req.content)["message"]
        self.mensajes.append(msg)
        status, cuerpo = self.respuestas.get(msg["token"], (200, {"name": "ok"}))
        return httpx.Response(status, json=cuerpo)


def _no_registrado():
    return 404, {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}}


def test_push_envia_y_reporta_tokens_vencidos():
    srv = ServidorFcm({"viejo": _no_registrado()})
    push = PushFirebase(
        _credenciales(), "https://app.vigilant.mx", httpx.Client(transport=httpx.MockTransport(srv))
    )
    invalidos = push.enviar(
        ["bueno", "viejo"], "ALERTA", "Bodega 8", {"tipo": "ALERTA_EMERGENCIA", "reporte_id": 5}
    )
    assert invalidos == ["viejo"]
    assert srv.mensajes[0]["notification"] == {"title": "ALERTA", "body": "Bodega 8"}
    assert srv.mensajes[0]["android"]["priority"] == "high"
    assert srv.mensajes[0]["webpush"]["fcm_options"]["link"] == "https://app.vigilant.mx/bitacora"
    assert srv.mensajes[0]["data"]["reporte_id"] == "5"  # FCM solo acepta strings
    # El token de acceso se reutiliza entre envíos.
    push.enviar(["bueno"], "x", "y", {})
    assert srv.tokens_pedidos == 1


def test_push_falla_si_ningun_dispositivo_recibio():
    srv = ServidorFcm({"viejo": _no_registrado()})
    push = PushFirebase(
        _credenciales(), "https://x.mx", httpx.Client(transport=httpx.MockTransport(srv))
    )
    with pytest.raises(ErrorEnvio) as e:
        push.enviar(["viejo"], "x", "y", {})
    assert e.value.tokens_invalidos == ["viejo"]


def test_whatsapp_manda_plantilla():
    enviados = []

    def meta(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v23.0/123456/messages"
        assert req.headers["authorization"] == "Bearer EAAG"
        enviados.append(json.loads(req.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    wa = WhatsAppMeta("EAAG", "123456", http=httpx.Client(transport=httpx.MockTransport(meta)))
    wa.enviar("+528110000002", "plantilla_emergencia_v1", ["Bodega 8", "https://foto"])
    m = enviados[0]
    assert m["to"] == "528110000002"
    assert m["template"]["name"] == "plantilla_emergencia_v1"
    assert m["template"]["language"]["code"] == "es_MX"
    assert [p["text"] for p in m["template"]["components"][0]["parameters"]] == [
        "Bodega 8",
        "https://foto",
    ]


def test_whatsapp_error_de_meta():
    def meta(req):
        return httpx.Response(400, json={"error": {"message": "Template name does not exist"}})

    wa = WhatsAppMeta("EAAG", "1", http=httpx.Client(transport=httpx.MockTransport(meta)))
    with pytest.raises(ErrorEnvio, match="Template name does not exist"):
        wa.enviar("+528110000002", "plantilla_x", [])


def test_canal_sin_configurar_cuenta_como_fallo():
    n = NotificadorReal(push=None, whatsapp=None)
    with pytest.raises(ErrorEnvio, match="Push no configurado"):
        n.enviar_push(["t"], "a", "b", {})
    with pytest.raises(ErrorEnvio, match="WhatsApp no configurado"):
        n.enviar_whatsapp("+5281", "p", [])
