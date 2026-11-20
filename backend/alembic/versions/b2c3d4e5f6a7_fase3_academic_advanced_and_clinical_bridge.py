"""fase3_academic_advanced_and_clinical_bridge

Revision ID: b2c3d4e5f6a7
Revises: a1f2c3d4e5f6
Create Date: 2026-11-18 22:36:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1f2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Nuevas columnas en academic.programs y academic.courses (B.4, B.5, B.8)
    op.add_column("programs", sa.Column("requires_interview", sa.Boolean(), nullable=False, server_default="1"), schema="academic")
    op.add_column("programs", sa.Column("min_attendance_pct", sa.Numeric(5, 2), nullable=False, server_default="75.0"), schema="academic")
    op.add_column("programs", sa.Column("min_passing_grade", sa.Numeric(3, 1), nullable=True, server_default="4.0"), schema="academic")
    op.add_column("programs", sa.Column("requires_grade_for_approval", sa.Boolean(), nullable=False, server_default="1"), schema="academic")
    op.add_column("programs", sa.Column("auto_issue_diploma", sa.Boolean(), nullable=False, server_default="1"), schema="academic")
    op.add_column("programs", sa.Column("practice_max_months", sa.Integer(), nullable=False, server_default="6"), schema="academic")

    op.add_column("courses", sa.Column("min_attendance_pct", sa.Numeric(5, 2), nullable=False, server_default="75.0"), schema="academic")
    op.add_column("courses", sa.Column("min_passing_grade", sa.Numeric(3, 1), nullable=True, server_default="4.0"), schema="academic")
    op.add_column("courses", sa.Column("requires_grade_for_approval", sa.Boolean(), nullable=False, server_default="1"), schema="academic")
    op.add_column("courses", sa.Column("auto_issue_diploma", sa.Boolean(), nullable=False, server_default="0"), schema="academic")

    # 2. Doble cohorte y asignaturas transitorias en academic.cohort_enrollments (B.1)
    op.add_column("cohort_enrollments", sa.Column("enrollment_type", sa.String(40), nullable=False, server_default="REGULAR"), schema="academic")
    op.add_column("cohort_enrollments", sa.Column("valid_from", sa.Date(), nullable=True), schema="academic")
    op.add_column("cohort_enrollments", sa.Column("valid_until", sa.Date(), nullable=True), schema="academic")
    op.add_column("cohort_enrollments", sa.Column("origin_cohort_id", sa.String(36), nullable=True), schema="academic")
    op.add_column("cohort_enrollments", sa.Column("notes", sa.Text(), nullable=True), schema="academic")

    # 3. Trazabilidad de autorizaciones en cambios de curso (B.2) y Decreto 313 en students
    op.add_column("students", sa.Column("decreto_313_coverage_confirmed", sa.Boolean(), nullable=False, server_default="1"), schema="academic")
    op.add_column("student_course_transfers", sa.Column("authorized_by", sa.String(150), nullable=False, server_default="Coordinación Académica - Escuela San Bao"), schema="academic")
    op.add_column("student_course_transfers", sa.Column("authorization_code", sa.String(60), nullable=True), schema="academic")
    op.add_column("student_course_transfers", sa.Column("preserved_history_snapshot", sa.Text(), nullable=True), schema="academic")

    # 4. Puente Clínico-Académico Idempotente y Ajustes Auditables en academic.clinical_practice_hours (C)
    op.add_column("clinical_practice_hours", sa.Column("shift_id", sa.String(36), nullable=True), schema="academic")
    op.add_column("clinical_practice_hours", sa.Column("specialty", sa.String(100), nullable=False, server_default="ACUPUNTURA"), schema="academic")
    op.add_column("clinical_practice_hours", sa.Column("idempotency_key", sa.String(120), nullable=True), schema="academic")
    op.add_column("clinical_practice_hours", sa.Column("record_type", sa.String(40), nullable=False, server_default="ACREDITACION_TURNO"), schema="academic")
    op.add_column("clinical_practice_hours", sa.Column("parent_hour_id", sa.String(36), nullable=True), schema="academic")
    op.add_column("clinical_practice_hours", sa.Column("adjusted_by_user_id", sa.String(36), nullable=True), schema="academic")
    op.add_column("clinical_practice_hours", sa.Column("adjustment_reason", sa.String(255), nullable=True), schema="academic")
    op.add_column("clinical_practice_hours", sa.Column("remuneration_accrued", sa.Boolean(), nullable=False, server_default="1"), schema="academic")
    op.create_index("ix_academic_cph_idempotency_key", "clinical_practice_hours", ["idempotency_key"], unique=True, schema="academic")

    # 5. Tabla academic.academic_incidents (B.3)
    op.create_table(
        "academic_incidents",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("incident_code", sa.String(50), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("cohort_id", sa.String(36), nullable=True),
        sa.Column("course_id", sa.String(36), nullable=True),
        sa.Column("reported_by_id", sa.String(36), nullable=True),
        sa.Column("reported_by_name", sa.String(150), nullable=False),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="ACADEMICA"),
        sa.Column("severity", sa.String(30), nullable=False, server_default="MEDIA"),
        sa.Column("status", sa.String(40), nullable=False, server_default="PENDIENTE_REVISION"),
        sa.Column("reviewed_by_name", sa.String(150), nullable=True),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        sa.Column("moderation_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["academic.students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cohort_id"], ["academic.cohorts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_id"], ["academic.courses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_code"),
        schema="academic",
    )

    # 6. Tablas academic.tutor_student_evaluations y academic.student_tutor_evaluations (B.7)
    op.create_table(
        "tutor_student_evaluations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("tutor_id", sa.String(36), nullable=False),
        sa.Column("period_code", sa.String(30), nullable=False, server_default="2026-2"),
        sa.Column("specialty", sa.String(100), nullable=False, server_default="ACUPUNTURA"),
        sa.Column("clinical_competency_score", sa.Numeric(3, 1), nullable=False),
        sa.Column("anamnesis_quality_score", sa.Numeric(3, 1), nullable=False),
        sa.Column("punctuality_ethics_score", sa.Numeric(3, 1), nullable=False),
        sa.Column("final_score", sa.Numeric(3, 1), nullable=False),
        sa.Column("clinical_reports_required", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("clinical_reports_delivered", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("clinical_reports_compliant", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("report_delivery_notes", sa.Text(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("evaluation_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["academic.students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tutor_id"], ["core.people.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="academic",
    )

    op.create_table(
        "student_tutor_evaluations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("tutor_id", sa.String(36), nullable=False),
        sa.Column("period_code", sa.String(30), nullable=False, server_default="2026-2"),
        sa.Column("pedagogical_clarity_score", sa.Numeric(3, 1), nullable=False),
        sa.Column("supervision_support_score", sa.Numeric(3, 1), nullable=False),
        sa.Column("clinical_feedback_score", sa.Numeric(3, 1), nullable=False),
        sa.Column("overall_score", sa.Numeric(3, 1), nullable=False),
        sa.Column("confidential_comments", sa.Text(), nullable=True),
        sa.Column("is_confidential", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("evaluation_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["academic.students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tutor_id"], ["core.people.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "tutor_id", "period_code", name="uq_student_tutor_eval_period"),
        schema="academic",
    )


def downgrade() -> None:
    op.drop_table("student_tutor_evaluations", schema="academic")
    op.drop_table("tutor_student_evaluations", schema="academic")
    op.drop_table("academic_incidents", schema="academic")
    op.drop_index("ix_academic_cph_idempotency_key", table_name="clinical_practice_hours", schema="academic")
    for col in ("remuneration_accrued", "adjustment_reason", "adjusted_by_user_id", "parent_hour_id", "record_type", "idempotency_key", "specialty", "shift_id"):
        op.drop_column("clinical_practice_hours", col, schema="academic")
    for col in ("preserved_history_snapshot", "authorization_code", "authorized_by"):
        op.drop_column("student_course_transfers", col, schema="academic")
    op.drop_column("students", "decreto_313_coverage_confirmed", schema="academic")
    for col in ("notes", "origin_cohort_id", "valid_until", "valid_from", "enrollment_type"):
        op.drop_column("cohort_enrollments", col, schema="academic")
    for col in ("auto_issue_diploma", "requires_grade_for_approval", "min_passing_grade", "min_attendance_pct"):
        op.drop_column("courses", col, schema="academic")
    for col in ("practice_max_months", "auto_issue_diploma", "requires_grade_for_approval", "min_passing_grade", "min_attendance_pct", "requires_interview"):
        op.drop_column("programs", col, schema="academic")
