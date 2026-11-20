"""fase8_bi_kpis_aes256_and_15y_retention

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-18 23:33:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Cifrado AES-256 de campos clínicos sensibles y conservación legal por 15 años en clinical.encounters (Requerimiento M)
    op.add_column("encounters", sa.Column("encrypted_sensitive_payload", sa.Text(), nullable=True), schema="clinical")
    op.add_column("encounters", sa.Column("retention_until_date", sa.Date(), nullable=True), schema="clinical")

    # 2. Tabla de Gestión de Incidentes de Seguridad en audit.security_incidents (Requerimiento M)
    op.create_table(
        "security_incidents",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("incident_code", sa.String(50), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=True),
        sa.Column("reported_by_user_id", sa.String(36), nullable=True),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False, server_default="ALTA"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mitigation_action", sa.Text(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="OPEN_INVESTIGATING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_code"),
        schema="audit",
    )


def downgrade() -> None:
    op.drop_table("security_incidents", schema="audit")
    op.drop_column("encounters", "retention_until_date", schema="clinical")
    op.drop_column("encounters", "encrypted_sensitive_payload", schema="clinical")
