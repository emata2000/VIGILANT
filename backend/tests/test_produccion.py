"""Piezas para producción: tokens vencidos, resumen matutino, config de push, URLs públicas."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.config import get_settings
from app.db import sesion
from app.models import DispositivoPush, ReporteGuardia, ResumenEnviado
from app.services import storage
from app.services.notificadores import NotificadorMemoria
from app.services.resumen import enviar_resumenes, texto_resumen
from tests.conftest import DENTRO_8

# 07:05 hora de Ciudad de México (UTC-6) → 13:05 UTC.
MANANA = datetime(2026, 10, 29, 13, 5, tzinfo=UTC)


class NotificadorConVencidos(NotificadorMemoria):
    def enviar_push(self, tokens, titulo, cuerpo, datos):
        super().enviar_push(tokens, titulo, cuerpo, datos)
        return ["fcm-cli"]


def test_push_borra_tokens_vencidos(client, parque):
    from app.services.notificadores import configurar_notificador

    configurar_notificador(NotificadorConVencidos())
    r = client.post(
        "/v1/reportes",
        headers=parque["h"]["guardia"],
        json={
            "uuid_cliente": str(uuid.uuid4()),
            "tipo_evento": "RUTINA_PASO",
            "timestamp_campo": datetime.now(UTC).isoformat(),
            "ubicacion": DENTRO_8,
        },
    )
    assert r.status_code == 201
    with sesion(bypass_rls=True) as db:
        assert db.scalar(select(func.count()).where(DispositivoPush.fcm_token == "fcm-cli")) == 0


def _silenciado(tenant_id, guardia_id, bodega_id, cuando):
    with sesion(tenant_id) as db:
        db.add(
            ReporteGuardia(
                tenant_id=tenant_id,
                uuid_cliente=uuid.uuid4(),
                guardia_id=guardia_id,
                tipo_evento="RUTINA_PASO",
                timestamp_campo=cuando,
                ubicacion_real=f"SRID=4326;POINT({DENTRO_8['lng']} {DENTRO_8['lat']})",
                bodega_detectada_id=bodega_id,
                estado_notificacion="SILENCIADO",
            )
        )
        db.commit()


def _activar_mute(client, parque, inicio="22:00", fin="07:00"):
    r = client.put(
        "/v1/me/alertas",
        headers=parque["h"]["cliente"],
        json={"modo_mute_activo": True, "mute_inicio_hora": inicio, "mute_fin_hora": fin},
    )
    assert r.status_code == 200, r.text


def test_resumen_matutino_una_vez_por_dia(client, parque):
    ids = parque["ids"]
    _activar_mute(client, parque)
    for horas in (2, 4, 6):  # 01:05, 03:05 y 05:05 locales: dentro del mute 22-07
        _silenciado(ids["tenant"], ids["guardia"], ids["bodega"], MANANA - timedelta(hours=horas))
    _silenciado(ids["tenant"], ids["guardia"], ids["bodega"], MANANA - timedelta(hours=30))  # ayer

    n = NotificadorMemoria()
    assert enviar_resumenes(MANANA, n) == 1
    assert n.push[0]["titulo"] == "Resumen de la noche"
    assert n.push[0]["cuerpo"].startswith("3 rondines")
    assert "Bodega 8" in n.push[0]["cuerpo"]
    # Otra pasada del cron en la misma mañana no repite.
    assert enviar_resumenes(MANANA + timedelta(minutes=5), n) == 0
    assert len(n.push) == 1
    with sesion(bypass_rls=True) as db:
        assert db.scalar(select(ResumenEnviado.rondines)) == 3


def test_resumen_fuera_de_ventana_o_sin_rondines(client, parque):
    ids = parque["ids"]
    _activar_mute(client, parque)
    n = NotificadorMemoria()
    assert enviar_resumenes(MANANA, n) == 0  # sin rondines silenciados: no molesta
    _silenciado(ids["tenant"], ids["guardia"], ids["bodega"], MANANA - timedelta(hours=2))
    assert enviar_resumenes(MANANA + timedelta(hours=3), n) == 0  # 10:05, ya pasó la ventana
    assert n.push == []


def test_texto_resumen_singular():
    from collections import Counter

    assert texto_resumen(Counter({"Bodega 8": 1})) == (
        "1 rondín sin novedades durante la noche (1 en Bodega 8)."
    )


def test_config_push_publica(client, monkeypatch):
    r = client.get("/v1/push/config")
    assert r.json() == {
        "habilitado": False,
        "whatsapp_habilitado": False,
        "firebase": None,
        "vapid_key": None,
    }
    s = get_settings()
    monkeypatch.setattr(s, "firebase_web_config", '{"apiKey": "AIza", "projectId": "p"}')
    monkeypatch.setattr(s, "firebase_vapid_key", "BKx")
    r = client.get("/v1/push/config")
    assert r.json()["habilitado"] is True
    assert r.json()["firebase"]["projectId"] == "p"


def test_urls_prefirmadas_usan_endpoint_publico(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "s3_endpoint_url", "http://minio:9000")
    monkeypatch.setattr(s, "s3_endpoint_publico", "https://s3.vigilant.mx")
    storage._cliente.cache_clear()
    try:
        url, _ = storage.url_subida("t1/a.jpg", "image/jpeg")
        assert url.startswith("https://s3.vigilant.mx/")
        assert storage.url_lectura("t1/a.jpg").startswith("https://s3.vigilant.mx/")
    finally:
        storage._cliente.cache_clear()


class SoloPush(NotificadorMemoria):
    whatsapp_disponible = False


def test_sin_whatsapp_la_emergencia_va_solo_por_push(client, parque):
    from app.services.notificadores import configurar_notificador

    n = SoloPush()
    configurar_notificador(n)
    r = client.post(
        "/v1/reportes",
        headers=parque["h"]["guardia"],
        json={
            "uuid_cliente": str(uuid.uuid4()),
            "tipo_evento": "ALERTA_EMERGENCIA",
            "timestamp_campo": datetime.now(UTC).isoformat(),
            "ubicacion": DENTRO_8,
        },
    )
    assert r.json()["estado_notificacion"] == "ENVIADO"
    assert n.whatsapp == []
    assert len(n.push) == 2  # dueño y administrador
    with sesion(bypass_rls=True) as db:
        from app.models import NotificacionEnviada

        canales = set(db.scalars(select(NotificacionEnviada.canal)))
    assert canales == {"PUSH"}


def test_tarea_resumenes_requiere_token(client, monkeypatch):
    assert client.post("/v1/tareas/resumenes").status_code == 403  # sin token configurado
    monkeypatch.setattr(get_settings(), "tareas_token", "secreto-cron")
    assert client.post("/v1/tareas/resumenes", headers={"X-Tarea-Token": "otro"}).status_code == 403
    r = client.post("/v1/tareas/resumenes", headers={"X-Tarea-Token": "secreto-cron"})
    assert r.status_code == 200
    assert r.json() == {"resumenes_enviados": 0}
