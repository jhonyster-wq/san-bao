import uuid
from datetime import date, datetime
from sqlalchemy import Column, String, Integer, Numeric, Boolean, Date, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class ClinicalSessionPrice(Base, AuditMixin):
    """
    Aranceles y valores de sesiones clínicas administrados por la Dirección Clínica.
    Aplica para Servicios Clínicos San Bao SpA.
    """

    __tablename__ = "clinical_session_prices"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), default="GENERAL", nullable=False, comment="GENERAL, DOCENTE, INTEGRAL, CONVENIO")
    duration_minutes = Column(Integer, default=60, nullable=False)
    session_count = Column(Integer, default=1, nullable=False, comment="Cantidad de sesiones incluidas: 1 para individual, 2 a X para packs")
    service_type = Column(String(50), default="ACUPUNTURA", nullable=False, comment="ACUPUNTURA, TUI_NA, INTEGRAL")
    price_clp = Column(Numeric(10, 0), nullable=False, comment="Precio de la sesión en Pesos Chilenos (CLP)")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    company = relationship("Company")


class PatientTreatmentPack(Base, AuditMixin):
    """
    Seguimiento y control de packs de sesiones clínicas adquiridas por un paciente.
    Registra la cantidad de sesiones (1 a X), sesiones consumidas y sesiones restantes.
    Se descuentan automáticamente cada vez que el paciente se atiende.
    """

    __tablename__ = "patient_treatment_packs"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("clinical.patients.id"), nullable=False, index=True)
    session_price_id = Column(String(36), ForeignKey("clinical.clinical_session_prices.id"), nullable=True, index=True)

    pack_name = Column(String(100), nullable=False)
    service_type = Column(String(50), default="ACUPUNTURA", nullable=False)
    total_sessions = Column(Integer, default=1, nullable=False, comment="Cantidad total de sesiones del pack (1 a X)")
    used_sessions = Column(Integer, default=0, nullable=False, comment="Sesiones consumidas/atendidas")
    remaining_sessions = Column(Integer, default=1, nullable=False, comment="Sesiones restantes disponibles")
    price_paid_clp = Column(Numeric(10, 0), default=0, nullable=False)
    status = Column(String(30), default="ACTIVE", nullable=False, comment="ACTIVE, EXHAUSTED, CANCELLED")
    purchase_date = Column(Date, default=date.today, nullable=False)
    notes = Column(Text, nullable=True)

    company = relationship("Company")
    patient = relationship("Patient")
    session_price = relationship("ClinicalSessionPrice")


class ClinicalShiftSchedule(Base, AuditMixin):
    """
    Programación de turnos clínicos y turnero de terapeutas por sede (Santiago Providencia / Viña del Mar).
    Administrado por la Dirección Clínica.
    """

    __tablename__ = "clinical_shift_schedules"
    __table_args__ = (
        Index("ix_shifts_practitioner_date", "practitioner_id", "shift_date"),
        Index("ix_shifts_campus_date_period", "campus_id", "shift_date", "shift_period"),
        {"schema": "clinical"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    campus_id = Column(String(36), ForeignKey("core.campuses.id"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("core.rooms.id"), nullable=True)
    practitioner_id = Column(String(36), ForeignKey("clinical.practitioners.id"), nullable=True, index=True)
    substitute_practitioner_id = Column(String(36), ForeignKey("clinical.practitioners.id"), nullable=True, index=True)
    substitute_active = Column(Boolean, default=False, nullable=False, comment="Indica si el tutor suplente está activado para este turno")
    intern_student_id = Column(String(36), ForeignKey("academic.students.id"), nullable=True, index=True, comment="Alumno en práctica clínica supervisada asignado por Dirección Clínica")
    intern_student_name = Column(String(200), nullable=True, comment="Nombre visible del alumno practicante asignado al turno")
    
    shift_code = Column(String(50), nullable=False, index=True)
    shift_name = Column(String(100), nullable=False, comment="Turno Mañana, Turno Tarde, Turno Sábado")
    service_type = Column(String(50), default="ACUPUNTURA", nullable=False, comment="ACUPUNTURA, TUI_NA")
    shift_period = Column(String(30), default="AM", nullable=False, comment="AM (10:00-14:00), PM (15:00-19:00), VESPERTINO (18:00-22:00)")
    day_schedule = Column(String(50), default="LUNES_A_SABADO", nullable=False, comment="LUNES_A_SABADO (AM/PM) o LUNES_A_VIERNES (Vespertino)")
    shift_date = Column(Date, default=date.today, nullable=False, index=True)
    start_time = Column(String(5), default="10:00", nullable=False)
    end_time = Column(String(5), default="14:00", nullable=False)
    status = Column(String(30), default="OPEN", nullable=False, comment="OPEN, ASSIGNED, IN_PROGRESS, CLOSED, CANCELLED")
    closed_at = Column(DateTime, nullable=True)
    closed_by_user_id = Column(String(36), ForeignKey("core.users.id"), nullable=True)
    closure_type = Column(String(50), default="SINGLE_DATE", nullable=True, comment="SINGLE_DATE, DATE_RANGE, SPECIFIC_DATES, PERMANENT")
    closure_start_date = Column(Date, nullable=True, comment="Fecha de inicio o fecha puntual en que se cerrará el turno")
    closure_end_date = Column(Date, nullable=True, comment="Fecha de término del cierre programado")
    closure_dates_text = Column(String(255), nullable=True, comment="Texto legible de las fechas de cierre (ej: 01/11/2026 al 05/11/2026)")
    closure_reason = Column(String(255), nullable=True, comment="Motivo institucional del cierre asistencial")
    notes = Column(Text, nullable=True)

    company = relationship("Company")
    campus = relationship("Campus")
    room = relationship("Room")
    practitioner = relationship("Practitioner", foreign_keys=[practitioner_id])
    substitute_practitioner = relationship("Practitioner", foreign_keys=[substitute_practitioner_id])
    closed_by = relationship("User", foreign_keys=[closed_by_user_id])


class ClinicalSecretaryAssignment(Base, AuditMixin):
    """
    Asignación institucional de secretarias clínicas a sedes de atención (Santiago / Viña del Mar).
    Determinada formalmente por la Dirección Clínica de Servicios Clínicos San Bao SpA.
    Define qué sede clínica puede visualizar y gestionar cada secretaria en su perfil.
    """

    __tablename__ = "clinical_secretary_assignments"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("core.users.id"), nullable=False, index=True)
    campus_id = Column(String(36), ForeignKey("core.campuses.id"), nullable=False, index=True)
    is_primary = Column(Boolean, default=True, nullable=False)
    assignment_date = Column(Date, default=date.today, nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False, comment="ACTIVE, INACTIVE, TEMPORARY")
    notes = Column(Text, nullable=True)

    company = relationship("Company")
    user = relationship("User", foreign_keys=[user_id])
    campus = relationship("Campus", foreign_keys=[campus_id])


class ClinicalPaymentRequest(Base, AuditMixin):
    """
    Solicitud de Pago emitida por Dirección Clínica hacia el Área de Finanzas (Normalizada 3NF/BCNF).
    Incluye factura adjunta (PDF/Imagen/DTE) para que Finanzas ingrese la obligación a CxP y ejecute el pago,
    actualizando automáticamente el estado en Dirección Clínica (PENDIENTE_FINANZAS -> FACTURA_INGRESADA_CXP -> PAGADA).
    """

    __tablename__ = "clinical_payment_requests"
    __table_args__ = (
        Index("ix_clin_payreq_company_status", "company_id", "status"),
        {"schema": "clinical"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    campus_id = Column(String(36), ForeignKey("core.campuses.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by_user_id = Column(String(36), ForeignKey("core.users.id", ondelete="SET NULL"), nullable=True, index=True)
    payable_id = Column(String(36), ForeignKey("finance.accounts_payable.id", ondelete="SET NULL"), nullable=True, index=True)

    request_code = Column(String(50), unique=True, nullable=False, index=True, comment="Ej: SOL-PAG-2026-0001")
    request_date = Column(Date, default=date.today, nullable=False, index=True)
    due_date = Column(Date, nullable=False, index=True)

    supplier_rut = Column(String(30), nullable=False, index=True)
    supplier_name = Column(String(255), nullable=False)
    invoice_type = Column(String(50), default="FACTURA_AFECTA_33", nullable=False, comment="FACTURA_AFECTA_33, FACTURA_EXENTA_34, BOLETA_HONORARIOS")
    invoice_number = Column(String(60), nullable=False, index=True)
    category = Column(String(80), default="INSUMOS_CLINICOS", nullable=False)
    cost_center = Column(String(120), default="CC-201 Clínica San Bao - Acupuntura Providencia", nullable=False)
    business_unit = Column(String(120), default="UN-03 Clínica Acupuntura Providencia", nullable=False)
    amount_clp = Column(Numeric(12, 0), nullable=False)
    concept = Column(String(255), nullable=False)

    attachment_filename = Column(String(255), nullable=False)
    attachment_mime_type = Column(String(100), default="application/pdf", nullable=False)
    attachment_data_url = Column(Text, nullable=True, comment="Contenido Base64/DataURL o representación del DTE adjunto")

    status = Column(
        String(40),
        default="PENDIENTE_FINANZAS",
        nullable=False,
        index=True,
        comment="PENDIENTE_FINANZAS, FACTURA_INGRESADA_CXP, PAGADA, OBSERVADA",
    )
    payment_date = Column(Date, nullable=True)
    payment_method = Column(String(50), nullable=True)
    payment_reference = Column(String(100), nullable=True)
    journal_entry_number = Column(String(50), nullable=True)
    finance_notes = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    company = relationship("Company")
    campus = relationship("Campus")
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])


class ClinicalOverbookingRequest(Base, AuditMixin):
    """
    Solicitud de Sobrecupo Manual (Acupuntura y Tui Na) emitida desde Gestión Clínica / Toma de Hora
    y sujeta a autorización obligatoria por parte de Dirección Clínica.
    """

    __tablename__ = "clinical_overbooking_requests"
    __table_args__ = (
        Index("ix_clin_overbook_company_status_date", "company_id", "status", "appointment_date"),
        {"schema": "clinical"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    campus_id = Column(String(36), ForeignKey("core.campuses.id", ondelete="SET NULL"), nullable=True, index=True)
    shift_id = Column(String(36), ForeignKey("clinical.clinical_shift_schedules.id", ondelete="SET NULL"), nullable=True, index=True)
    practitioner_id = Column(String(36), ForeignKey("clinical.practitioners.id", ondelete="SET NULL"), nullable=True, index=True)

    request_code = Column(String(50), unique=True, nullable=False, index=True, comment="Ej: SOB-2026-0001")
    service_type = Column(String(50), default="ACUPUNTURA", nullable=False, index=True, comment="ACUPUNTURA, TUI_NA")
    shift_period = Column(String(30), default="AM", nullable=False, comment="AM, PM, VESPERTINO")
    appointment_date = Column(Date, default=date.today, nullable=False, index=True)
    requested_time = Column(String(15), nullable=False, comment="Hora del sobrecupo ej: 10:15, 12:40, 15:45")

    tutor_name = Column(String(200), nullable=False)
    room_name = Column(String(200), nullable=False)
    patient_rut = Column(String(30), nullable=False, index=True)
    patient_name = Column(String(200), nullable=False)
    patient_phone = Column(String(60), nullable=True)
    treatment_name = Column(String(200), nullable=True)
    reason = Column(Text, nullable=False)

    status = Column(String(30), default="PENDING", nullable=False, index=True, comment="PENDING, APPROVED, REJECTED")
    authorized_by = Column(String(200), nullable=True)
    authorized_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    company = relationship("Company")
    campus = relationship("Campus")


class ClinicalShiftClosureAffectedPatient(Base, AuditMixin):
    """
    Nómina de pacientes afectados por cierre de turno o jornada (por día, semana, mes o indefinidamente)
    enviada desde Dirección Clínica al panel de Gestión Clínica con propuesta de nueva hora para reagendar
    vía WhatsApp directo desde el sitio o vía llamada telefónica.
    """

    __tablename__ = "clinical_shift_closure_affected_patients"
    __table_args__ = (
        Index("ix_clin_shift_closure_aff_company_status", "company_id", "status", "original_date"),
        {"schema": "clinical"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    campus_id = Column(String(36), ForeignKey("core.campuses.id", ondelete="SET NULL"), nullable=True, index=True)
    shift_id = Column(String(36), ForeignKey("clinical.clinical_shift_schedules.id", ondelete="SET NULL"), nullable=True, index=True)

    closure_code = Column(String(50), nullable=False, index=True, comment="Ej: CIE-2026-0001")
    shift_code = Column(String(50), nullable=False, index=True, comment="Ej: TUR-ACU-STGO-AM")
    service_type = Column(String(50), default="ACUPUNTURA", nullable=False, index=True)
    shift_period = Column(String(30), default="AM", nullable=False)
    closure_scope = Column(String(30), default="DAY", nullable=False, comment="DAY, WEEK, MONTH, INDEFINITE")
    closure_dates_text = Column(String(255), nullable=False)
    closure_reason = Column(String(255), nullable=False)

    tutor_name = Column(String(200), nullable=False)
    box_name = Column(String(200), nullable=False)

    patient_rut = Column(String(30), nullable=False, index=True)
    patient_name = Column(String(200), nullable=False)
    patient_phone = Column(String(60), nullable=False)
    treatment_name = Column(String(200), nullable=True)

    original_date = Column(Date, nullable=False, index=True)
    original_time = Column(String(20), nullable=False)

    proposed_date = Column(Date, nullable=False)
    proposed_time = Column(String(20), nullable=False)
    proposed_tutor_name = Column(String(200), nullable=False)
    proposed_shift_code = Column(String(50), nullable=False)

    contact_channel = Column(String(30), default="NONE", nullable=False, comment="NONE, WHATSAPP, PHONE_CALL")
    contact_notes = Column(Text, nullable=True)
    status = Column(
        String(40),
        default="PENDING_CONTACT",
        nullable=False,
        index=True,
        comment="PENDING_CONTACT, PROPOSAL_SENT_WHATSAPP, CONTACTED_PHONE, RESCHEDULED, CANCELLED",
    )
    notified_at = Column(DateTime, nullable=True)
    rescheduled_at = Column(DateTime, nullable=True)
    handled_by = Column(String(200), nullable=True)

    company = relationship("Company")
    campus = relationship("Campus")


