import uuid
from sqlalchemy import Column, String, Boolean, Date, Numeric, Integer, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class Evaluation(Base, AuditMixin):
    """
    Evaluación parcial programada dentro de una cohorte/sección.
    Ej: Certamen 1 (30%), Control Práctico de Acupuntura (30%), Examen Final (40%).
    """

    __tablename__ = "evaluations"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cohort_id = Column(String(36), ForeignKey("academic.cohorts.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(String(36), ForeignKey("academic.courses.id", ondelete="SET NULL"), nullable=True, index=True, comment="Asignatura específica evaluada")
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    weight_percentage = Column(Numeric(5, 2), nullable=False, comment="Ponderación porcentual (ej: 25.0)")
    evaluation_date = Column(Date, nullable=False)

    cohort = relationship("Cohort", back_populates="evaluations")
    course = relationship("Course", backref="evaluations")
    grades = relationship("Grade", back_populates="evaluation", cascade="all, delete-orphan")


class Grade(Base, AuditMixin):
    """
    Calificación individual de un estudiante en una evaluación.
    Escala oficial chilena: 1.0 a 7.0 (Aprobación >= 4.0).
    """

    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("evaluation_id", "student_id", name="uq_grade_evaluation_student"),
        Index("ix_grades_student_eval", "student_id", "evaluation_id"),
        {"schema": "academic"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id = Column(String(36), ForeignKey("academic.evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Numeric(3, 1), nullable=False, comment="Nota de 1.0 a 7.0")
    feedback = Column(Text, nullable=True, comment="Comentarios o retroalimentación del docente")
    graded_by = Column(String(36), ForeignKey("core.users.id"), nullable=True, index=True)

    evaluation = relationship("Evaluation", back_populates="grades")
    student = relationship("Student")


class Attendance(Base, AuditMixin):
    """Registro individual de asistencia a sesiones de clase o prácticas."""

    __tablename__ = "attendances"
    __table_args__ = (
        Index("ix_attendances_student_course_date", "student_id", "course_id", "class_date"),
        {"schema": "academic"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cohort_id = Column(String(36), ForeignKey("academic.cohorts.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(String(36), ForeignKey("academic.courses.id", ondelete="CASCADE"), nullable=True, index=True, comment="Asignatura cátedra a la que corresponde la clase")
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    class_date = Column(Date, nullable=False)
    class_number = Column(Integer, nullable=True, comment="Número de clase o sesión")
    session_topic = Column(String(255), nullable=True, comment="Tema abordado en la sesión")
    status = Column(String(20), default="PRESENTE", nullable=False, comment="PRESENTE, AUSENTE, JUSTIFICADO, ATRASO")
    is_present = Column(Boolean, default=True, nullable=False)
    is_excused = Column(Boolean, default=False, nullable=False)
    notes = Column(String(255), nullable=True)

    course = relationship("Course", backref="attendances")
    student = relationship("Student", backref="attendances")


class ClinicalPracticeHour(Base, AuditMixin):
    """
    Registro y acreditación de horas prácticas clínicas acumuladas por el estudiante.
    Punto de integración directo entre la Escuela (requisito de egreso) y la Clínica San Bao.
    """

    __tablename__ = "clinical_practice_hours"
    __table_args__ = (
        Index("ix_clinical_practice_student_status", "student_id", "status"),
        Index("ix_clinical_practice_tutor_date", "tutor_id", "activity_date"),
        {"schema": "academic"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    cohort_id = Column(String(36), ForeignKey("academic.cohorts.id", ondelete="SET NULL"), nullable=True, index=True)
    tutor_id = Column(String(36), ForeignKey("core.people.id"), nullable=False, index=True, comment="Terapeuta o tutor que certifica")
    activity_date = Column(Date, nullable=False, index=True)
    hours_completed = Column(Integer, nullable=False, default=3)
    patient_encounter_id = Column(String(36), ForeignKey("clinical.encounters.id", ondelete="SET NULL"), nullable=True, index=True, comment="ID de la atención clínica vinculada en schema clinical")
    shift_id = Column(String(36), nullable=True, index=True, comment="C: ID del turno clínico cuyo cierre originó las horas")
    specialty = Column(String(100), default="ACUPUNTURA", nullable=False, comment="C: Especialidad clínica (ACUPUNTURA, TUI_NA, FITOTERAPIA)")
    idempotency_key = Column(String(120), unique=True, nullable=True, index=True, comment="C: Clave de idempotencia para evitar duplicar horas ante reenvío de evento")
    record_type = Column(String(40), default="ACREDITACION_TURNO", nullable=False, comment="C: ACREDITACION_TURNO, SESION_CLINICA, AJUSTE_AUDITABLE")
    parent_hour_id = Column(String(36), ForeignKey("academic.clinical_practice_hours.id", ondelete="SET NULL"), nullable=True, index=True, comment="C: Registro original al que aplica el ajuste auditable")
    adjusted_by_user_id = Column(String(36), nullable=True, comment="C: Usuario que realizó el ajuste auditable")
    adjustment_reason = Column(String(255), nullable=True, comment="C: Motivo del ajuste auditable sin sobrescribir registro original")
    remuneration_accrued = Column(Boolean, default=True, nullable=False, comment="C: Indica si generó información devengada para remuneraciones del tutor")
    status = Column(String(50), default="APPROVED", nullable=False, index=True, comment="PENDING, APPROVED, REJECTED")
    comments = Column(Text, nullable=True)

    student = relationship("Student")
    tutor = relationship("Person", foreign_keys=[tutor_id])


class TutorStudentEvaluation(Base, AuditMixin):
    """
    Evaluación Semestral del Alumno por el Tutor Clínico y Registro de Entrega de Reportes Clínicos (Requerimiento B.7).
    """

    __tablename__ = "tutor_student_evaluations"
    __table_args__ = (
        Index("ix_tutor_student_eval_student_period", "student_id", "period_code"),
        {"schema": "academic"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    tutor_id = Column(String(36), ForeignKey("core.people.id"), nullable=False, index=True)
    period_code = Column(String(30), default="2026-2", nullable=False, index=True, comment="Semestre evaluado ej: 2026-1, 2026-2")
    specialty = Column(String(100), default="ACUPUNTURA", nullable=False)

    clinical_competency_score = Column(Numeric(3, 1), nullable=False, comment="Desempeño clínico y técnica MTC (1.0 a 7.0)")
    anamnesis_quality_score = Column(Numeric(3, 1), nullable=False, comment="Calidad de anamnesis, pulso y lengua (1.0 a 7.0)")
    punctuality_ethics_score = Column(Numeric(3, 1), nullable=False, comment="Puntualidad, ética y trato al paciente (1.0 a 7.0)")
    final_score = Column(Numeric(3, 1), nullable=False, comment="Promedio semestral de práctica (1.0 a 7.0)")

    clinical_reports_required = Column(Integer, default=5, nullable=False, comment="Cantidad de reportes clínicos exigidos en el semestre")
    clinical_reports_delivered = Column(Integer, default=5, nullable=False, comment="Cantidad de reportes clínicos entregados por el alumno")
    clinical_reports_compliant = Column(Boolean, default=True, nullable=False, comment="True si cumplió con la entrega de reportes clínicos")
    report_delivery_notes = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)
    evaluation_date = Column(Date, nullable=False)

    student = relationship("Student")
    tutor = relationship("Person", foreign_keys=[tutor_id])


class StudentTutorEvaluation(Base, AuditMixin):
    """
    Evaluación del Tutor por parte del Alumno con Control Estricto de Confidencialidad (Requerimiento B.7).
    Los reportes expuestos a Dirección y Tutores son exclusivamente agregados y anónimos.
    """

    __tablename__ = "student_tutor_evaluations"
    __table_args__ = (
        UniqueConstraint("student_id", "tutor_id", "period_code", name="uq_student_tutor_eval_period"),
        Index("ix_student_tutor_eval_tutor_period", "tutor_id", "period_code"),
        {"schema": "academic"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="CASCADE"), nullable=False, index=True)
    tutor_id = Column(String(36), ForeignKey("core.people.id"), nullable=False, index=True)
    period_code = Column(String(30), default="2026-2", nullable=False, index=True)

    pedagogical_clarity_score = Column(Numeric(3, 1), nullable=False, comment="Claridad pedagógica del tutor (1.0 a 7.0)")
    supervision_support_score = Column(Numeric(3, 1), nullable=False, comment="Acompañamiento y supervisión en box (1.0 a 7.0)")
    clinical_feedback_score = Column(Numeric(3, 1), nullable=False, comment="Calidad de la retroalimentación clínica (1.0 a 7.0)")
    overall_score = Column(Numeric(3, 1), nullable=False, comment="Puntaje general del tutor (1.0 a 7.0)")

    confidential_comments = Column(Text, nullable=True, comment="Comentario confidencial del alumno")
    is_confidential = Column(Boolean, default=True, nullable=False)
    evaluation_date = Column(Date, nullable=False)

    student = relationship("Student")
    tutor = relationship("Person", foreign_keys=[tutor_id])

