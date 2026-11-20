"""fase2_master_identity_suppliers_cost_centers_rbac

Revision ID: a1f2c3d4e5f6
Revises: 3b35c8d26b23
Create Date: 2026-11-18 22:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a1f2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "3b35c8d26b23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabla Maestra de Proveedores vinculada a core.people (Requerimiento A)
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("person_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("rut", sa.String(length=12), nullable=False),
        sa.Column("business_name", sa.String(length=255), nullable=False),
        sa.Column("trade_category", sa.String(length=100), nullable=False, server_default="INSUMOS_CLINICOS"),
        sa.Column("tax_activity", sa.String(length=255), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("bank_account_type", sa.String(length=50), nullable=True),
        sa.Column("bank_account_number", sa.String(length=60), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("default_cost_center_code", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["core.people.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id"),
        sa.UniqueConstraint("rut"),
        schema="core",
    )
    op.create_index("ix_core_suppliers_rut", "suppliers", ["rut"], unique=True, schema="core")
    op.create_index("ix_core_suppliers_person_id", "suppliers", ["person_id"], unique=True, schema="core")

    # 2. Centros de Costo Obligatorios en Cargos Académicos, Pagos, CxP y Remuneraciones/Honorarios (Requerimiento E.6)
    op.add_column("payment_commitments", sa.Column("cost_center_id", sa.String(length=36), nullable=True), schema="finance")
    op.add_column(
        "payment_commitments",
        sa.Column("cost_center", sa.String(length=120), nullable=False, server_default="CC-101 Docencia y Aranceles Escuela San Bao"),
        schema="finance",
    )
    op.add_column("payments", sa.Column("cost_center_id", sa.String(length=36), nullable=True), schema="finance")
    op.add_column(
        "payments",
        sa.Column("cost_center", sa.String(length=120), nullable=False, server_default="CC-101 Docencia y Aranceles Escuela San Bao"),
        schema="finance",
    )
    op.add_column("accounts_payable", sa.Column("cost_center_id", sa.String(length=36), nullable=True), schema="finance")
    op.add_column("hr_fee_receipts", sa.Column("cost_center_id", sa.String(length=36), nullable=True), schema="hr")
    op.add_column(
        "hr_fee_receipts",
        sa.Column("cost_center", sa.String(length=120), nullable=False, server_default="CC-101 Docencia y Aranceles Escuela San Bao"),
        schema="hr",
    )
    op.add_column("hr_payrolls", sa.Column("cost_center_id", sa.String(length=36), nullable=True), schema="hr")
    op.add_column(
        "hr_payrolls",
        sa.Column("cost_center", sa.String(length=120), nullable=False, server_default="CC-101 Docencia y Aranceles Escuela San Bao"),
        schema="hr",
    )


def downgrade() -> None:
    op.drop_column("hr_payrolls", "cost_center", schema="hr")
    op.drop_column("hr_payrolls", "cost_center_id", schema="hr")
    op.drop_column("hr_fee_receipts", "cost_center", schema="hr")
    op.drop_column("hr_fee_receipts", "cost_center_id", schema="hr")
    op.drop_column("accounts_payable", "cost_center_id", schema="finance")
    op.drop_column("payments", "cost_center", schema="finance")
    op.drop_column("payments", "cost_center_id", schema="finance")
    op.drop_column("payment_commitments", "cost_center", schema="finance")
    op.drop_column("payment_commitments", "cost_center_id", schema="finance")
    op.drop_index("ix_core_suppliers_person_id", table_name="suppliers", schema="core")
    op.drop_index("ix_core_suppliers_rut", table_name="suppliers", schema="core")
    op.drop_table("suppliers", schema="core")
