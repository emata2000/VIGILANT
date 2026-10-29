from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import UsuarioActual, db_tenant, requiere_rol, usuario_actual
from app.models import BodegaGeocerca, ReporteGuardia
from app.schemas import (
    LoteIn,
    LoteOut,
    ReporteIn,
    ReporteOut,
    ResultadoLote,
    UrlSubidaIn,
    UrlSubidaOut,
)
from app.services import storage
from app.services.cola import encolar_reporte
from app.services.geo import punto_a_coordenada
from app.services.reportes import ReporteInvalido, crear_reporte

router = APIRouter(prefix="/v1", tags=["reportes"])

_guardia = requiere_rol("GUARDIA")


def _out(r: ReporteGuardia, duplicado: bool = False) -> ReporteOut:
    return ReporteOut(
        id=r.id,
        uuid_cliente=r.uuid_cliente,
        tipo_evento=r.tipo_evento,
        timestamp_campo=r.timestamp_campo,
        recibido_el=r.recibido_el,
        guardia_id=r.guardia_id,
        ubicacion=punto_a_coordenada(r.ubicacion_real),
        precision_metros=r.precision_metros,
        bodega_detectada_id=r.bodega_detectada_id,
        punto_control_id=r.punto_control_id,
        estado_notificacion=r.estado_notificacion,
        descripcion=r.descripcion,
        duplicado=duplicado,
    )


@router.post("/multimedia/url", response_model=UrlSubidaOut)
def pedir_url_subida(datos: UrlSubidaIn, actual: UsuarioActual = Depends(_guardia)):
    """Paso 1 de la subida: la app pide una URL prefirmada y hace PUT de la foto ahí."""
    key = storage.nueva_llave(actual.tenant_id, datos.content_type)
    url, segundos = storage.url_subida(key, datos.content_type)
    return UrlSubidaOut(storage_key=key, url=url, expira_en_segundos=segundos)


@router.post(
    "/reportes",
    response_model=ReporteOut,
    status_code=201,
    responses={200: {"description": "El reporte ya existía (reenvío); no se duplicó"}},
)
def recibir_reporte(
    datos: ReporteIn,
    response: Response,
    actual: UsuarioActual = Depends(_guardia),
    db: Session = Depends(db_tenant),
):
    try:
        res = crear_reporte(db, actual.tenant_id, actual.id, datos)
    except ReporteInvalido as e:
        raise HTTPException(422, str(e)) from e
    if res.duplicado:
        response.status_code = 200
    else:
        encolar_reporte(actual.tenant_id, res.reporte.id)
        db.refresh(res.reporte)
    return _out(res.reporte, res.duplicado)


@router.post("/reportes/lote", response_model=LoteOut)
def recibir_lote(
    datos: LoteIn, actual: UsuarioActual = Depends(_guardia), db: Session = Depends(db_tenant)
):
    """Sincronización diferida: la app envía hasta 100 reportes guardados sin señal.
    Cada uno se procesa por separado; un reporte inválido no tumba al resto."""
    resultados = []
    for item in sorted(datos.reportes, key=lambda r: r.timestamp_campo):
        try:
            res = crear_reporte(db, actual.tenant_id, actual.id, item)
        except ReporteInvalido as e:
            db.rollback()
            resultados.append(ResultadoLote(uuid_cliente=item.uuid_cliente, ok=False, error=str(e)))
            continue
        if not res.duplicado:
            encolar_reporte(actual.tenant_id, res.reporte.id)
        resultados.append(
            ResultadoLote(
                uuid_cliente=item.uuid_cliente,
                ok=True,
                reporte_id=res.reporte.id,
                duplicado=res.duplicado,
            )
        )
    return LoteOut(resultados=resultados)


@router.get("/reportes", response_model=list[ReporteOut])
def listar_reportes(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    bodega_id: int | None = None,
    tipo_evento: str | None = None,
    limite: int = Query(100, ge=1, le=500),
    actual: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(db_tenant),
):
    """Bitácora. El admin ve todo su tenant, el guardia sus reportes y el cliente sus bodegas."""
    q = select(ReporteGuardia).order_by(ReporteGuardia.timestamp_campo.desc()).limit(limite)
    if actual.rol == "GUARDIA":
        q = q.where(ReporteGuardia.guardia_id == actual.id)
    elif actual.rol == "DUENO_NAVE":
        q = q.join(BodegaGeocerca, BodegaGeocerca.id == ReporteGuardia.bodega_detectada_id).where(
            BodegaGeocerca.cliente_id == actual.id
        )
    if desde:
        q = q.where(ReporteGuardia.timestamp_campo >= desde)
    if hasta:
        q = q.where(ReporteGuardia.timestamp_campo < hasta)
    if bodega_id:
        q = q.where(ReporteGuardia.bodega_detectada_id == bodega_id)
    if tipo_evento:
        q = q.where(ReporteGuardia.tipo_evento == tipo_evento)
    return [_out(r) for r in db.scalars(q)]
