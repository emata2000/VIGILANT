from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PuntoControl, ReporteGuardia, ReporteMultimedia
from app.schemas import ReporteIn
from app.services.geo import resolver_bodega
from app.services.storage import llave_pertenece_a_tenant


class ReporteInvalido(ValueError):
    pass


@dataclass
class Resultado:
    reporte: ReporteGuardia
    duplicado: bool


def crear_reporte(db: Session, tenant_id: int, guardia_id: int, datos: ReporteIn) -> Resultado:
    """Guarda un reporte. Si `uuid_cliente` ya existe, devuelve el existente sin duplicar,
    para que la app pueda reintentar envíos offline sin miedo."""
    s = get_settings()

    existente = db.scalar(
        select(ReporteGuardia).where(ReporteGuardia.uuid_cliente == datos.uuid_cliente)
    )
    if existente is not None:
        if existente.tenant_id != tenant_id or existente.guardia_id != guardia_id:
            raise ReporteInvalido("uuid_cliente ya usado por otro reporte")
        return Resultado(existente, duplicado=True)

    limite = datetime.now(UTC) + timedelta(minutes=s.reloj_tolerancia_futuro_min)
    if datos.timestamp_campo > limite:
        raise ReporteInvalido("timestamp_campo está en el futuro: revisa el reloj del teléfono")

    for m in datos.multimedia:
        if not llave_pertenece_a_tenant(m.storage_key, tenant_id):
            raise ReporteInvalido(f"storage_key no pertenece a este tenant: {m.storage_key}")

    punto_id = None
    if datos.codigo_punto_control:
        punto_id = db.scalar(
            select(PuntoControl.id).where(
                PuntoControl.tenant_id == tenant_id,
                PuntoControl.codigo_uid == datos.codigo_punto_control,
            )
        )
        if punto_id is None:
            raise ReporteInvalido("Punto de control desconocido")

    ubicacion = None
    bodega_id = None
    if datos.ubicacion is not None:
        u = datos.ubicacion
        ubicacion = f"SRID=4326;POINT({u.lng} {u.lat})"
        bodega = resolver_bodega(db, tenant_id, u.lng, u.lat, s.geocerca_tolerancia_m)
        bodega_id = bodega.id if bodega else None

    # ON CONFLICT cubre la carrera de dos reenvíos simultáneos del mismo reporte.
    stmt = (
        insert(ReporteGuardia)
        .values(
            tenant_id=tenant_id,
            guardia_id=guardia_id,
            uuid_cliente=datos.uuid_cliente,
            tipo_evento=datos.tipo_evento,
            descripcion=datos.descripcion,
            punto_control_id=punto_id,
            ubicacion_real=ubicacion,
            precision_metros=datos.ubicacion.precision_metros if datos.ubicacion else None,
            bodega_detectada_id=bodega_id,
            timestamp_campo=datos.timestamp_campo,
        )
        .on_conflict_do_nothing(index_elements=["uuid_cliente"])
        .returning(ReporteGuardia.id)
    )
    nuevo_id = db.scalar(stmt)
    if nuevo_id is None:
        # Otro envío del mismo reporte ganó la carrera, o el UUID existe en otro tenant
        # (invisible por RLS).
        db.rollback()
        existente = db.scalar(
            select(ReporteGuardia).where(ReporteGuardia.uuid_cliente == datos.uuid_cliente)
        )
        if existente is None or existente.guardia_id != guardia_id:
            raise ReporteInvalido("uuid_cliente ya usado por otro reporte")
        return Resultado(existente, duplicado=True)

    for m in datos.multimedia:
        db.add(
            ReporteMultimedia(
                tenant_id=tenant_id, reporte_id=nuevo_id, storage_key=m.storage_key, tipo=m.tipo
            )
        )
    db.commit()
    return Resultado(db.get(ReporteGuardia, nuevo_id), duplicado=False)
