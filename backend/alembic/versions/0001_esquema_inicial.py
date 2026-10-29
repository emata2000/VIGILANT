"""Esquema inicial: tablas del PRD corregidas y Row-Level Security por tenant.

Revision ID: 0001
Revises:
Create Date: 2026-10-29 19:52:59.177252

"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa

from alembic import op
from app.models import TABLAS_TENANT

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("nombre_comercial", sa.String(length=150), nullable=False),
        sa.Column(
            "token_identificador",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "zona_horaria",
            sa.String(length=50),
            server_default="America/Mexico_City",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('active', 'suspended', 'trial')"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("token_identificador"),
    )
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("telefono_whatsapp", sa.String(length=20), nullable=True),
        sa.Column("rol", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rol = 'SUPER_ADMIN' OR tenant_id IS NOT NULL", name="tenant_requerido"),
        sa.CheckConstraint("rol IN ('SUPER_ADMIN', 'ADMINISTRADOR', 'DUENO_NAVE', 'GUARDIA')"),
        sa.CheckConstraint(
            "telefono_whatsapp IS NULL OR telefono_whatsapp ~ '^\\+[1-9][0-9]{7,14}$'",
            name="telefono_e164",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email"),
    )
    op.create_table(
        "bodegas_geocercas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("nombre_bodega", sa.String(length=100), nullable=False),
        sa.Column("num_bodega", sa.String(length=30), nullable=True),
        sa.Column(
            "perimetro",
            geoalchemy2.types.Geometry(
                geometry_type="POLYGON",
                srid=4326,
                dimension=2,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ST_IsValid(perimetro)", name="perimetro_valido"),
        sa.ForeignKeyConstraint(["cliente_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "configuracion_alertas",
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("recibir_rutina_whatsapp", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("recibir_rutina_push", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "recibir_emergencia_whatsapp", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("recibir_emergencia_push", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("modo_mute_activo", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("mute_inicio_hora", sa.Time(), server_default="22:00:00", nullable=False),
        sa.Column("mute_fin_hora", sa.Time(), server_default="06:00:00", nullable=False),
        sa.ForeignKeyConstraint(["cliente_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("cliente_id"),
    )
    op.create_table(
        "dispositivos_push",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("fcm_token", sa.String(length=255), nullable=False),
        sa.Column("plataforma", sa.String(length=20), server_default="android", nullable=False),
        sa.Column(
            "ultimo_uso",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fcm_token"),
    )
    op.create_table(
        "puntos_control",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("bodega_id", sa.Integer(), nullable=True),
        sa.Column("codigo_uid", sa.String(length=100), nullable=False),
        sa.Column("nombre_punto", sa.String(length=100), nullable=False),
        sa.Column(
            "coordenada_esperada",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("tolerancia_metros", sa.Integer(), server_default="15", nullable=False),
        sa.ForeignKeyConstraint(["bodega_id"], ["bodegas_geocercas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "codigo_uid"),
    )
    op.create_table(
        "reportes_guardias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("guardia_id", sa.Integer(), nullable=True),
        sa.Column("uuid_cliente", sa.UUID(), nullable=False),
        sa.Column("tipo_evento", sa.String(length=30), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("punto_control_id", sa.Integer(), nullable=True),
        sa.Column(
            "ubicacion_real",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column("precision_metros", sa.Float(), nullable=True),
        sa.Column("bodega_detectada_id", sa.Integer(), nullable=True),
        sa.Column("timestamp_campo", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recibido_el",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "estado_notificacion", sa.String(length=20), server_default="PENDIENTE", nullable=False
        ),
        sa.CheckConstraint(
            "estado_notificacion IN ('PENDIENTE', 'ENVIADO', 'SILENCIADO', 'TARDIO', 'SIN_DESTINATARIO')"
        ),
        sa.CheckConstraint("tipo_evento IN ('RUTINA_PASO', 'ALERTA_EMERGENCIA')"),
        sa.ForeignKeyConstraint(
            ["bodega_detectada_id"], ["bodegas_geocercas.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["guardia_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["punto_control_id"], ["puntos_control.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid_cliente"),
    )
    op.create_table(
        "notificaciones_enviadas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("reporte_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("canal", sa.String(length=20), nullable=False),
        sa.Column("plantilla", sa.String(length=60), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("canal IN ('PUSH', 'WHATSAPP')"),
        sa.CheckConstraint("estado IN ('ENVIADO', 'FALLIDO')"),
        sa.ForeignKeyConstraint(["reporte_id"], ["reportes_guardias.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reporte_id", "usuario_id", "canal"),
    )
    op.create_table(
        "reporte_multimedia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("reporte_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=20), server_default="foto", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["reporte_id"], ["reportes_guardias.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reporte_multimedia_reporte_id"), "reporte_multimedia", ["reporte_id"], unique=False
    )
    op.create_index(
        "ix_reportes_tenant_timestamp",
        "reportes_guardias",
        ["tenant_id", sa.text("timestamp_campo DESC")],
    )
    op.create_index("ix_geocercas_tenant", "bodegas_geocercas", ["tenant_id"])

    # Row-Level Security: cada consulta solo ve filas del tenant fijado en app.tenant_id.
    # FORCE aplica las políticas también al dueño de las tablas (el rol de la app).
    # app.bypass_rls='on' solo lo activa el backend para login y SUPER_ADMIN.
    bypass = "current_setting('app.bypass_rls', true) = 'on'"
    tenant_actual = "NULLIF(current_setting('app.tenant_id', true), '')::int"
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY aislamiento_tenant ON tenants USING ({bypass} OR id = {tenant_actual})"
    )
    for tabla in TABLAS_TENANT:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY aislamiento_tenant ON {tabla} "
            f"USING ({bypass} OR tenant_id = {tenant_actual})"
        )


def downgrade() -> None:
    op.drop_index("ix_geocercas_tenant", table_name="bodegas_geocercas")
    op.drop_index("ix_reportes_tenant_timestamp", table_name="reportes_guardias")
    op.drop_index(op.f("ix_reporte_multimedia_reporte_id"), table_name="reporte_multimedia")
    op.drop_table("reporte_multimedia")
    op.drop_table("notificaciones_enviadas")
    op.drop_table("reportes_guardias")
    op.drop_table("puntos_control")
    op.drop_table("dispositivos_push")
    op.drop_table("configuracion_alertas")
    op.drop_table("bodegas_geocercas")
    op.drop_table("usuarios")
    op.drop_table("tenants")
