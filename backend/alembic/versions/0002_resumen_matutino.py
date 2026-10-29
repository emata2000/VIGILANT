"""Resumen matutino de rondines silenciados.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resumenes_enviados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cliente_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("rondines", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("cliente_id", "fecha"),
    )
    bypass = "current_setting('app.bypass_rls', true) = 'on'"
    tenant_actual = "NULLIF(current_setting('app.tenant_id', true), '')::int"
    op.execute("ALTER TABLE resumenes_enviados ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE resumenes_enviados FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY aislamiento_tenant ON resumenes_enviados "
        f"USING ({bypass} OR tenant_id = {tenant_actual})"
    )


def downgrade() -> None:
    op.drop_table("resumenes_enviados")
