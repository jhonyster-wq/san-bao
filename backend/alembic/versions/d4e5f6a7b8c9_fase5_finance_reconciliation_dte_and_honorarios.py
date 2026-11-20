"""fase5_finance_reconciliation_dte_and_honorarios

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-18 23:06:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Excepciones de cobro académico en finance.installments (E.1)
    op.add_column("installments", sa.Column("exemption_type", sa.String(40), nullable=True), schema="finance")
    op.add_column("installments", sa.Column("exemption_reason", sa.String(255), nullable=True), schema="finance")
    op.add_column("installments", sa.Column("exemption_valid_from", sa.Date(), nullable=True), schema="finance")
    op.add_column("installments", sa.Column("exemption_valid_until", sa.Date(), nullable=True), schema="finance")
    op.add_column("installments", sa.Column("exemption_authorized_by", sa.String(150), nullable=True), schema="finance")

    # 2. Reversos en finance.payments y finance.payment_reversals (E.3)
    op.add_column("payments", sa.Column("is_reversed", sa.Boolean(), nullable=False, server_default="0"), schema="finance")
    op.create_table(
        "payment_reversals",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("original_payment_id", sa.String(36), nullable=False),
        sa.Column("reversal_code", sa.String(60), nullable=False),
        sa.Column("reversal_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 0), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("responsible_user", sa.String(150), nullable=False),
        sa.Column("accounting_reference", sa.String(80), nullable=False),
        sa.Column("cost_center", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["original_payment_id"], ["finance.payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reversal_code"),
        schema="finance",
    )

    # 3. Cuentas Bancarias por Sociedad y Órdenes de Compra (E.4, E.5, E.6)
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("account_number", sa.String(60), nullable=False),
        sa.Column("account_name", sa.String(160), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="CLP"),
        sa.Column("current_balance_clp", sa.Numeric(14, 0), nullable=False, server_default="0"),
        sa.Column("overdraft_limit_clp", sa.Numeric(14, 0), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "account_number", name="uq_finance_bank_account_company_number"),
        schema="finance",
    )

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("oc_number", sa.String(60), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("supplier_rut", sa.String(25), nullable=False),
        sa.Column("supplier_name", sa.String(255), nullable=False),
        sa.Column("cost_center_id", sa.String(36), nullable=True),
        sa.Column("cost_center", sa.String(120), nullable=False),
        sa.Column("business_unit", sa.String(120), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("concept", sa.String(255), nullable=False),
        sa.Column("total_amount_clp", sa.Numeric(12, 0), nullable=False),
        sa.Column("committed_amount_clp", sa.Numeric(12, 0), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="APPROVED_COMMITTED"),
        sa.Column("approved_by", sa.String(150), nullable=False),
        sa.Column("overdraft_alert", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("overdraft_alert_detail", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cost_center_id"], ["finance.cost_centers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("oc_number"),
        schema="finance",
    )
    op.add_column("accounts_payable", sa.Column("purchase_order_id", sa.String(36), nullable=True), schema="finance")

    # 4. Conciliación Bancaria de Tres Vías (F)
    op.create_table(
        "bank_statement_lines",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("bank_account_name", sa.String(140), nullable=False),
        sa.Column("statement_line_code", sa.String(80), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount_clp", sa.Numeric(12, 0), nullable=False),
        sa.Column("movement_nature", sa.String(40), nullable=False, server_default="ABONO"),
        sa.Column("is_reconciled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciliation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "statement_line_code", name="uq_bank_statement_line_company_code"),
        schema="finance",
    )

    op.create_table(
        "three_way_reconciliations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("statement_line_id", sa.String(36), nullable=False),
        sa.Column("payment_id", sa.String(36), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("match_status", sa.String(40), nullable=False, server_default="MATCHED_3_WAY"),
        sa.Column("discrepancy_type", sa.String(60), nullable=True),
        sa.Column("discrepancy_amount_clp", sa.Numeric(12, 0), nullable=False, server_default="0"),
        sa.Column("assigned_reviewer", sa.String(150), nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False, server_default="AUTO_RECONCILED"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["statement_line_id"], ["finance.bank_statement_lines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["finance.payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["finance.journal_entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("statement_line_id"),
        schema="finance",
    )

    # 5. Clasificaciones Tributarias y Control de DTE SII (G)
    op.create_table(
        "tax_classifications",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("operation_type", sa.String(60), nullable=False),
        sa.Column("dte_type_default", sa.Integer(), nullable=False, server_default="41"),
        sa.Column("tax_regime", sa.String(40), nullable=False, server_default="EXENTO_IVA"),
        sa.Column("iva_rate_pct", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("sii_legal_reference", sa.String(200), nullable=False),
        sa.Column("validated_by_finance", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("validated_by_user", sa.String(150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "operation_type", name="uq_tax_classification_company_op"),
        schema="finance",
    )

    op.add_column("dte_documents", sa.Column("source_operation_key", sa.String(120), nullable=True), schema="integrations")
    op.add_column("dte_documents", sa.Column("tax_classification_code", sa.String(60), nullable=True), schema="integrations")
    op.add_column("dte_documents", sa.Column("contingency_mode", sa.Boolean(), nullable=False, server_default="0"), schema="integrations")
    op.add_column("dte_documents", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"), schema="integrations")
    op.add_column("dte_documents", sa.Column("rejection_reason", sa.String(255), nullable=True), schema="integrations")
    op.add_column("dte_documents", sa.Column("related_dte_id", sa.String(36), nullable=True), schema="integrations")

    # 6. Tasas de Retención de Honorarios por Período según Ley 21.133 (H)
    op.add_column("hr_fee_receipts", sa.Column("academic_hours", sa.Numeric(6, 2), nullable=False, server_default="0.00"), schema="hr")
    op.add_column("hr_fee_receipts", sa.Column("clinical_hours", sa.Numeric(6, 2), nullable=False, server_default="0.00"), schema="hr")
    op.add_column("hr_fee_receipts", sa.Column("hourly_rate", sa.Numeric(12, 2), nullable=False, server_default="0.00"), schema="hr")
    op.create_table(
        "tax_retention_rates",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("retention_rate_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("legal_reference", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_year"),
        schema="hr",
    )


def downgrade() -> None:
    op.drop_table("tax_retention_rates", schema="hr")
    for col in ("hourly_rate", "clinical_hours", "academic_hours"):
        op.drop_column("hr_fee_receipts", col, schema="hr")
    for col in ("related_dte_id", "rejection_reason", "retry_count", "contingency_mode", "tax_classification_code", "source_operation_key"):
        op.drop_column("dte_documents", col, schema="integrations")
    op.drop_table("tax_classifications", schema="finance")
    op.drop_table("three_way_reconciliations", schema="finance")
    op.drop_table("bank_statement_lines", schema="finance")
    op.drop_column("accounts_payable", "purchase_order_id", schema="finance")
    op.drop_table("purchase_orders", schema="finance")
    op.drop_table("bank_accounts", schema="finance")
    op.drop_table("payment_reversals", schema="finance")
    op.drop_column("payments", "is_reversed", schema="finance")
    for col in ("exemption_authorized_by", "exemption_valid_until", "exemption_valid_from", "exemption_reason", "exemption_type"):
        op.drop_column("installments", col, schema="finance")
