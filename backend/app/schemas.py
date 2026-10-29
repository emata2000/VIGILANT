"""Payloads JSON entre la app, el panel y la API. Son el contrato que publica OpenAPI (/docs)."""

import uuid
from datetime import datetime, time
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator

Rol = Literal["SUPER_ADMIN", "ADMINISTRADOR", "DUENO_NAVE", "GUARDIA"]
TipoEvento = Literal["RUTINA_PASO", "ALERTA_EMERGENCIA"]
Lat = Annotated[float, Field(ge=-90, le=90)]
Lng = Annotated[float, Field(ge=-180, le=180)]


# ---------- Autenticación ----------


class LoginIn(BaseModel):
    tenant: str | None = Field(
        None, description="Slug del tenant (ej. 'parque-norte'). Vacío solo para SUPER_ADMIN."
    )
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    usuario_id: int
    tenant_id: int | None
    rol: Rol
    zona_horaria: str | None


# ---------- Tenants y usuarios ----------


class TenantIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$")
    nombre_comercial: str = Field(max_length=150)
    zona_horaria: str = Field("America/Mexico_City", description="Nombre IANA de la zona horaria")
    status: Literal["active", "suspended", "trial"] = "trial"

    @field_validator("zona_horaria")
    @classmethod
    def _zona_valida(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"Zona horaria desconocida: {v}") from e
        return v


class TenantOut(TenantIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    token_identificador: uuid.UUID


class UsuarioIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    nombre: str = Field(max_length=100)
    telefono_whatsapp: str | None = Field(None, pattern=r"^\+[1-9][0-9]{7,14}$")
    rol: Literal["ADMINISTRADOR", "DUENO_NAVE", "GUARDIA"]
    tenant_id: int | None = Field(
        None, description="Solo SUPER_ADMIN lo indica; los demás crean en su propio tenant."
    )


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int | None
    email: str
    nombre: str
    telefono_whatsapp: str | None
    rol: Rol
    status: str


class UsuarioCambios(BaseModel):
    """Campos que el administrador puede cambiar. Los omitidos quedan igual."""

    nombre: str | None = Field(None, max_length=100)
    telefono_whatsapp: str | None = Field(None, pattern=r"^\+[1-9][0-9]{7,14}$")
    status: Literal["active", "inactive"] | None = None
    password: str | None = Field(None, min_length=8)


class DispositivoIn(BaseModel):
    fcm_token: str = Field(max_length=255)
    plataforma: Literal["android", "ios", "web"] = "android"


# ---------- Geocercas y puntos de control ----------


class PoligonoGeoJSON(BaseModel):
    """Polígono GeoJSON. Coordenadas en orden [lng, lat] (estándar GeoJSON, SRID 4326)."""

    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[tuple[Lng, Lat]]] = Field(min_length=1)

    @field_validator("coordinates")
    @classmethod
    def _anillo_cerrado(cls, v: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
        for anillo in v:
            if len(anillo) < 4 or anillo[0] != anillo[-1]:
                raise ValueError("Cada anillo necesita 4 o más puntos y debe cerrar en el primero")
        return v


class GeocercaIn(BaseModel):
    nombre_bodega: str = Field(max_length=100)
    num_bodega: str | None = Field(None, max_length=30)
    cliente_id: int | None = None
    perimetro: PoligonoGeoJSON


class GeocercaOut(GeocercaIn):
    id: int
    tenant_id: int


class Coordenada(BaseModel):
    lat: Lat
    lng: Lng


class PuntoControlIn(BaseModel):
    codigo_uid: str = Field(max_length=100, description="UID del chip NFC o contenido del QR")
    nombre_punto: str = Field(max_length=100)
    bodega_id: int | None = None
    coordenada_esperada: Coordenada
    tolerancia_metros: int = Field(15, ge=1, le=500)


class PuntoControlOut(PuntoControlIn):
    id: int


# ---------- Reportes de campo (app del guardia) ----------


class UbicacionIn(BaseModel):
    lat: Lat
    lng: Lng
    precision_metros: float | None = Field(None, ge=0)


class MultimediaIn(BaseModel):
    storage_key: str = Field(max_length=255, description="Llave devuelta por /v1/multimedia/url")
    tipo: Literal["foto", "video", "audio"] = "foto"


class ReporteIn(BaseModel):
    uuid_cliente: uuid.UUID = Field(
        description="UUID que genera la app al crear el reporte. Reenviarlo no duplica el reporte."
    )
    tipo_evento: TipoEvento
    timestamp_campo: AwareDatetime = Field(
        description="Momento real del evento en campo, ISO 8601 con zona horaria."
    )
    ubicacion: UbicacionIn | None = Field(None, description="Nulo si el GPS no obtuvo posición")
    descripcion: str | None = Field(None, max_length=4000)
    codigo_punto_control: str | None = Field(None, description="UID NFC o QR escaneado")
    multimedia: list[MultimediaIn] = Field(default_factory=list, max_length=10)


class MultimediaOut(BaseModel):
    tipo: str
    url: str = Field(description="URL temporal de lectura (prefirmada)")


class ReporteOut(BaseModel):
    id: int
    uuid_cliente: uuid.UUID
    tipo_evento: TipoEvento
    timestamp_campo: datetime
    recibido_el: datetime
    guardia_id: int | None
    ubicacion: Coordenada | None
    precision_metros: float | None
    bodega_detectada_id: int | None
    punto_control_id: int | None
    estado_notificacion: str
    descripcion: str | None
    guardia_nombre: str | None = None
    multimedia: list[MultimediaOut] = Field(default_factory=list)
    duplicado: bool = Field(False, description="True si el reporte ya existía (reenvío)")


class LoteIn(BaseModel):
    reportes: list[ReporteIn] = Field(min_length=1, max_length=100)


class ResultadoLote(BaseModel):
    uuid_cliente: uuid.UUID
    ok: bool
    reporte_id: int | None = None
    duplicado: bool = False
    error: str | None = None


class LoteOut(BaseModel):
    resultados: list[ResultadoLote]


class UrlSubidaIn(BaseModel):
    content_type: Literal["image/jpeg", "image/png", "image/webp", "video/mp4", "audio/mp4"]


class UrlSubidaOut(BaseModel):
    storage_key: str
    url: str
    metodo: Literal["PUT"] = "PUT"
    expira_en_segundos: int


# ---------- Preferencias de alertas (dueño de nave) ----------


class ConfigAlertasIO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recibir_rutina_whatsapp: bool = False
    recibir_rutina_push: bool = True
    recibir_emergencia_whatsapp: bool = True
    recibir_emergencia_push: bool = True
    modo_mute_activo: bool = False
    mute_inicio_hora: time = time(22, 0)
    mute_fin_hora: time = time(6, 0)
