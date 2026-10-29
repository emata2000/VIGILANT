from dataclasses import dataclass

from geoalchemy2.shape import to_shape
from shapely.geometry import mapping, shape
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class BodegaDetectada:
    id: int
    cliente_id: int | None
    nombre_bodega: str
    dentro: bool  # False si se asignó por cercanía (GPS justo afuera del polígono)


def resolver_bodega(
    db: Session, tenant_id: int, lng: float, lat: float, tolerancia_m: float
) -> BodegaDetectada | None:
    """Busca la bodega que contiene el punto. Si ninguna lo contiene, toma la más cercana
    dentro de `tolerancia_m` metros, porque el GPS puede marcar al guardia justo afuera.
    Siempre filtra por tenant (además de RLS)."""
    fila = db.execute(
        text(
            """
            WITH p AS (SELECT ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) AS g)
            SELECT b.id, b.cliente_id, b.nombre_bodega, ST_Contains(b.perimetro, p.g) AS dentro
            FROM bodegas_geocercas b, p
            WHERE b.tenant_id = :tenant_id
              AND ST_DWithin(b.perimetro::geography, p.g::geography, :tol)
            ORDER BY dentro DESC,
                     ST_Distance(b.perimetro::geography, p.g::geography),
                     ST_Area(b.perimetro::geography)
            LIMIT 1
            """
        ),
        {"lng": lng, "lat": lat, "tenant_id": tenant_id, "tol": tolerancia_m},
    ).first()
    if fila is None:
        return None
    return BodegaDetectada(
        id=fila.id, cliente_id=fila.cliente_id, nombre_bodega=fila.nombre_bodega, dentro=fila.dentro
    )


def geojson_a_ewkt(geojson: dict) -> str:
    return f"SRID=4326;{shape(geojson).wkt}"


def geom_a_geojson(geom) -> dict:
    return mapping(to_shape(geom))


def punto_a_coordenada(geom) -> dict | None:
    if geom is None:
        return None
    p = to_shape(geom)
    return {"lat": p.y, "lng": p.x}
