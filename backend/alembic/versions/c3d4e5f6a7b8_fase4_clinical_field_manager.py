"""fase4_clinical_field_manager

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-18 22:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Columnas de seguimiento, segmentación y consentimientos en clinical.patients (D.1 y D.2)
    op.add_column("patients", sa.Column("last_visit_date", sa.Date(), nullable=True), schema="clinical")
    op.add_column("patients", sa.Column("retention_segment", sa.String(30), nullable=False, server_default="ACTIVO"), schema="clinical")
    op.add_column("patients", sa.Column("comm_consent_whatsapp", sa.Boolean(), nullable=False, server_default="1"), schema="clinical")
    op.add_column("patients", sa.Column("comm_consent_email", sa.Boolean(), nullable=False, server_default="1"), schema="clinical")
    op.add_column("patients", sa.Column("comm_opt_out", sa.Boolean(), nullable=False, server_default="0"), schema="clinical")
    op.add_column("patients", sa.Column("comm_opt_out_at", sa.String(40), nullable=True), schema="clinical")

    # 2. Columnas de recordatorios 48h/24h y modalidad/prestación en clinical.appointments (D.1 y D.5)
    op.add_column("appointments", sa.Column("session_modality", sa.String(40), nullable=False, server_default="SESION_UNICA"), schema="clinical")
    op.add_column("appointments", sa.Column("service_type", sa.String(50), nullable=False, server_default="ACUPUNTURA"), schema="clinical")
    op.add_column("appointments", sa.Column("amount_paid_clp", sa.Numeric(12, 0), nullable=False, server_default="35000"), schema="clinical")
    op.add_column("appointments", sa.Column("confirmed_at", sa.String(40), nullable=True), schema="clinical")
    op.add_column("appointments", sa.Column("reminder_48h_sent", sa.Boolean(), nullable=False, server_default="0"), schema="clinical")
    op.add_column("appointments", sa.Column("reminder_24h_sent", sa.Boolean(), nullable=False, server_default="0"), schema="clinical")
    op.add_column("appointments", sa.Column("cancellation_reason", sa.String(255), nullable=True), schema="clinical")

    # 3. Checklist obligatorio de Cierre Sanitario REAS en clinical.sanitary_closure_logs (D.3)
    op.create_table(
        "sanitary_closure_logs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("shift_id", sa.String(36), nullable=True),
        sa.Column("tutor_id", sa.String(36), nullable=True),
        sa.Column("sharps_disposal_verified", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("complete_needle_removal_verified", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("box_and_stretcher_sanitized", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("moxa_and_equipment_secured", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("all_mandatory_checks_passed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("confirmed_by_user_id", sa.String(36), nullable=False),
        sa.Column("confirmed_by_name", sa.String(150), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["encounter_id"], ["clinical.encounters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shift_id"], ["clinical.clinical_shift_schedules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tutor_id"], ["clinical.practitioners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="clinical",
    )

    # 4. Control de Insumos por Tutor y Sesión en clinical.tutor_supply_consumptions (D.4)
    op.create_table(
        "tutor_supply_consumptions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("tutor_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=True),
        sa.Column("supply_id", sa.String(36), nullable=True),
        sa.Column("supply_code", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("consumption_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"]),
        sa.ForeignKeyConstraint(["tutor_id"], ["clinical.practitioners.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["clinical.patients.id"]),
        sa.ForeignKeyConstraint(["supply_id"], ["clinical.clinical_supplies.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="clinical",
    )

    # 5. Reporte Automático de Cierre Mensual Clínico en clinical.monthly_clinical_closures (D.5)
    op.create_table(
        "monthly_clinical_closures",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("period_code", sa.String(20), nullable=False),
        sa.Column("total_attentions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_collected_clp", sa.Numeric(14, 0), nullable=False, server_default="0"),
        sa.Column("by_modality_json", sa.Text(), nullable=False),
        sa.Column("by_service_type_json", sa.Text(), nullable=False),
        sa.Column("cross_matrix_json", sa.Text(), nullable=False),
        sa.Column("auto_recalculated_day_1", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        schema="clinical",
    )


def downgrade() -> None:
    op.drop_table("monthly_clinical_closures", schema="clinical")
    op.drop_table("tutor_supply_consumptions", schema="clinical")
    op.drop_table("sanitary_closure_logs", schema="clinical")
    for col in ("cancellation_reason", "reminder_24h_sent", "reminder_48h_sent", "confirmed_at", "amount_paid_clp", "service_type", "session_modality"):
        op.drop_column("appointments", col, schema="clinical")
    for col in ("comm_opt_out_at", "comm_opt_out", "comm_consent_email", "comm_consent_whatsapp", "retention_segment", "last_visit_date"):
        op.drop_column("patients", col, schema="clinical")
