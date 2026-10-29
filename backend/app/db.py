"""Conexión a la base de datos y contexto de tenant para Row-Level Security.

Cada sesión lleva en `session.info` el tenant activo. Al iniciar cada transacción se
ejecuta `set_config('app.tenant_id', ...)` con alcance local a la transacción, y las
políticas RLS de PostgreSQL filtran todas las tablas por ese valor. Así, un filtro
olvidado en el código no expone datos de otro tenant.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def _aplicar_contexto_tenant(session: Session, transaction, connection) -> None:
    tenant_id = session.info.get("tenant_id")
    bypass = session.info.get("bypass_rls", False)
    connection.execute(
        text(
            "SELECT set_config('app.tenant_id', :t, true), set_config('app.bypass_rls', :b, true)"
        ),
        {"t": "" if tenant_id is None else str(tenant_id), "b": "on" if bypass else "off"},
    )


@contextmanager
def sesion(tenant_id: int | None = None, *, bypass_rls: bool = False) -> Iterator[Session]:
    """Abre una sesión limitada a un tenant. `bypass_rls` solo para login y SUPER_ADMIN."""
    db = SessionLocal()
    db.info["tenant_id"] = tenant_id
    db.info["bypass_rls"] = bypass_rls
    try:
        yield db
    finally:
        db.close()
