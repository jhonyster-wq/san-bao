"""fase7_transactional_integration_bus_and_transversal_blocking

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-18 23:23:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extensión de integrations.operation_logs para Idempotencia, Backoff Exponencial y DLQ (Requerimiento J)
    op.add_column("operation_logs", sa.Column("idempotency_key", sa.String(120), nullable=True), schema="integrations")
    op.add_column("operation_logs", sa.Column("backoff_seconds", sa.Integer(), nullable=False, server_default="0"), schema="integrations")
    op.add_column("operation_logs", sa.Column("next_retry_at", sa.String(40), nullable=True), schema="integrations")
    op.add_column("operation_logs", sa.Column("dead_letter_queued", sa.Boolean(), nullable=False, server_default="0"), schema="integrations")
    op.add_column("operation_logs", sa.Column("error_alert_sent", sa.Boolean(), nullable=False, server_default="0"), schema="integrations")
    op.add_column("operation_logs", sa.Column("payload_json", sa.Text(), nullable=True), schema="integrations")
    op.create_index("ix_integrations_op_logs_idempotency_key", "operation_logs", ["idempotency_key"], unique=True, schema="integrations")

    # 2. Tablas del Motor de Bloqueo Transversal con Continuidad Clínica (Requerimiento K)
    op.create_table(
        "transversal_restriction_rules",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("rule_code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("trigger_condition", sa.String(80), nullable=False),
        sa.Column("min_overdue_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("restricted_scopes_json", sa.Text(), nullable=False),
        sa.Column("preserve_clinical_patient_continuity", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("auto_rehabilitate_on_payment", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_code"),
        schema="integrations",
    )

    op.create_table(
        "transversal_restrictions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=True),
        sa.Column("rule_code", sa.String(60), nullable=False),
        sa.Column("origin_condition", sa.String(200), nullable=False),
        sa.Column("restricted_scopes_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("applied_by", sa.String(150), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("exception_authorized_by", sa.String(150), nullable=True),
        sa.Column("exception_reason", sa.String(255), nullable=True),
        sa.Column("exception_valid_from", sa.Date(), nullable=True),
        sa.Column("exception_valid_until", sa.Date(), nullable=True),
        sa.Column("rehabilitated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rehabilitated_by", sa.String(150), nullable=True),
        sa.Column("rehabilitation_reason", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["core.people.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="integrations",
    )


def downgrade() -> None:
    op.drop_table("transversal_restrictions", schema="integrations")
    op.drop_table("transversal_restriction_rules", schema="integrations")
    op.drop_index("ix_integrations_op_logs_idempotency_key", table_name="operation_logs", schema="integrations")
    for col in ("payload_json", "error_alert_sent", "dead_letter_queued", "next_retry_at", "backoff_seconds", "idempotency_key"):
        op.drop_column("operation_logs", col, schema="integrations")
