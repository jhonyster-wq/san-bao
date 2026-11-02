import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class CostCenter(Base, AuditMixin):
    """
    Catálogo Maestro Normalizado (3NF) de Centros de Costo por Sociedad SpA.
    Elimina la redundancia textual en CxP, Tesorería, Presupuestos y Libro Diario.
    """

    __tablename__ = "cost_centers"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_finance_cost_center_company_code"),
        {"schema": "finance"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True, comment="Ej: CC-DOCENCIA-ESCUELA, CC-TUTORIA-CLINICA")
    name = Column(String(160), nullable=False)
    area_type = Column(String(50), default="ACADEMICO", nullable=False, comment="ACADEMICO, CLINICO, ADMINISTRATIVO, COMERCIAL")
    is_active = Column(Boolean, default=True, nullable=False)

    company = relationship("Company")


class BusinessUnit(Base, AuditMixin):
    """
    Catálogo Maestro Normalizado (3NF) de Unidades de Negocio vinculadas a Sociedad y Sede.
    """

    __tablename__ = "business_units"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_finance_business_unit_company_code"),
        {"schema": "finance"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    campus_id = Column(String(36), ForeignKey("core.campuses.id", ondelete="SET NULL"), nullable=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True, comment="Ej: UN-01, UN-02, UN-03, UN-04")
    name = Column(String(160), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    company = relationship("Company")
    campus = relationship("Campus")


class PaymentCommitment(Base, AuditMixin):
    """
    Compromiso financiero u obligación de pago (ej: Arancel de carrera, matrícula o paquete de sesiones).
    Asociado obligatoriamente a una persona jurídica (SpA) para garantizar estricta separación contable.
    """

    __tablename__ = "payment_commitments"
    __table_args__ = {"schema": "finance"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    person_id = Column(String(36), ForeignKey("core.people.id", ondelete="RESTRICT"), nullable=False, index=True)
    enrollment_id = Column(String(36), ForeignKey("academic.enrollments.id", ondelete="SET NULL"), nullable=True, index=True)
    concept = Column(String(255), nullable=False)
    total_amount = Column(Numeric(12, 0), nullable=False, comment="Monto total en pesos chilenos (CLP)")
    balance = Column(Numeric(12, 0), nullable=False, comment="Saldo pendiente por recaudar")
    installments_count = Column(Integer, default=1, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False, comment="PENDING, PARTIALLY_PAID, PAID, OVERDUE, CANCELLED")

    company = relationship("Company")
    person = relationship("Person")
    installments = relationship("Installment", back_populates="commitment", cascade="all, delete-orphan", order_by="Installment.installment_number")

    def __repr__(self):
        return f"<PaymentCommitment {self.concept}: Total={self.total_amount} Balance={self.balance}>"


class Installment(Base, AuditMixin):
    """Cuota individual pactada con fecha de vencimiento (Normalizada 3NF con restricción única e índice de morosidad)."""

    __tablename__ = "installments"
    __table_args__ = (
        UniqueConstraint("commitment_id", "installment_number", name="uq_installment_commitment_number"),
        Index("ix_installments_status_duedate", "status", "due_date"),
        {"schema": "finance"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    commitment_id = Column(String(36), ForeignKey("finance.payment_commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    installment_number = Column(Integer, nullable=False)
    amount = Column(Numeric(12, 0), nullable=False)
    balance = Column(Numeric(12, 0), nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    status = Column(String(50), default="PENDING", nullable=False, index=True, comment="PENDING, PAID, OVERDUE")
    paid_at = Column(DateTime(timezone=True), nullable=True)

    commitment = relationship("PaymentCommitment", back_populates="installments")
    allocations = relationship("PaymentAllocation", back_populates="installment")

    def __repr__(self):
        return f"<Installment #{self.installment_number} due={self.due_date} amount={self.amount} status={self.status}>"


class Payment(Base, AuditMixin):
    """Registro de recaudación y recepción de fondos."""

    __tablename__ = "payments"
    __table_args__ = {"schema": "finance"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    person_id = Column(String(36), ForeignKey("core.people.id", ondelete="RESTRICT"), nullable=False, index=True)
    payment_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(12, 0), nullable=False)
    payment_method = Column(String(50), default="TRANSFER", nullable=False, comment="TRANSFER, WEBPAY, CASH, CHECK")
    reference_number = Column(String(100), nullable=True, comment="Número de transferencia bancaria o código de autorización")
    notes = Column(Text, nullable=True)
    received_by = Column(String(36), ForeignKey("core.users.id"), nullable=True)

    company = relationship("Company")
    person = relationship("Person")
    allocations = relationship("PaymentAllocation", back_populates="payment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Payment {self.id} amount={self.amount} method={self.payment_method}>"


class PaymentAllocation(Base, AuditMixin):
    """Imputación del pago hacia una cuota específica del compromiso financiero."""

    __tablename__ = "payment_allocations"
    __table_args__ = {"schema": "finance"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String(36), ForeignKey("finance.payments.id", ondelete="CASCADE"), nullable=False, index=True)
    installment_id = Column(String(36), ForeignKey("finance.installments.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_applied = Column(Numeric(12, 0), nullable=False)

    payment = relationship("Payment", back_populates="allocations")
    installment = relationship("Installment", back_populates="allocations")


class CollectionAction(Base, AuditMixin):
    """Bitácora de gestiones de cobranza, avisos de morosidad y compromisos de pago."""

    __tablename__ = "collection_actions"
    __table_args__ = {"schema": "finance"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    person_id = Column(String(36), ForeignKey("core.people.id", ondelete="RESTRICT"), nullable=False, index=True)
    commitment_id = Column(String(36), ForeignKey("finance.payment_commitments.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(50), default="EMAIL", nullable=False, comment="EMAIL, WHATSAPP, PHONE, LETTER, RENEGOTIATION")
    action_type = Column(String(100), default="AVISO_VENCIMIENTO", nullable=False)
    overdue_days = Column(Integer, default=0, nullable=False)
    overdue_amount = Column(Numeric(12, 0), default=0, nullable=False)
    promised_payment_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="SENT", nullable=False, comment="SENT, CONTACTED, PROMISED, RESOLVED")

    company = relationship("Company")
    person = relationship("Person")
    commitment = relationship("PaymentCommitment")


class FinanceLegalDocument(Base, AuditMixin):
    """Contratos educacionales, laborales, convenios y pagarés con firma electrónica."""

    __tablename__ = "legal_documents"
    __table_args__ = {"schema": "finance"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    person_id = Column(String(36), ForeignKey("core.people.id", ondelete="RESTRICT"), nullable=False, index=True)
    commitment_id = Column(String(36), ForeignKey("finance.payment_commitments.id", ondelete="SET NULL"), nullable=True, index=True)
    document_code = Column(String(60), nullable=False, unique=True, index=True)
    document_type = Column(String(60), nullable=False, comment="PAGARE_ARANCEL, CONTRATO_EDUCACIONAL, CONTRATO_LABORAL, CONVENIO_PAGO")
    title = Column(String(255), nullable=False)
    total_amount = Column(Numeric(12, 0), default=0, nullable=False)
    installments_count = Column(Integer, default=1, nullable=False)
    guarantor_name = Column(String(200), nullable=True)
    guarantor_rut = Column(String(30), nullable=True)
    content_text = Column(Text, nullable=False)
    status = Column(String(40), default="PENDING_SIGNATURE", nullable=False, comment="PENDING_SIGNATURE, SIGNED, ANNULLED")
    signature_token = Column(String(128), nullable=True, index=True)
    document_hash = Column(String(64), nullable=True)
    signer_ip = Column(String(45), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)

    company = relationship("Company")
    person = relationship("Person")
    commitment = relationship("PaymentCommitment")


class FinancePayable(Base, AuditMixin):
    """Cuentas por Pagar (CxP): Facturas de proveedores, arriendos, insumos clínicos, Previred, F29 SII y honorarios."""

    __tablename__ = "accounts_payable"
    __table_args__ = {"schema": "finance"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    supplier_rut = Column(String(25), nullable=False, index=True)
    supplier_name = Column(String(255), nullable=False)
    document_type = Column(String(60), default="FACTURA_PROVEEDOR", nullable=False, comment="FACTURA_PROVEEDOR, BOLETA_HONORARIOS, PREVIRED, F29_SII, ARRIENDO, SERVICIOS_BASICOS")
    document_number = Column(String(60), nullable=False)
    category = Column(String(80), default="INSUMOS_CLINICOS", nullable=False)
    cost_center = Column(String(120), default="CC-301 Administración Central Holding", nullable=False)
    business_unit = Column(String(120), default="UN-03 Clínica Acupuntura Providencia", nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(12, 0), default=0, nullable=False)
    paid_amount = Column(Numeric(12, 0), default=0, nullable=False)
    balance = Column(Numeric(12, 0), default=0, nullable=False)
    status = Column(String(40), default="PENDING", nullable=False, comment="PENDING, PARTIAL, PAID, OVERDUE")
    payment_method = Column(String(50), nullable=True)
    paid_at = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    company = relationship("Company")


class FinanceTreasuryMovement(Base, AuditMixin):
    """Libro de Tesorería, Control de Ingresos y Egresos, y Conciliación Bancaria."""

    __tablename__ = "treasury_movements"
    __table_args__ = {"schema": "finance"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    bank_account_name = Column(String(140), nullable=False, index=True)
    movement_date = Column(Date, nullable=False, index=True)
    movement_type = Column(String(20), nullable=False, comment="INGRESO, EGRESO")
    category = Column(String(100), nullable=False)
    cost_center = Column(String(120), nullable=False)
    business_unit = Column(String(120), nullable=False)
    concept = Column(String(255), nullable=False)
    counterparty_name = Column(String(200), nullable=True)
    counterparty_rut = Column(String(30), nullable=True)
    amount = Column(Numeric(12, 0), nullable=False)
    payment_method = Column(String(50), default="TRANSFER", nullable=False)
    reference_number = Column(String(80), nullable=True)
    bank_statement_code = Column(String(80), nullable=True)
    bank_reconciled = Column(Boolean, default=False, nullable=False)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)

    company = relationship("Company")


class FinanceBudgetItem(Base, AuditMixin):
    """Partidas de Presupuesto Anual/Mensual por Sociedad, Centro de Costo y Unidad de Negocio."""

    __tablename__ = "budget_items"
    __table_args__ = {"schema": "finance"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    period_year = Column(Integer, default=2026, nullable=False)
    cost_center = Column(String(120), nullable=False, index=True)
    business_unit = Column(String(120), nullable=False, index=True)
    category = Column(String(120), nullable=False)
    item_name = Column(String(255), nullable=False)
    budget_type = Column(String(20), default="EGRESO", nullable=False, comment="INGRESO, EGRESO")
    budgeted_amount = Column(Numeric(12, 0), default=0, nullable=False)
    executed_amount = Column(Numeric(12, 0), default=0, nullable=False)
    notes = Column(Text, nullable=True)

    company = relationship("Company")


class FinanceJournalEntry(Base, AuditMixin):
    """Libro Diario de Contabilidad General (Asientos Contables Debe = Haber)."""

    __tablename__ = "journal_entries"
    __table_args__ = {"schema": "finance"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    entry_number = Column(String(40), nullable=False, unique=True, index=True)
    entry_date = Column(Date, nullable=False, index=True)
    entry_type = Column(String(30), default="TRASPASO", nullable=False, comment="INGRESO, EGRESO, TRASPASO, APERTURA")
    glosa = Column(String(255), nullable=False)
    account_debit_code = Column(String(30), nullable=False)
    account_debit_name = Column(String(140), nullable=False)
    account_credit_code = Column(String(30), nullable=False)
    account_credit_name = Column(String(140), nullable=False)
    amount = Column(Numeric(12, 0), default=0, nullable=False)
    cost_center = Column(String(120), nullable=False)
    business_unit = Column(String(120), nullable=True)
    reference_doc = Column(String(80), nullable=True)
    status = Column(String(30), default="POSTED", nullable=False, comment="POSTED, DRAFT, REVERSED")

    company = relationship("Company")


