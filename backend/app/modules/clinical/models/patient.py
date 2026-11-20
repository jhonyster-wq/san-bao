import uuid
from sqlalchemy import Column, String, Boolean, Date, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class Patient(Base, AuditMixin):
    """
    Paciente atendido en Servicios Clínicos San Bao SpA.
    Vinculado 1:1 a la entidad maestra Person (core.people) para evitar duplicación.
    """

    __tablename__ = "patients"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), ForeignKey("core.people.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True)
    record_number = Column(String(50), unique=True, nullable=False, index=True, comment="Número de Ficha Clínica legal ej: FICH-2026-0001")
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    emergency_contact_relationship = Column(String(50), nullable=True, comment="Familiar, cónyuge, etc.")
    blood_type = Column(String(10), nullable=True, comment="Grupo sanguíneo ej: O+, A+")
    allergies = Column(JSON, nullable=True, default=list, comment="Lista de alergias conocidas")
    chronic_conditions = Column(JSON, nullable=True, default=list, comment="Enfermedades crónicas o antecedentes mórbidos")
    general_notes = Column(Text, nullable=True)

    # D.1 y D.2: Seguimiento de pacientes, segmentación y consentimientos de comunicación
    last_visit_date = Column(Date, nullable=True, index=True, comment="D.2: Fecha de la última visita o atención clínica")
    retention_segment = Column(String(30), default="ACTIVO", nullable=False, index=True, comment="D.2: ACTIVO (<=45d), EN_RIESGO (46-90d), INACTIVO (>90d)")
    comm_consent_whatsapp = Column(Boolean, default=True, nullable=False, comment="D.1/D.2: Consentimiento de comunicaciones por WhatsApp")
    comm_consent_email = Column(Boolean, default=True, nullable=False, comment="D.1/D.2: Consentimiento de comunicaciones por Email")
    comm_opt_out = Column(Boolean, default=False, nullable=False, comment="D.1/D.2: Exclusión voluntaria de comunicaciones (Opt-Out)")
    comm_opt_out_at = Column(String(40), nullable=True, comment="Fecha/hora de exclusión de comunicaciones")

    is_active = Column(Boolean, default=True, nullable=False)

    person = relationship("Person", foreign_keys=[person_id])
    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    encounters = relationship("ClinicalEncounter", back_populates="patient", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Patient {self.record_number} person_id={self.person_id}>"
