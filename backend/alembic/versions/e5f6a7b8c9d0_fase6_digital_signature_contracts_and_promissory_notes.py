"""fase6_digital_signature_contracts_and_promissory_notes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-18 23:18:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extensión de finance.legal_documents para Firma Digital Transversal (Requerimiento I)
    op.add_column("legal_documents", sa.Column("onboarding_id", sa.String(36), nullable=True), schema="finance")
    op.add_column("legal_documents", sa.Column("is_mandatory_for_enrollment", sa.Boolean(), nullable=False, server_default="1"), schema="finance")
    op.add_column("legal_documents", sa.Column("provider_name", sa.String(80), nullable=False, server_default="GENERIC_REST_ESIGN_PROVIDER"), schema="finance")
    op.add_column("legal_documents", sa.Column("provider_envelope_id", sa.String(120), nullable=True), schema="finance")
    op.add_column("legal_documents", sa.Column("signer_rut", sa.String(20), nullable=True), schema="finance")
    op.add_column("legal_documents", sa.Column("signer_name", sa.String(200), nullable=True), schema="finance")
    op.add_column("legal_documents", sa.Column("timestamp_seal", sa.String(140), nullable=True), schema="finance")
    op.add_column("legal_documents", sa.Column("signature_evidence_json", sa.Text(), nullable=True), schema="finance")
    op.add_column("legal_documents", sa.Column("events_history_json", sa.Text(), nullable=True), schema="finance")
    op.add_column("legal_documents", sa.Column("archived_document_uri", sa.String(500), nullable=True), schema="finance")

    # 2. Vínculo de Pagaré y Estado de Regularización en academic.student_onboardings (Requerimiento I)
    op.add_column("student_onboardings", sa.Column("promissory_note_document_id", sa.String(36), nullable=True), schema="academic")
    op.add_column("student_onboardings", sa.Column("promissory_note_code", sa.String(60), nullable=True), schema="academic")
    op.add_column("student_onboardings", sa.Column("enrollment_regularized", sa.Boolean(), nullable=False, server_default="0"), schema="academic")


def downgrade() -> None:
    for col in ("enrollment_regularized", "promissory_note_code", "promissory_note_document_id"):
        op.drop_column("student_onboardings", col, schema="academic")
    for col in (
        "archived_document_uri",
        "events_history_json",
        "signature_evidence_json",
        "timestamp_seal",
        "signer_name",
        "signer_rut",
        "provider_envelope_id",
        "provider_name",
        "is_mandatory_for_enrollment",
        "onboarding_id",
    ):
        op.drop_column("legal_documents", col, schema="finance")
