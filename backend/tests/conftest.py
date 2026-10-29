import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://vigilant:vigilant@localhost:5432/vigilant_test"
)
os.environ["ALERTAS_MODO"] = "sync"
os.environ.setdefault("S3_ACCESS_KEY", "prueba")
os.environ.setdefault("S3_SECRET_KEY", "prueba")

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.db import engine, sesion  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ConfiguracionAlertas, DispositivoPush, Tenant, Usuario  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.notificadores import NotificadorMemoria, configurar_notificador  # noqa: E402

PASSWORD = "secreto-123"
# Bodega 8: cuadrado de ~110 m en Monterrey. Coordenadas GeoJSON [lng, lat].
BODEGA_8 = [
    [-100.3000, 25.7000],
    [-100.2990, 25.7000],
    [-100.2990, 25.7010],
    [-100.3000, 25.7010],
    [-100.3000, 25.7000],
]
DENTRO_8 = {"lat": 25.7005, "lng": -100.2995}
FUERA = {"lat": 25.7100, "lng": -100.2800}  # ~2 km, área común


@pytest.fixture(scope="session", autouse=True)
def _esquema():
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _limpiar():
    yield
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL app.bypass_rls = 'on'"))
        conn.execute(text("TRUNCATE tenants, usuarios RESTART IDENTITY CASCADE"))


@pytest.fixture
def notificador() -> NotificadorMemoria:
    n = NotificadorMemoria()
    configurar_notificador(n)
    return n


@pytest.fixture
def client(notificador) -> TestClient:
    with TestClient(app) as c:
        yield c


def crear_tenant(slug: str, zona: str = "America/Mexico_City") -> int:
    with sesion(bypass_rls=True) as db:
        t = Tenant(slug=slug, nombre_comercial=slug.title(), zona_horaria=zona)
        db.add(t)
        db.commit()
        return t.id


def crear_usuario(
    tenant_id: int | None, email: str, rol: str, telefono: str | None = None, fcm: str | None = None
) -> int:
    with sesion(bypass_rls=True) as db:
        u = Usuario(
            tenant_id=tenant_id,
            email=email,
            password_hash=hash_password(PASSWORD),
            nombre=email.split("@")[0],
            telefono_whatsapp=telefono,
            rol=rol,
        )
        db.add(u)
        db.flush()
        if rol == "CLIENTE_FINAL":
            db.add(ConfiguracionAlertas(cliente_id=u.id, tenant_id=tenant_id))
        if fcm:
            db.add(DispositivoPush(tenant_id=tenant_id, usuario_id=u.id, fcm_token=fcm))
        db.commit()
        return u.id


def token(client: TestClient, tenant: str | None, email: str) -> dict:
    r = client.post("/v1/auth/login", json={"tenant": tenant, "email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def parque(client):
    """Un tenant con admin, cliente dueño de la bodega 8, guardia y un checkpoint."""
    t = crear_tenant("parque-norte")
    ids = {
        "tenant": t,
        "admin": crear_usuario(t, "admin@norte.mx", "TENANT_ADMIN", "+528110000001", "fcm-admin"),
        "cliente": crear_usuario(
            t, "cliente@norte.mx", "CLIENTE_FINAL", "+528110000002", "fcm-cli"
        ),
        "guardia": crear_usuario(t, "guardia@norte.mx", "GUARDIA"),
    }
    h = {
        "admin": token(client, "parque-norte", "admin@norte.mx"),
        "cliente": token(client, "parque-norte", "cliente@norte.mx"),
        "guardia": token(client, "parque-norte", "guardia@norte.mx"),
    }
    r = client.post(
        "/v1/geocercas",
        headers=h["admin"],
        json={
            "nombre_bodega": "Bodega 8",
            "num_bodega": "8",
            "cliente_id": ids["cliente"],
            "perimetro": {"type": "Polygon", "coordinates": [BODEGA_8]},
        },
    )
    assert r.status_code == 201, r.text
    ids["bodega"] = r.json()["id"]
    r = client.post(
        "/v1/puntos-control",
        headers=h["admin"],
        json={
            "codigo_uid": "NFC-04A1B2",
            "nombre_punto": "Puerta norte B8",
            "bodega_id": ids["bodega"],
            "coordenada_esperada": DENTRO_8,
        },
    )
    assert r.status_code == 201, r.text
    return {"ids": ids, "h": h}
