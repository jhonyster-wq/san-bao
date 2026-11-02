"""add_hr_integrations_and_bi_modules

Revision ID: 3b35c8d26b23
Revises: d08a47a11f4e
Create Date: 2026-10-30 15:34:04.828204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3b35c8d26b23'
down_revision: Union[str, Sequence[str], None] = 'd08a47a11f4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # ESQUEMA HR: RECURSOS HUMANOS Y REMUNERACIONES
    # -------------------------------------------------------------------------
    op.create_table(
        'hr_employees',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('employee_number', sa.String(length=50), nullable=False),
        sa.Column('job_title', sa.String(length=100), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=False),
        sa.Column('employee_type', sa.String(length=50), nullable=False),
        sa.Column('hire_date', sa.Date(), nullable=False),
        sa.Column('termination_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['company_id'], ['core.companies.id']),
        sa.ForeignKeyConstraint(['person_id'], ['core.people.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='hr'
    )
    op.create_index(op.f('ix_hr_hr_employees_company_id'), 'hr_employees', ['company_id'], unique=False, schema='hr')
    op.create_index(op.f('ix_hr_hr_employees_person_id'), 'hr_employees', ['person_id'], unique=False, schema='hr')
    op.create_index(op.f('ix_hr_hr_employees_employee_number'), 'hr_employees', ['employee_number'], unique=True, schema='hr')

    op.create_table(
        'hr_contracts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('contract_type', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('base_salary', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('hourly_rate', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('clinical_commission_pct', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.00'),
        sa.Column('weekly_hours', sa.Integer(), nullable=False, server_default='40'),
        sa.Column('afp_name', sa.String(length=50), nullable=True),
        sa.Column('health_system', sa.String(length=50), nullable=True),
        sa.Column('health_quote_pct', sa.Numeric(precision=5, scale=2), nullable=False, server_default='7.00'),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('document_url', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr.hr_employees.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='hr'
    )
    op.create_index(op.f('ix_hr_hr_contracts_employee_id'), 'hr_contracts', ['employee_id'], unique=False, schema='hr')

    op.create_table(
        'hr_leave_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('leave_type', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('days_count', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['hr.hr_employees.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['core.users.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='hr'
    )
    op.create_index(op.f('ix_hr_hr_leave_requests_employee_id'), 'hr_leave_requests', ['employee_id'], unique=False, schema='hr')

    op.create_table(
        'hr_fee_receipts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('receipt_number', sa.String(length=50), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('period_month', sa.Integer(), nullable=False),
        sa.Column('period_year', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('gross_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('retention_rate', sa.Numeric(precision=5, scale=2), nullable=False, server_default='13.75'),
        sa.Column('retention_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('net_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['core.companies.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['hr.hr_employees.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='hr'
    )
    op.create_index(op.f('ix_hr_hr_fee_receipts_company_id'), 'hr_fee_receipts', ['company_id'], unique=False, schema='hr')
    op.create_index(op.f('ix_hr_hr_fee_receipts_employee_id'), 'hr_fee_receipts', ['employee_id'], unique=False, schema='hr')
    op.create_index(op.f('ix_hr_hr_fee_receipts_receipt_number'), 'hr_fee_receipts', ['receipt_number'], unique=False, schema='hr')

    op.create_table(
        'hr_payrolls',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('contract_id', sa.UUID(), nullable=False),
        sa.Column('period_month', sa.Integer(), nullable=False),
        sa.Column('period_year', sa.Integer(), nullable=False),
        sa.Column('worked_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('base_salary', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('legal_gratuity', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('bonuses', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('overtime_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('gross_taxable_salary', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('non_taxable_allowances', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('total_earnings', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('pension_deduction', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('health_deduction', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('unemployment_insurance', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('income_tax', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('other_deductions', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('total_deductions', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('net_salary', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['core.companies.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['hr.hr_employees.id']),
        sa.ForeignKeyConstraint(['contract_id'], ['hr.hr_contracts.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='hr'
    )
    op.create_index(op.f('ix_hr_hr_payrolls_company_id'), 'hr_payrolls', ['company_id'], unique=False, schema='hr')
    op.create_index(op.f('ix_hr_hr_payrolls_employee_id'), 'hr_payrolls', ['employee_id'], unique=False, schema='hr')

    # -------------------------------------------------------------------------
    # ESQUEMA INTEGRATIONS: DTE SII, WEBHOOKS Y FIRMA ELECTRÓNICA
    # -------------------------------------------------------------------------
    op.create_table(
        'dte_documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('dte_type', sa.Integer(), nullable=False),
        sa.Column('folio', sa.Integer(), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('issuer_rut', sa.String(length=20), nullable=False),
        sa.Column('issuer_name', sa.String(length=255), nullable=False),
        sa.Column('receiver_rut', sa.String(length=20), nullable=False),
        sa.Column('receiver_name', sa.String(length=255), nullable=False),
        sa.Column('receiver_address', sa.String(length=255), nullable=True),
        sa.Column('receiver_commune', sa.String(length=100), nullable=True),
        sa.Column('receiver_activity', sa.String(length=255), nullable=True),
        sa.Column('net_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('exempt_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('iva_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('items', sa.JSON(), nullable=False),
        sa.Column('sii_status', sa.String(length=50), nullable=False),
        sa.Column('sii_track_id', sa.String(length=50), nullable=True),
        sa.Column('digital_stamp', sa.Text(), nullable=True),
        sa.Column('pdf_url', sa.String(length=255), nullable=True),
        sa.Column('reference_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['core.companies.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='integrations'
    )
    op.create_index(op.f('ix_integrations_dte_documents_company_id'), 'dte_documents', ['company_id'], unique=False, schema='integrations')
    op.create_index(op.f('ix_integrations_dte_documents_dte_type'), 'dte_documents', ['dte_type'], unique=False, schema='integrations')
    op.create_index(op.f('ix_integrations_dte_documents_folio'), 'dte_documents', ['folio'], unique=False, schema='integrations')

    op.create_table(
        'webhook_endpoints',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('secret', sa.String(length=255), nullable=False),
        sa.Column('subscribed_events', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['core.companies.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='integrations'
    )
    op.create_index(op.f('ix_integrations_webhook_endpoints_company_id'), 'webhook_endpoints', ['company_id'], unique=False, schema='integrations')

    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('endpoint_id', sa.UUID(), nullable=False),
        sa.Column('event_name', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('delivered_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['endpoint_id'], ['integrations.webhook_endpoints.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='integrations'
    )
    op.create_index(op.f('ix_integrations_webhook_deliveries_endpoint_id'), 'webhook_deliveries', ['endpoint_id'], unique=False, schema='integrations')
    op.create_index(op.f('ix_integrations_webhook_deliveries_event_name'), 'webhook_deliveries', ['event_name'], unique=False, schema='integrations')

    op.create_table(
        'digital_signatures',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('document_type', sa.String(length=100), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('signer_person_id', sa.UUID(), nullable=False),
        sa.Column('document_hash', sa.String(length=64), nullable=False),
        sa.Column('signature_token', sa.String(length=128), nullable=False),
        sa.Column('signer_ip', sa.String(length=45), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('signed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['core.companies.id']),
        sa.ForeignKeyConstraint(['signer_person_id'], ['core.people.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('signature_token'),
        schema='integrations'
    )
    op.create_index(op.f('ix_integrations_digital_signatures_company_id'), 'digital_signatures', ['company_id'], unique=False, schema='integrations')
    op.create_index(op.f('ix_integrations_digital_signatures_document_id'), 'digital_signatures', ['document_id'], unique=False, schema='integrations')


def downgrade() -> None:
    op.drop_table('digital_signatures', schema='integrations')
    op.drop_table('webhook_deliveries', schema='integrations')
    op.drop_table('webhook_endpoints', schema='integrations')
    op.drop_table('dte_documents', schema='integrations')
    op.drop_table('hr_payrolls', schema='hr')
    op.drop_table('hr_fee_receipts', schema='hr')
    op.drop_table('hr_leave_requests', schema='hr')
    op.drop_table('hr_contracts', schema='hr')
    op.drop_table('hr_employees', schema='hr')
