import uuid
from sqlalchemy import Column, String, Boolean, Date, Time, Numeric, ForeignKey, Text, Index
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

    # D.1 y D.5: Confirmación, recordatorios 48h/24h, modalidad y prestación para cierre mensual
    session_modality = Column(String(40), default="SESION_UNICA", nullable=False, comment="D.5: PRIMERA_SESION, SESION_UNICA, PACK")
    service_type = Column(String(50), default="ACUPUNTURA", nullable=False, comment="D.5: ACUPUNTURA, TUI_NA, FITOTERAPIA, OTRAS")
    amount_paid_clp = Column(Numeric(12, 0), default=35000, nullable=False, comment="D.5: Monto recaudado en la sesión (CLP)")
    confirmed_at = Column(String(40), nullable=True, comment="D.1: Fecha/hora de confirmación de atención")
    reminder_48h_sent = Column(Boolean, default=False, nullable=False, comment="D.1: Recordatorio a 48 horas enviado")
    reminder_24h_sent = Column(Boolean, default=False, nullable=False, comment="D.1: Recordatorio a 24 horas enviado")
    cancellation_reason = Column(String(255), nullable=True, comment="D.1: Motivo de cancelación o reprogramación")

    company = relationship("Company")
    patient = relationship("Patient", back_populates="appointments")
    practitioner = relationship("Practitioner", back_populates="appointments")
    student = relationship("Student")
    campus = relationship("Campus")
    room = relationship("Room")
    encounter = relationship("ClinicalEncounter", back_populates="appointment", uselist=False)

    def __repr__(self):
        return f"<Appointment {self.id} Date={self.appointment_date} {self.start_time}-{self.end_time} Status={self.status}>"
