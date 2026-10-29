from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import UsuarioActual, db_tenant, requiere_rol, usuario_actual
from app.models import BodegaGeocerca, PuntoControl, Usuario
from app.schemas import GeocercaIn, GeocercaOut, PuntoControlIn, PuntoControlOut
from app.services.geo import geojson_a_ewkt, geom_a_geojson, punto_a_coordenada

router = APIRouter(prefix="/v1", tags=["geocercas"])

_admin = requiere_rol("TENANT_ADMIN")


def _geocerca_out(b: BodegaGeocerca) -> GeocercaOut:
    return GeocercaOut(
        id=b.id,
        tenant_id=b.tenant_id,
        nombre_bodega=b.nombre_bodega,
        num_bodega=b.num_bodega,
        cliente_id=b.cliente_id,
        perimetro=geom_a_geojson(b.perimetro),
    )


def _validar_cliente(db: Session, cliente_id: int | None) -> None:
    if cliente_id is None:
        return
    rol = db.scalar(select(Usuario.rol).where(Usuario.id == cliente_id))  # RLS: mismo tenant
    if rol != "CLIENTE_FINAL":
        raise HTTPException(422, "cliente_id debe ser un CLIENTE_FINAL de tu empresa")


@router.post("/geocercas", response_model=GeocercaOut, status_code=201)
def crear_geocerca(
    datos: GeocercaIn, actual: UsuarioActual = Depends(_admin), db: Session = Depends(db_tenant)
):
    _validar_cliente(db, datos.cliente_id)
    b = BodegaGeocerca(
        tenant_id=actual.tenant_id,
        cliente_id=datos.cliente_id,
        nombre_bodega=datos.nombre_bodega,
        num_bodega=datos.num_bodega,
        perimetro=geojson_a_ewkt(datos.perimetro.model_dump()),
    )
    db.add(b)
    try:
        db.commit()
    except IntegrityError as e:
        raise HTTPException(422, "El polígono no es válido (¿se cruza consigo mismo?)") from e
    db.refresh(b)
    return _geocerca_out(b)


@router.get("/geocercas", response_model=list[GeocercaOut])
def listar_geocercas(
    actual: UsuarioActual = Depends(usuario_actual), db: Session = Depends(db_tenant)
):
    q = select(BodegaGeocerca).order_by(BodegaGeocerca.id)
    if actual.rol == "CLIENTE_FINAL":
        q = q.where(BodegaGeocerca.cliente_id == actual.id)
    return [_geocerca_out(b) for b in db.scalars(q)]


@router.put("/geocercas/{geocerca_id}", response_model=GeocercaOut)
def actualizar_geocerca(
    geocerca_id: int,
    datos: GeocercaIn,
    _: UsuarioActual = Depends(_admin),
    db: Session = Depends(db_tenant),
):
    b = db.get(BodegaGeocerca, geocerca_id)
    if b is None:
        raise HTTPException(404, "Geocerca no encontrada")
    _validar_cliente(db, datos.cliente_id)
    b.nombre_bodega = datos.nombre_bodega
    b.num_bodega = datos.num_bodega
    b.cliente_id = datos.cliente_id
    b.perimetro = geojson_a_ewkt(datos.perimetro.model_dump())
    try:
        db.commit()
    except IntegrityError as e:
        raise HTTPException(422, "El polígono no es válido (¿se cruza consigo mismo?)") from e
    db.refresh(b)
    return _geocerca_out(b)


def _punto_out(p: PuntoControl) -> PuntoControlOut:
    return PuntoControlOut(
        id=p.id,
        codigo_uid=p.codigo_uid,
        nombre_punto=p.nombre_punto,
        bodega_id=p.bodega_id,
        coordenada_esperada=punto_a_coordenada(p.coordenada_esperada),
        tolerancia_metros=p.tolerancia_metros,
    )


@router.post("/puntos-control", response_model=PuntoControlOut, status_code=201)
def crear_punto(
    datos: PuntoControlIn, actual: UsuarioActual = Depends(_admin), db: Session = Depends(db_tenant)
):
    if datos.bodega_id is not None and db.get(BodegaGeocerca, datos.bodega_id) is None:
        raise HTTPException(422, "bodega_id no existe en tu empresa")
    c = datos.coordenada_esperada
    p = PuntoControl(
        tenant_id=actual.tenant_id,
        bodega_id=datos.bodega_id,
        codigo_uid=datos.codigo_uid,
        nombre_punto=datos.nombre_punto,
        coordenada_esperada=f"SRID=4326;POINT({c.lng} {c.lat})",
        tolerancia_metros=datos.tolerancia_metros,
    )
    db.add(p)
    try:
        db.commit()
    except IntegrityError as e:
        raise HTTPException(409, "Ya existe un punto con ese código") from e
    db.refresh(p)
    return _punto_out(p)


@router.get("/puntos-control", response_model=list[PuntoControlOut])
def listar_puntos(
    _: UsuarioActual = Depends(requiere_rol("TENANT_ADMIN", "GUARDIA")),
    db: Session = Depends(db_tenant),
):
    """La app del guardia descarga esta lista al iniciar turno para trabajar sin señal."""
    return [_punto_out(p) for p in db.scalars(select(PuntoControl).order_by(PuntoControl.id))]
