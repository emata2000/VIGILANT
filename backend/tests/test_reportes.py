import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import sesion
from app.models import NotificacionEnviada, ReporteGuardia
from tests.conftest import DENTRO_8, FUERA


def _reporte(tipo="RUTINA_PASO", ubicacion=DENTRO_8, cuando=None, **extra):
    return {
        "uuid_cliente": str(uuid.uuid4()),
        "tipo_evento": tipo,
        "timestamp_campo": (cuando or datetime.now(UTC)).isoformat(),
        "ubicacion": ubicacion,
        **extra,
    }


def _hoy_local(hora: int) -> datetime:
    """Una hora local de Monterrey (UTC-6, sin horario de verano desde 2022) de hoy o ayer,
    siempre en el pasado reciente."""
    ahora = datetime.now(UTC)
    local = (ahora - timedelta(hours=6)).replace(hour=hora, minute=0, second=0, microsecond=0)
    utc = local + timedelta(hours=6)
    if utc > ahora:
        utc -= timedelta(days=1)
    return utc.replace(tzinfo=UTC)


def test_rutina_en_bodega_notifica_al_cliente(client, parque, notificador):
    r = client.post("/v1/reportes", headers=parque["h"]["guardia"], json=_reporte())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["bodega_detectada_id"] == parque["ids"]["bodega"]
    assert body["estado_notificacion"] == "ENVIADO"
    assert notificador.push[0]["tokens"] == ["fcm-cli"]
    assert "Bodega 8" in notificador.push[0]["cuerpo"]
    assert notificador.whatsapp == []


def test_reenvio_no_duplica(client, parque, notificador):
    datos = _reporte()
    r1 = client.post("/v1/reportes", headers=parque["h"]["guardia"], json=datos)
    r2 = client.post("/v1/reportes", headers=parque["h"]["guardia"], json=datos)
    assert (r1.status_code, r2.status_code) == (201, 200)
    assert r2.json()["duplicado"] is True
    assert r1.json()["id"] == r2.json()["id"]
    assert len(notificador.push) == 1


def test_gps_justo_afuera_se_asigna_a_bodega_cercana(client, parque):
    # ~10 m al este del borde de la bodega 8
    cerca = {"lat": 25.7005, "lng": -100.2989}
    r = client.post("/v1/reportes", headers=parque["h"]["guardia"], json=_reporte(ubicacion=cerca))
    assert r.json()["bodega_detectada_id"] == parque["ids"]["bodega"]


def test_rutina_en_area_comun_se_guarda_sin_notificar(client, parque, notificador):
    r = client.post("/v1/reportes", headers=parque["h"]["guardia"], json=_reporte(ubicacion=FUERA))
    assert r.status_code == 201
    assert r.json()["bodega_detectada_id"] is None
    assert r.json()["estado_notificacion"] == "SIN_DESTINATARIO"
    assert notificador.push == []


def test_emergencia_fuera_de_geocerca_avisa_al_admin(client, parque, notificador):
    r = client.post(
        "/v1/reportes",
        headers=parque["h"]["guardia"],
        json=_reporte("ALERTA_EMERGENCIA", ubicacion=FUERA),
    )
    assert r.json()["estado_notificacion"] == "ENVIADO"
    assert [p["tokens"] for p in notificador.push] == [["fcm-admin"]]
    assert notificador.whatsapp[0]["telefono"] == "+528110000001"
    assert "área común" in notificador.whatsapp[0]["parametros"][0]


def test_emergencia_sin_gps_tambien_avisa(client, parque, notificador):
    r = client.post(
        "/v1/reportes",
        headers=parque["h"]["guardia"],
        json=_reporte("ALERTA_EMERGENCIA", ubicacion=None),
    )
    assert r.status_code == 201
    assert r.json()["ubicacion"] is None
    assert notificador.push


def test_mute_usa_la_hora_local_del_tenant(client, parque, notificador):
    h = parque["h"]
    r = client.put(
        "/v1/me/alertas",
        headers=h["cliente"],
        json={"modo_mute_activo": True, "mute_inicio_hora": "22:00", "mute_fin_hora": "06:00"},
    )
    assert r.status_code == 200
    # Las 23:00 en Monterrey son las 05:00 UTC: debe silenciarse aunque en UTC no sea de noche.
    noche = _hoy_local(23)
    rutina = client.post(
        "/v1/reportes",
        headers=h["guardia"],
        json=_reporte(cuando=datetime.now(UTC) - timedelta(minutes=1)),
    )
    assert rutina.status_code == 201
    # Reporte a las 23:00 locales que llega a tiempo
    from app.services import alertas

    with sesion(parque["ids"]["tenant"]) as db:
        rep = db.get(ReporteGuardia, rutina.json()["id"])
        rep.timestamp_campo = noche
        rep.estado_notificacion = "PENDIENTE"
        db.commit()
        db.execute(NotificacionEnviada.__table__.delete())
        db.commit()
        notificador.push.clear()
        d = alertas.procesar_reporte(db, rep.id, ahora=noche + timedelta(minutes=2))
    assert d.estado == "SILENCIADO"
    assert notificador.push == []

    emergencia = client.post(
        "/v1/reportes", headers=h["guardia"], json=_reporte("ALERTA_EMERGENCIA")
    )
    assert emergencia.json()["estado_notificacion"] == "ENVIADO"


def test_rutina_que_llega_tarde_no_se_notifica(client, parque, notificador):
    viejo = datetime.now(UTC) - timedelta(hours=3)
    r = client.post("/v1/reportes", headers=parque["h"]["guardia"], json=_reporte(cuando=viejo))
    assert r.json()["estado_notificacion"] == "TARDIO"
    assert notificador.push == []


def test_timestamp_futuro_rechazado(client, parque):
    futuro = datetime.now(UTC) + timedelta(hours=1)
    r = client.post("/v1/reportes", headers=parque["h"]["guardia"], json=_reporte(cuando=futuro))
    assert r.status_code == 422
    assert "futuro" in r.json()["detail"]


def test_timestamp_sin_zona_horaria_rechazado(client, parque):
    datos = _reporte()
    datos["timestamp_campo"] = "2026-10-29T10:00:00"
    r = client.post("/v1/reportes", headers=parque["h"]["guardia"], json=datos)
    assert r.status_code == 422


def test_lote_offline(client, parque, notificador):
    h = parque["h"]["guardia"]
    ya_enviado = _reporte()
    client.post("/v1/reportes", headers=h, json=ya_enviado)
    lote = [
        ya_enviado,
        _reporte(codigo_punto_control="NFC-04A1B2"),
        _reporte(codigo_punto_control="NO-EXISTE"),
        _reporte("ALERTA_EMERGENCIA"),
    ]
    r = client.post("/v1/reportes/lote", headers=h, json={"reportes": lote})
    assert r.status_code == 200
    res = {x["uuid_cliente"]: x for x in r.json()["resultados"]}
    assert res[ya_enviado["uuid_cliente"]]["duplicado"] is True
    assert res[lote[1]["uuid_cliente"]]["ok"] is True
    assert res[lote[2]["uuid_cliente"]] == {
        "uuid_cliente": lote[2]["uuid_cliente"],
        "ok": False,
        "reporte_id": None,
        "duplicado": False,
        "error": "Punto de control desconocido",
    }
    assert res[lote[3]["uuid_cliente"]]["ok"] is True


def test_falla_de_whatsapp_no_duplica_push_al_reintentar(client, parque, notificador):
    from app.services import alertas

    notificador.fallar_whatsapp = True
    r = client.post(
        "/v1/reportes", headers=parque["h"]["guardia"], json=_reporte("ALERTA_EMERGENCIA")
    )
    rid = r.json()["id"]
    pushes = len(notificador.push)
    assert pushes == 2  # cliente + admin

    notificador.fallar_whatsapp = False
    with sesion(parque["ids"]["tenant"]) as db:
        alertas.procesar_reporte(db, rid)
        estados = db.execute(
            select(NotificacionEnviada.canal, NotificacionEnviada.estado).where(
                NotificacionEnviada.reporte_id == rid
            )
        ).all()
    assert len(notificador.push) == pushes  # no se repitieron
    assert len(notificador.whatsapp) == 2
    assert {e for _, e in estados} == {"ENVIADO"}


def test_solo_guardias_envian_reportes(client, parque):
    r = client.post("/v1/reportes", headers=parque["h"]["cliente"], json=_reporte())
    assert r.status_code == 403


def test_bitacora_por_rol(client, parque):
    h = parque["h"]
    client.post("/v1/reportes", headers=h["guardia"], json=_reporte())
    client.post("/v1/reportes", headers=h["guardia"], json=_reporte(ubicacion=FUERA))
    assert len(client.get("/v1/reportes", headers=h["admin"]).json()) == 2
    assert len(client.get("/v1/reportes", headers=h["guardia"]).json()) == 2
    # El cliente solo ve lo ocurrido en su bodega
    assert len(client.get("/v1/reportes", headers=h["cliente"]).json()) == 1
