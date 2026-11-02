import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Numeric, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class ClinicalEncounter(Base, AuditMixin):
    """
    Ficha de Atención Clínica Electrónica especializada en Medicina Tradicional China (MTC).
    Cumple con la Ley N° 20.584 sobre derechos y deberes en salud y confidencialidad médica.
    Permite registrar atenciones de terapeutas titulares o atenciones supervisadas de alumnos en práctica.
    """

    __tablename__ = "encounters"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("clinical.patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    appointment_id = Column(String(36), ForeignKey("clinical.appointments.id", ondelete="SET NULL"), nullable=True, unique=True)
    practitioner_id = Column(String(36), ForeignKey("clinical.practitioners.id", ondelete="RESTRICT"), nullable=False, index=True, comment="Terapeuta titular o Tutor Clínico supervisor")
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="SET NULL"), nullable=True, index=True, comment="Alumno en práctica supervisada (si corresponde)")

    encounter_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # 1. Anamnesis y Antecedentes
    reason_for_consultation = Column(Text, nullable=False, comment="Motivo de consulta principal")
    current_illness_history = Column(Text, nullable=True, comment="Historia de la enfermedad actual")
    traditional_anamnesis = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Interrogatorio tradicional MTC: sueño, apetito, sed, frío/calor, sudoración, digestión, dolor, ciclo menstrual",
    )

    # 2. Diagnóstico Tradicional MTC
    tongue_diagnosis = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Diagnóstico por Lengua: color_cuerpo, forma, marcas_dentales, color_saburra, espesor, humedad",
    )
    pulse_diagnosis = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Diagnóstico por Pulso: muñeca izquierda (Cun, Guan, Chi) y derecha (Cun, Guan, Chi), cualidades (tenso, resbaladizo, etc.)",
    )
    zang_fu_syndrome = Column(String(255), nullable=True, comment="Diferenciación de síndromes Zang-Fu (ej: Insuficiencia de Qi de Bazo)")
    eight_principles = Column(JSON, nullable=True, default=dict, comment="8 Principios: Interior/Exterior, Frío/Calor, Vacío/Plenitud, Yin/Yang")

    # 3. Tratamiento y Prescripción
    therapeutic_principle = Column(Text, nullable=True, comment="Principio de tratamiento (ej: Tonificar Bazo y drenar Humedad)")
    treatment_plan = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Puntos de Acupuntura seleccionados, método de punción, moxibustión, ventosas, auriculoterapia, fitoterapia",
    )
    recommendations = Column(Text, nullable=True, comment="Recomendaciones de dietoterapia y estilo de vida")

    # 4. Supervisión Docente (si intervino un alumno)
    tutor_feedback = Column(Text, nullable=True, comment="Comentarios y correcciones del tutor clínico")
    tutor_grade = Column(Numeric(3, 1), nullable=True, comment="Evaluación pedagógica de la sesión (1.0 a 7.0)")

    # 5. Estado y Firma Legal
    status = Column(String(50), default="DRAFT", nullable=False, comment="DRAFT (borrador alumno), VALIDATED, SIGNED (firmada legalmente por profesional)")
    signed_at = Column(DateTime(timezone=True), nullable=True)
    signed_by = Column(String(36), ForeignKey("core.users.id"), nullable=True)

    patient = relationship("Patient", back_populates="encounters")
    appointment = relationship("Appointment", back_populates="encounter")
    practitioner = relationship("Practitioner")
    student = relationship("Student")
    signer = relationship("User", foreign_keys=[signed_by])

    def __repr__(self):
        return f"<ClinicalEncounter {self.id} Patient={self.patient_id} Date={self.encounter_date} Status={self.status}>"
