"""Endpoints que usa el panel web: edición de usuarios, bitácora con nombres y fotos, CORS."""

import uuid
from datetime import UTC, datetime

from tests.conftest import DENTRO_8, PASSWORD, crear_tenant, crear_usuario, token


def _reporte(**extra):
    return {
        "uuid_cliente": str(uuid.uuid4()),
        "tipo_evento": "RUTINA_PASO",
        "timestamp_campo": datetime.now(UTC).isoformat(),
        "ubicacion": DENTRO_8,
        **extra,
    }


def test_admin_da_de_baja_a_un_guardia(client, parque):
    h, ids = parque["h"], parque["ids"]
    r = client.patch(
        f"/v1/usuarios/{ids['guardia']}", headers=h["admin"], json={"status": "inactive"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "inactive"
    r = client.post(
        "/v1/auth/login",
        json={"tenant": "parque-norte", "email": "guardia@norte.mx", "password": PASSWORD},
    )
    assert r.status_code == 403


def test_admin_cambia_contrasena_y_borra_whatsapp(client, parque):
    h, ids = parque["h"], parque["ids"]
    r = client.patch(
        f"/v1/usuarios/{ids['cliente']}",
        headers=h["admin"],
        json={"password": "nueva-clave-99", "telefono_whatsapp": None, "nombre": "Bodegas Sol"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["telefono_whatsapp"] is None
    assert r.json()["nombre"] == "Bodegas Sol"
    r = client.post(
        "/v1/auth/login",
        json={"tenant": "parque-norte", "email": "cliente@norte.mx", "password": "nueva-clave-99"},
    )
    assert r.status_code == 200


def test_admin_no_se_da_de_baja_a_si_mismo(client, parque):
    h, ids = parque["h"], parque["ids"]
    r = client.patch(
        f"/v1/usuarios/{ids['admin']}", headers=h["admin"], json={"status": "inactive"}
    )
    assert r.status_code == 422


def test_admin_no_edita_usuarios_de_otra_empresa(client, parque):
    t = crear_tenant("parque-sur")
    ajeno = crear_usuario(t, "guardia@sur.mx", "GUARDIA")
    r = client.patch(f"/v1/usuarios/{ajeno}", headers=parque["h"]["admin"], json={"nombre": "x"})
    assert r.status_code == 404


def test_guardia_y_dueno_no_editan_usuarios(client, parque):
    h, ids = parque["h"], parque["ids"]
    for quien in ("guardia", "cliente"):
        r = client.patch(f"/v1/usuarios/{ids['guardia']}", headers=h[quien], json={"nombre": "x"})
        assert r.status_code == 403


def test_bitacora_trae_nombre_del_guardia_y_fotos(client, parque):
    h = parque["h"]
    r = client.post(
        "/v1/reportes",
        headers=h["guardia"],
        json=_reporte(multimedia=[{"storage_key": f"t{parque['ids']['tenant']}/foto.jpg"}]),
    )
    assert r.status_code == 201, r.text
    for quien in ("admin", "cliente"):
        r = client.get("/v1/reportes", headers=h[quien])
        assert r.status_code == 200
        rep = r.json()[0]
        assert rep["guardia_nombre"] == "guardia"
        assert len(rep["multimedia"]) == 1
        assert "foto.jpg" in rep["multimedia"][0]["url"]


def test_cors_permite_al_panel_local(client):
    r = client.options(
        "/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_token_de_superadmin_sigue_funcionando(client):
    crear_usuario(None, "root@vigilant.mx", "SUPER_ADMIN")
    h = token(client, None, "root@vigilant.mx")
    assert client.get("/v1/tenants", headers=h).status_code == 200
