import uuid
from sqlalchemy import Column, String, Date, Time, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class Appointment(Base, AuditMixin):
    """
    Reserva de hora para atención en Servicios Clínicos San Bao SpA.
    Asocia paciente, terapeuta, box clínico y opcionalmente alumno en práctica supervisada.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_campus_date_status", "campus_id", "appointment_date", "status"),
        Index("ix_appointments_practitioner_date", "practitioner_id", "appointment_date"),
        {"schema": "clinical"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("clinical.patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    practitioner_id = Column(String(36), ForeignKey("clinical.practitioners.id", ondelete="RESTRICT"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("academic.students.id", ondelete="SET NULL"), nullable=True, index=True, comment="Alumno en práctica asignado")
    campus_id = Column(String(36), ForeignKey("core.campuses.id"), nullable=False, index=True)
    room_id = Column(String(36), ForeignKey("core.rooms.id"), nullable=False, index=True, comment="Box de atención clínica")
    appointment_date = Column(Date, nullable=False, index=True)
    start_time = Column(String(5), nullable=False, comment="Formato HH:MM ej: 10:00")
    end_time = Column(String(5), nullable=False, comment="Formato HH:MM ej: 11:00")
    reason = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="SCHEDULED", nullable=False, comment="SCHEDULED, CONFIRMED, WAITING, IN_CONSULTATION, COMPLETED, CANCELLED, NO_SHOW")

    company = relationship("Company")
    patient = relationship("Patient", back_populates="appointments")
    practitioner = relationship("Practitioner", back_populates="appointments")
    student = relationship("Student")
    campus = relationship("Campus")
    room = relationship("Room")
    encounter = relationship("ClinicalEncounter", back_populates="appointment", uselist=False)

    def __repr__(self):
        return f"<Appointment {self.id} Date={self.appointment_date} {self.start_time}-{self.end_time} Status={self.status}>"
