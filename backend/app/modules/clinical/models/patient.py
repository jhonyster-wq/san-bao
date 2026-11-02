import uuid
from sqlalchemy import Column, String, Boolean, JSON, ForeignKey, Text
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
    is_active = Column(Boolean, default=True, nullable=False)

    person = relationship("Person", foreign_keys=[person_id])
    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    encounters = relationship("ClinicalEncounter", back_populates="patient", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Patient {self.record_number} person_id={self.person_id}>"
