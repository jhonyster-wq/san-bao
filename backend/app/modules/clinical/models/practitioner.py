import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class Practitioner(Base, AuditMixin):
    """
    Profesional de salud acreditado de Servicios Clínicos San Bao SpA.
    Puede actuar como terapeuta tratante independiente o como Tutor Clínico supervisor de estudiantes.
    """

    __tablename__ = "practitioners"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), ForeignKey("core.people.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True)
    license_number = Column(String(100), nullable=True, comment="Registro Minsal / Superintendencia de Salud de Acupunturista")
    specialty = Column(String(100), default="Acupuntura y Medicina China", nullable=False)
    is_tutor = Column(Boolean, default=False, nullable=False, comment="Acreditado como Tutor Clínico de la Escuela")
    is_active = Column(Boolean, default=True, nullable=False)

    person = relationship("Person", foreign_keys=[person_id])
    appointments = relationship("Appointment", back_populates="practitioner")

    def __repr__(self):
        return f"<Practitioner {self.id} specialty={self.specialty} tutor={self.is_tutor}>"
