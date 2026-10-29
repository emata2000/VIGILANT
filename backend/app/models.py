import uuid
from datetime import datetime, time

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROLES = ("SUPER_ADMIN", "ADMINISTRADOR", "DUENO_NAVE", "GUARDIA")
TIPOS_EVENTO = ("RUTINA_PASO", "ALERTA_EMERGENCIA")
# Estado del reporte respecto a las notificaciones en tiempo real.
ESTADOS_NOTIFICACION = (
    "PENDIENTE",  # aún no lo procesa el motor de alertas
    "ENVIADO",  # se notificó al menos a un destinatario
    "SILENCIADO",  # rutina dentro del horario de mute: queda para el resumen matutino
    "TARDIO",  # rutina que llegó demasiado tarde para notificarse en tiempo real
    "SIN_DESTINATARIO",  # no hay a quién avisar (área común, bodega sin cliente, canales apagados)
)


def _en(nombre: str, valores: tuple[str, ...]) -> str:
    lista = ", ".join(f"'{v}'" for v in valores)
    return f"{nombre} IN ({lista})"


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    nombre_comercial: Mapped[str] = mapped_column(String(150))
    token_identificador: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, server_default=text("gen_random_uuid()")
    )
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    zona_horaria: Mapped[str] = mapped_column(String(50), server_default="America/Mexico_City")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint(_en("status", ("active", "suspended", "trial"))),)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    nombre: Mapped[str] = mapped_column(String(100))
    telefono_whatsapp: Mapped[str | None] = mapped_column(String(20))
    rol: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "email"),
        CheckConstraint(_en("rol", ROLES)),
        CheckConstraint("rol = 'SUPER_ADMIN' OR tenant_id IS NOT NULL", name="tenant_requerido"),
        CheckConstraint(
            "telefono_whatsapp IS NULL OR telefono_whatsapp ~ '^\\+[1-9][0-9]{7,14}$'",
            name="telefono_e164",
        ),
    )


class DispositivoPush(Base):
    """Un usuario puede tener varios teléfonos; cada uno con su token de Firebase."""

    __tablename__ = "dispositivos_push"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    fcm_token: Mapped[str] = mapped_column(String(255), unique=True)
    plataforma: Mapped[str] = mapped_column(String(20), server_default="android")
    ultimo_uso: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BodegaGeocerca(Base):
    __tablename__ = "bodegas_geocercas"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    nombre_bodega: Mapped[str] = mapped_column(String(100))
    num_bodega: Mapped[str | None] = mapped_column(String(30))
    perimetro = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("ST_IsValid(perimetro)", name="perimetro_valido"),)


class PuntoControl(Base):
    __tablename__ = "puntos_control"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    # Nulo cuando el checkpoint está en un área común, fuera de toda bodega.
    bodega_id: Mapped[int | None] = mapped_column(
        ForeignKey("bodegas_geocercas.id", ondelete="CASCADE")
    )
    codigo_uid: Mapped[str] = mapped_column(String(100))
    nombre_punto: Mapped[str] = mapped_column(String(100))
    coordenada_esperada = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=False
    )
    tolerancia_metros: Mapped[int] = mapped_column(Integer, server_default="15")

    __table_args__ = (UniqueConstraint("tenant_id", "codigo_uid"),)


class ConfiguracionAlertas(Base):
    __tablename__ = "configuracion_alertas"

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    recibir_rutina_whatsapp: Mapped[bool] = mapped_column(Boolean, server_default="false")
    recibir_rutina_push: Mapped[bool] = mapped_column(Boolean, server_default="true")
    recibir_emergencia_whatsapp: Mapped[bool] = mapped_column(Boolean, server_default="true")
    recibir_emergencia_push: Mapped[bool] = mapped_column(Boolean, server_default="true")
    modo_mute_activo: Mapped[bool] = mapped_column(Boolean, server_default="false")
    mute_inicio_hora: Mapped[time] = mapped_column(Time, server_default="22:00:00")
    mute_fin_hora: Mapped[time] = mapped_column(Time, server_default="06:00:00")


class ReporteGuardia(Base):
    __tablename__ = "reportes_guardias"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    guardia_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Generado por la app al crear el reporte: hace idempotentes los reintentos offline.
    uuid_cliente: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True)
    tipo_evento: Mapped[str] = mapped_column(String(30))
    descripcion: Mapped[str | None] = mapped_column(Text)
    punto_control_id: Mapped[int | None] = mapped_column(
        ForeignKey("puntos_control.id", ondelete="SET NULL")
    )
    # Puede ser nulo: bajo techos metálicos el GPS a veces no obtiene posición.
    ubicacion_real = mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=True)
    precision_metros: Mapped[float | None] = mapped_column(Float)
    bodega_detectada_id: Mapped[int | None] = mapped_column(
        ForeignKey("bodegas_geocercas.id", ondelete="SET NULL")
    )
    # Cuándo ocurrió en campo (reloj del teléfono) vs. cuándo llegó al servidor.
    timestamp_campo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recibido_el: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    estado_notificacion: Mapped[str] = mapped_column(String(20), server_default="PENDIENTE")

    __table_args__ = (
        CheckConstraint(_en("tipo_evento", TIPOS_EVENTO)),
        CheckConstraint(_en("estado_notificacion", ESTADOS_NOTIFICACION)),
    )


class ReporteMultimedia(Base):
    __tablename__ = "reporte_multimedia"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    reporte_id: Mapped[int] = mapped_column(
        ForeignKey("reportes_guardias.id", ondelete="CASCADE"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(20), server_default="foto")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificacionEnviada(Base):
    """Registro de cada envío. La restricción única evita duplicados si la cola reintenta."""

    __tablename__ = "notificaciones_enviadas"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    reporte_id: Mapped[int] = mapped_column(ForeignKey("reportes_guardias.id", ondelete="CASCADE"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    canal: Mapped[str] = mapped_column(String(20))
    plantilla: Mapped[str] = mapped_column(String(60))
    estado: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("reporte_id", "usuario_id", "canal"),
        CheckConstraint(_en("canal", ("PUSH", "WHATSAPP"))),
        CheckConstraint(_en("estado", ("ENVIADO", "FALLIDO"))),
    )


# Tablas con RLS por tenant_id (tenants usa su propio id).
TABLAS_TENANT = (
    "usuarios",
    "dispositivos_push",
    "bodegas_geocercas",
    "puntos_control",
    "configuracion_alertas",
    "reportes_guardias",
    "reporte_multimedia",
    "notificaciones_enviadas",
)
