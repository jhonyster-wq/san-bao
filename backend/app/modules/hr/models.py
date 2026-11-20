import uuid
import enum
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Date,
    Numeric,
    Integer,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class EmployeeType(str, enum.Enum):
    TEACHER = "TEACHER"
    PRACTITIONER = "PRACTITIONER"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    EXECUTIVE = "EXECUTIVE"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ON_LEAVE = "ON_LEAVE"
    TERMINATED = "TERMINATED"


class ContractType(str, enum.Enum):
    INDEFINITE = "INDEFINITE"
    FIXED_TERM = "FIXED_TERM"
    FEE_HONORARIOS = "FEE_HONORARIOS"
    PRACTICE = "PRACTICE"


class ContractStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"


class LeaveType(str, enum.Enum):
    VACATION = "VACATION"
    MEDICAL_LEAVE = "MEDICAL_LEAVE"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    UNPAID = "UNPAID"


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class FeeReceiptStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PAID = "PAID"
    ANNULLED = "ANNULLED"


class PayrollStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PAID = "PAID"


class HREmployee(Base):
    """Colaborador o funcionario institucional (Docente, Terapeuta, Administrativo)."""
    __tablename__ = "hr_employees"
    __table_args__ = (
        UniqueConstraint("company_id", "person_id", name="uq_hr_employee_company_person"),
        Index("ix_hr_employees_comp_type_active", "company_id", "employee_type", "is_active"),
        {"schema": "hr"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    person_id = Column(String(36), ForeignKey("core.people.id"), nullable=False, index=True)
    employee_number = Column(String(50), nullable=False, unique=True, index=True)
    job_title = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    employee_type = Column(Enum(EmployeeType), nullable=False, index=True)
    hire_date = Column(Date, nullable=False)
    termination_date = Column(Date, nullable=True)
    status = Column(Enum(EmployeeStatus), default=EmployeeStatus.ACTIVE, nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relaciones
    person = relationship("Person", lazy="joined")
    contracts = relationship("HRContract", back_populates="employee", cascade="all, delete-orphan")
    leave_requests = relationship("HRLeaveRequest", back_populates="employee", cascade="all, delete-orphan")
    fee_receipts = relationship("HRFeeReceipt", back_populates="employee", cascade="all, delete-orphan")
    payrolls = relationship("HRPayroll", back_populates="employee", cascade="all, delete-orphan")
    labor_documents = relationship("HRLaborDocument", back_populates="employee", cascade="all, delete-orphan")
    attendance_records = relationship("HRAttendanceRecord", back_populates="employee", cascade="all, delete-orphan")


class HRContract(Base):
    """Contrato laboral o de prestación de servicios profesionales."""
    __tablename__ = "hr_contracts"
    __table_args__ = {"schema": "hr"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hr.hr_employees.id"), nullable=False, index=True)
    contract_type = Column(Enum(ContractType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    
    # Remuneración
    base_salary = Column(Numeric(12, 2), default=0.00, nullable=False)  # CLP
    hourly_rate = Column(Numeric(10, 2), default=0.00, nullable=False)  # Para docentes por hora
    clinical_commission_pct = Column(Numeric(5, 2), default=0.00, nullable=False)  # % sobre valor atención clínica
    weekly_hours = Column(Integer, default=40, nullable=False)

    # Previsión chilena
    afp_name = Column(String(50), nullable=True)
    health_system = Column(String(50), default="FONASA", nullable=True)  # FONASA o Isapre
    health_quote_pct = Column(Numeric(5, 2), default=7.00, nullable=False)  # 7% legal

    status = Column(Enum(ContractStatus), default=ContractStatus.ACTIVE, nullable=False)
    document_url = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("HREmployee", back_populates="contracts")


class HRLeaveRequest(Base):
    """Solicitud y registro de permisos, vacaciones o licencias médicas."""
    __tablename__ = "hr_leave_requests"
    __table_args__ = {"schema": "hr"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hr.hr_employees.id"), nullable=False, index=True)
    leave_type = Column(Enum(LeaveType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days_count = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.PENDING, nullable=False)
    approved_by = Column(String(36), ForeignKey("core.users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("HREmployee", back_populates="leave_requests")


class HRFeeReceipt(Base):
    """Boleta de honorarios profesional (BHE) para docentes o terapeutas independientes."""
    __tablename__ = "hr_fee_receipts"
    __table_args__ = {"schema": "hr"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hr.hr_employees.id"), nullable=False, index=True)
    cost_center_id = Column(String(36), ForeignKey("finance.cost_centers.id", ondelete="SET NULL"), nullable=True, index=True)
    cost_center = Column(String(120), default="CC-101 Docencia y Aranceles Escuela San Bao", nullable=False)
    receipt_number = Column(String(50), nullable=False, index=True)
    issue_date = Column(Date, nullable=False)
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    description = Column(String(255), nullable=False)

    # Valores tributarios chilenos (Ley 21.133: Bruto = horas x valor hora, Retención = bruto x tasa vigente, Líquido = bruto - retención)
    academic_hours = Column(Numeric(6, 2), default=0.00, nullable=False, comment="H: Horas académicas validadas en el período")
    clinical_hours = Column(Numeric(6, 2), default=0.00, nullable=False, comment="H: Horas de tutoría/atención clínica validadas en el período")
    hourly_rate = Column(Numeric(12, 2), default=0.00, nullable=False, comment="H: Valor hora aplicado")
    gross_amount = Column(Numeric(12, 2), nullable=False)
    retention_rate = Column(Numeric(5, 2), nullable=False, comment="H: Tasa de retención obtenida de hr.tax_retention_rates por período Ley 21.133")
    retention_amount = Column(Numeric(12, 2), nullable=False)
    net_amount = Column(Numeric(12, 2), nullable=False)

    status = Column(Enum(FeeReceiptStatus), default=FeeReceiptStatus.DRAFT, nullable=False)
    payment_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("HREmployee", back_populates="fee_receipts")


class HRPayroll(Base):
    """Liquidación de remuneración mensual formal según normativa laboral chilena."""
    __tablename__ = "hr_payrolls"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_id", "period_year", "period_month", name="uq_hr_payroll_period"),
        Index("ix_hr_payrolls_comp_period", "company_id", "period_year", "period_month"),
        {"schema": "hr"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hr.hr_employees.id"), nullable=False, index=True)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("hr.hr_contracts.id"), nullable=False)
    cost_center_id = Column(String(36), ForeignKey("finance.cost_centers.id", ondelete="SET NULL"), nullable=True, index=True)
    cost_center = Column(String(120), default="CC-101 Docencia y Aranceles Escuela San Bao", nullable=False)
    
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    worked_days = Column(Integer, default=30, nullable=False)

    # Haberes
    base_salary = Column(Numeric(12, 2), nullable=False)
    legal_gratuity = Column(Numeric(12, 2), default=0.00, nullable=False)  # 25% con tope
    bonuses = Column(Numeric(12, 2), default=0.00, nullable=False)
    overtime_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    gross_taxable_salary = Column(Numeric(12, 2), nullable=False)
    non_taxable_allowances = Column(Numeric(12, 2), default=0.00, nullable=False)  # Colación/movilización
    total_earnings = Column(Numeric(12, 2), nullable=False)

    # Descuentos legales
    pension_deduction = Column(Numeric(12, 2), nullable=False)  # AFP
    health_deduction = Column(Numeric(12, 2), nullable=False)   # Fonasa/Isapre
    unemployment_insurance = Column(Numeric(12, 2), default=0.00, nullable=False)  # AFC
    income_tax = Column(Numeric(12, 2), default=0.00, nullable=False)  # Impuesto único 2da categoría
    other_deductions = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_deductions = Column(Numeric(12, 2), nullable=False)

    # Líquido a pagar
    net_salary = Column(Numeric(12, 2), nullable=False)
    status = Column(Enum(PayrollStatus), default=PayrollStatus.DRAFT, nullable=False)
    payment_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("HREmployee", back_populates="payrolls")
    contract = relationship("HRContract")


class HRLaborDocument(Base):
    """Control de documentación laboral y carpeta digital del trabajador (Contrato, RIOHS, SIS Minsal, Antecedentes, EPP)."""
    __tablename__ = "hr_labor_documents"
    __table_args__ = {"schema": "hr"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hr.hr_employees.id"), nullable=False, index=True)
    document_type = Column(String(60), nullable=False, index=True)
    document_code = Column(String(60), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    issue_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    status = Column(String(30), default="VIGENTE", nullable=False)  # VIGENTE, POR_VENCER, PENDIENTE, VENCIDO
    file_url = Column(String(255), nullable=True)
    verified_by = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("HREmployee", back_populates="labor_documents")


class HRAttendanceRecord(Base):
    """Registro de asistencia diaria, bloques docentes/clínicos, atrasos y horas extraordinarias."""
    __tablename__ = "hr_attendance_records"
    __table_args__ = {"schema": "hr"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("hr.hr_employees.id"), nullable=False, index=True)
    attendance_date = Column(Date, nullable=False, index=True)
    shift_name = Column(String(100), nullable=False)
    check_in = Column(String(10), nullable=True)
    check_out = Column(String(10), nullable=True)
    worked_hours = Column(Numeric(5, 2), default=0.00, nullable=False)
    overtime_hours = Column(Numeric(5, 2), default=0.00, nullable=False)
    late_minutes = Column(Integer, default=0, nullable=False)
    status = Column(String(30), default="PRESENTE", nullable=False)  # PRESENTE, ATRASO, PERMISO, VACACIONES, LICENCIA_MEDICA
    modality = Column(String(40), default="PRESENCIAL", nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee = relationship("HREmployee", back_populates="attendance_records")


class TaxRetentionRate(Base):
    """
    Tabla Parametrizable de Tasas de Retención de Boletas de Honorarios por Período según Ley 21.133 (Requerimiento H).
    Evita dejar porcentajes legales fijos en el código.
    """

    __tablename__ = "tax_retention_rates"
    __table_args__ = {"schema": "hr"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    period_year = Column(Integer, unique=True, nullable=False, index=True, comment="Año tributario ej: 2024, 2025, 2026, 2027, 2028")
    retention_rate_pct = Column(Numeric(5, 2), nullable=False, comment="Tasa porcentual vigente según gradualidad Ley 21.133")
    legal_reference = Column(String(200), default="Ley N° 21.133 - Cotizaciones Previsionales Honorarios SII", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    updated_by = Column(String(150), default="Dirección de Finanzas & RRHH San Bao", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


