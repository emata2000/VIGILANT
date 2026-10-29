"""Aislamiento entre empresas: lo que crea un tenant no debe verlo ni tocarlo otro."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text

from app.db import sesion
from app.models import BodegaGeocerca, ReporteGuardia, Usuario
from tests.conftest import DENTRO_8, crear_tenant, crear_usuario, token


def _otro_parque(client):
    t = crear_tenant("parque-sur", zona="America/Tijuana")
    crear_usuario(t, "admin@sur.mx", "TENANT_ADMIN")
    crear_usuario(t, "guardia@sur.mx", "GUARDIA")
    return t, {
        "admin": token(client, "parque-sur", "admin@sur.mx"),
        "guardia": token(client, "parque-sur", "guardia@sur.mx"),
    }


def test_rls_filtra_aunque_la_consulta_no_filtre(parque, client):
    t_sur, _ = _otro_parque(client)
    with sesion(t_sur) as db:
        # Consultas sin WHERE tenant_id: RLS solo deja ver filas del tenant activo.
        assert db.scalar(select(func.count()).select_from(BodegaGeocerca)) == 0
        emails = set(db.scalars(select(Usuario.email)))
        assert emails == {"admin@sur.mx", "guardia@sur.mx"}
    with sesion(None) as db:
        assert db.scalar(select(func.count()).select_from(Usuario)) == 0


def test_rls_impide_escribir_en_otro_tenant(parque, client):
    t_sur, _ = _otro_parque(client)
    with sesion(t_sur) as db:
        n = db.execute(text("UPDATE bodegas_geocercas SET nombre_bodega = 'hackeada'")).rowcount
        db.commit()
    assert n == 0


def test_guardia_de_otro_tenant_no_dispara_alertas_en_bodega_ajena(parque, client, notificador):
    _, h_sur = _otro_parque(client)
    r = client.post(
        "/v1/reportes",
        headers=h_sur["guardia"],
        json={
            "uuid_cliente": str(uuid.uuid4()),
            "tipo_evento": "RUTINA_PASO",
            "timestamp_campo": datetime.now(UTC).isoformat(),
            "ubicacion": DENTRO_8,  # dentro de la bodega 8 del parque norte
        },
    )
    assert r.status_code == 201
    assert r.json()["bodega_detectada_id"] is None
    assert notificador.push == []


def test_checkpoint_de_otro_tenant_es_desconocido(parque, client):
    _, h_sur = _otro_parque(client)
    r = client.post(
        "/v1/reportes",
        headers=h_sur["guardia"],
        json={
            "uuid_cliente": str(uuid.uuid4()),
            "tipo_evento": "RUTINA_PASO",
            "timestamp_campo": datetime.now(UTC).isoformat(),
            "codigo_punto_control": "NFC-04A1B2",
        },
    )
    assert r.status_code == 422


def test_uuid_de_otro_tenant_no_se_filtra(parque, client):
    _, h_sur = _otro_parque(client)
    datos = {
        "uuid_cliente": str(uuid.uuid4()),
        "tipo_evento": "RUTINA_PASO",
        "timestamp_campo": datetime.now(UTC).isoformat(),
    }
    assert (
        client.post("/v1/reportes", headers=parque["h"]["guardia"], json=datos).status_code == 201
    )
    r = client.post("/v1/reportes", headers=h_sur["guardia"], json=datos)
    assert r.status_code == 422
    with sesion(bypass_rls=True) as db:
        assert db.scalar(select(func.count()).select_from(ReporteGuardia)) == 1


def test_admin_no_ve_geocercas_ajenas(parque, client):
    _, h_sur = _otro_parque(client)
    assert client.get("/v1/geocercas", headers=h_sur["admin"]).json() == []


def test_admin_no_asigna_cliente_de_otro_tenant(parque, client):
    _, h_sur = _otro_parque(client)
    r = client.post(
        "/v1/geocercas",
        headers=h_sur["admin"],
        json={
            "nombre_bodega": "B1",
            "cliente_id": parque["ids"]["cliente"],
            "perimetro": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 0.001], [0.001, 0.001], [0, 0]]],
            },
        },
    )
    assert r.status_code == 422


def test_login_requiere_tenant_correcto(parque, client):
    r = client.post(
        "/v1/auth/login",
        json={"tenant": "parque-sur", "email": "admin@norte.mx", "password": "secreto-123"},
    )
    assert r.status_code == 401


def test_poligono_invalido(parque, client):
    moño = [[0, 0], [0.001, 0.001], [0.001, 0], [0, 0.001], [0, 0]]
    r = client.post(
        "/v1/geocercas",
        headers=parque["h"]["admin"],
        json={"nombre_bodega": "X", "perimetro": {"type": "Polygon", "coordinates": [moño]}},
    )
    assert r.status_code == 422


def test_superadmin_crea_tenant_y_admin(client):
    crear_usuario(None, "root@vigilant.mx", "SUPER_ADMIN")
    h = token(client, None, "root@vigilant.mx")
    r = client.post(
        "/v1/tenants",
        headers=h,
        json={
            "slug": "parque-este",
            "nombre_comercial": "Parque Este",
            "zona_horaria": "America/Cancun",
        },
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    r = client.post(
        "/v1/usuarios",
        headers=h,
        json={
            "email": "Admin@Este.mx",
            "password": "secreto-123",
            "nombre": "Admin",
            "rol": "TENANT_ADMIN",
            "tenant_id": tid,
        },
    )
    assert r.status_code == 201, r.text
    h_admin = token(client, "parque-este", "admin@este.mx")
    assert client.get("/v1/auth/me", headers=h_admin).json()["tenant_id"] == tid
    assert (
        client.post(
            "/v1/tenants", headers=h_admin, json={"slug": "x-y", "nombre_comercial": "x"}
        ).status_code
        == 403
    )
