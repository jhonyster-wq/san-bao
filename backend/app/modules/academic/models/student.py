import uuid
from sqlalchemy import Column, String, Boolean, Date, Numeric, Integer, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class Student(Base, AuditMixin):
    """
    Expediente del Alumno del Instituto de Medicina China Clásica SpA.
    Vinculado 1:1 con su registro maestro de persona natural (core.people).
    """

    __tablename__ = "students"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), ForeignKey("core.people.id"), unique=True, nullable=False, index=True)
    student_number = Column(String(50), unique=True, nullable=False, index=True, comment="Número de matrícula institucional")
    admission_date = Column(Date, nullable=False)
    status = Column(String(50), default="REGULAR", nullable=False, comment="APPLICANT, REGULAR, CONGELADO, GRADUATED, SUSPENDED, WITHDRAWN")
    freeze_reason = Column(String(255), nullable=True, comment="Motivo justificado de congelamiento de matrícula")
    freeze_date = Column(Date, nullable=True, comment="Fecha oficial de congelamiento de estudios")
    clinical_practice_approved = Column(Boolean, default=False, nullable=False, comment="Aprobación curricular para prácticas clínicas supervisadas")
    clinical_practice_approval_date = Column(Date, nullable=True, comment="Fecha de aprobación de práctica clínica")
    clinical_practice_notes = Column(Text, nullable=True, comment="Observaciones o resolución de habilitación clínica")
    notes = Column(String(500), nullable=True)

    person = relationship("Person", foreign_keys=[person_id])
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    cohort_enrollments = relationship("CohortEnrollment", back_populates="student", cascade="all, delete-orphan")
    transfers = relationship("StudentCourseTransfer", back_populates="student", cascade="all, delete-orphan")
    documents = relationship("AcademicDocument", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student {self.student_number} Person: {self.person_id}>"


class Enrollment(Base, AuditMixin):
    """
    Matrícula formal de un estudiante en un programa para un período académico determinado.
    Genera automáticamente el compromiso financiero (Arancel) en el esquema finance.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "program_id", "academic_period_id", name="uq_enrollment_student_program_period"),
        Index("ix_enrollments_student_status", "student_id", "status"),
        {"schema": "academic"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    program_id = Column(String(36), ForeignKey("academic.programs.id", ondelete="RESTRICT"), nullable=False, index=True)
    academic_period_id = Column(String(36), ForeignKey("academic.academic_periods.id", ondelete="RESTRICT"), nullable=False, index=True)
    enrollment_date = Column(Date, nullable=False)
    status = Column(String(50), default="CONFIRMED", nullable=False, index=True, comment="REGISTERED, CONFIRMED, CANCELLED")

    student = relationship("Student", back_populates="enrollments")
    program = relationship("Program")
    academic_period = relationship("AcademicPeriod")
    cohort_enrollments = relationship("CohortEnrollment", back_populates="enrollment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Enrollment student={self.student_id} program={self.program_id} period={self.academic_period_id}>"


class CohortEnrollment(Base, AuditMixin):
    """
    Inscripción de una asignatura específica (cohorte/sección) por parte de un estudiante matriculado.
    Registra nota final y porcentaje de asistencia del semestre.
    """

    __tablename__ = "cohort_enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "cohort_id", name="uq_cohort_enrollment_student_cohort"),
        Index("ix_cohort_enrollments_cohort_status", "cohort_id", "status"),
        {"schema": "academic"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enrollment_id = Column(String(36), ForeignKey("academic.enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    cohort_id = Column(String(36), ForeignKey("academic.cohorts.id", ondelete="CASCADE"), nullable=False, index=True)
    final_grade = Column(Numeric(3, 1), nullable=True, comment="Calificación final chilena (1.0 a 7.0)")
    attendance_percentage = Column(Numeric(5, 2), default=0.0, nullable=False)
    status = Column(String(50), default="ENROLLED", nullable=False, comment="ENROLLED, APPROVED, FAILED, WITHDRAWN")

    enrollment = relationship("Enrollment", back_populates="cohort_enrollments")
    student = relationship("Student", back_populates="cohort_enrollments")
    cohort = relationship("Cohort", back_populates="enrollments")

    def __repr__(self):
        return f"<CohortEnrollment student={self.student_id} cohort={self.cohort_id} status={self.status}>"


class StudentCourseTransfer(Base, AuditMixin):
    """
    Registro histórico de cambios o traspasos de curso o diplomado de un alumno.
    Permite trazabilidad del cambio curricular autorizado por Coordinación Académica.
    """

    __tablename__ = "student_course_transfers"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    from_program_id = Column(String(36), ForeignKey("academic.programs.id"), nullable=False, index=True)
    to_program_id = Column(String(36), ForeignKey("academic.programs.id"), nullable=False, index=True)
    transfer_date = Column(Date, nullable=False)
    reason = Column(String(255), nullable=False, comment="Motivo del cambio de curso")
    notes = Column(Text, nullable=True)

    student = relationship("Student", back_populates="transfers")
    from_program = relationship("Program", foreign_keys=[from_program_id])
    to_program = relationship("Program", foreign_keys=[to_program_id])


class AcademicDocument(Base, AuditMixin):
    """
    Registro y foliación de documentación oficial emitida por la Escuela San Bao.
    Certificados de Alumno Regular, Certificados de Curso, Documentación de Egreso y Diplomas.
    """

    __tablename__ = "academic_documents"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = Column(String(50), nullable=False, comment="ALUMNO_REGULAR, CERTIFICADO_CURSO, DOCUMENTACION_EGRESO, DIPLOMA_EGRESO")
    document_number = Column(String(100), unique=True, nullable=False, index=True, comment="Folio correlativo único oficial (ej: CERT-AR-2026-0001)")
    program_id = Column(String(36), ForeignKey("academic.programs.id"), nullable=True, index=True)
    course_id = Column(String(36), ForeignKey("academic.courses.id"), nullable=True, index=True)
    issue_date = Column(Date, nullable=False)
    is_compliant = Column(Boolean, default=True, nullable=False, comment="Verificación de cumplimiento de malla curricular")
    content_payload = Column(Text, nullable=True, comment="JSON o datos estructurados del documento oficial emitido")
    issued_by = Column(String(100), default="Coordinación Académica - Escuela San Bao", nullable=False)

    student = relationship("Student", back_populates="documents")
    program = relationship("Program", foreign_keys=[program_id])
    course = relationship("Course", foreign_keys=[course_id])


class StudentOnboarding(Base, AuditMixin):
    """
    Flujo de Admisión y Matrícula Digital de Alumnos (Coordinación Académica):
    1) Verificación de duplicidad de postulante
    2) Precarga de arancel según Catálogo de Diplomados/Cursos/Formación Continua
    3) Envío de link de Contrato al correo para Firma Electrónica
    4) Confirmación de Firma Electrónica -> Estado DOCUMENTO_FIRMADO + Link de Pago Webpay
    5) Confirmación de Pago Webpay -> Alumno REGULAR + Creación de Sesión Portal Alumno (RUT + Password Segura)
    """

    __tablename__ = "student_onboardings"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(String(36), ForeignKey("core.people.id", ondelete="CASCADE"), nullable=False, index=True)
    enrollment_id = Column(String(36), ForeignKey("academic.enrollments.id", ondelete="SET NULL"), nullable=True, index=True)
    program_id = Column(String(36), ForeignKey("academic.programs.id", ondelete="RESTRICT"), nullable=False, index=True)
    commitment_id = Column(String(36), ForeignKey("finance.payment_commitments.id", ondelete="SET NULL"), nullable=True, index=True)
    legal_document_id = Column(String(36), ForeignKey("finance.legal_documents.id", ondelete="SET NULL"), nullable=True, index=True)

    # Aranceles precargados desde catálogo
    enrollment_fee = Column(Numeric(12, 0), default=0, nullable=False, comment="Valor matrícula / pago inicial Webpay")
    tuition_amount = Column(Numeric(12, 0), default=0, nullable=False, comment="Arancel total del programa")
    installments_count = Column(Integer, default=10, nullable=False)

    # Paso 3 y 4: Contrato y Firma Electrónica
    contract_code = Column(String(60), nullable=True)
    contract_sign_link = Column(String(500), nullable=True)
    contract_email_sent = Column(Boolean, default=True, nullable=False)
    signature_token = Column(String(128), nullable=True)
    document_hash = Column(String(64), nullable=True)
    contract_signed_at = Column(String(60), nullable=True)

    # Paso 4 y 5: Link de Pago Webpay y Activación de Sesión Alumno
    webpay_token = Column(String(120), nullable=True)
    webpay_link = Column(String(500), nullable=True)
    webpay_amount = Column(Numeric(12, 0), default=0, nullable=False)
    webpay_auth_code = Column(String(60), nullable=True)
    webpay_paid_at = Column(String(60), nullable=True)
    dte_folio = Column(Integer, nullable=True)

    # Credenciales de sesión Portal Alumno (RUT + Password Segura)
    portal_username = Column(String(50), nullable=True, index=True)
    portal_temp_password = Column(String(100), nullable=True)
    portal_user_id = Column(String(36), ForeignKey("core.users.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(
        String(50),
        default="CONTRACT_SENT",
        nullable=False,
        comment="CONTRACT_SENT, DOCUMENT_SIGNED, REGULAR_ACTIVE",
    )

    student = relationship("Student")
    person = relationship("Person")
    program = relationship("Program")
    enrollment = relationship("Enrollment")


