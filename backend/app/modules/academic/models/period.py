import uuid
from sqlalchemy import Column, String, Boolean, Integer, Date, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class AcademicPeriod(Base, AuditMixin):
    """
    Período o Semestre Académico (ej: 2026-1, 2026-2).
    Controla aperturas de matrícula y vigencias.
    """

    __tablename__ = "academic_periods"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    semester_number = Column(Integer, nullable=False, default=1)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_enrollment_open = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    cohorts = relationship("Cohort", back_populates="academic_period")

    def __repr__(self):
        return f"<AcademicPeriod {self.code}: {self.name}>"


class Cohort(Base, AuditMixin):
    """
    Sección o cohorte de una asignatura específica en un período académico.
    Asocia docente (profesor de aula o tutor clínico), sala/box, y horario.
    """

    __tablename__ = "cohorts"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = Column(String(36), ForeignKey("academic.courses.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_period_id = Column(String(36), ForeignKey("academic.periods.id" if False else "academic.academic_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(String(36), ForeignKey("core.people.id"), nullable=True, index=True, comment="Docente o Tutor Clínico asignado")
    campus_id = Column(String(36), ForeignKey("core.campuses.id"), nullable=True, index=True)
    room_id = Column(String(36), ForeignKey("core.rooms.id"), nullable=True)
    code = Column(String(50), nullable=False, index=True, comment="Código de sección (ej: SECC-01)")
    schedule = Column(JSON, nullable=True, comment="Días y bloques horarios ej: [{'day': 'Lunes', 'start': '18:30', 'end': '21:30'}]")
    quota = Column(Integer, default=30, nullable=False)
    status = Column(String(50), default="OPEN", nullable=False, comment="OPEN, IN_PROGRESS, CLOSED, CANCELLED")

    course = relationship("Course")
    academic_period = relationship("AcademicPeriod", back_populates="cohorts")
    teacher = relationship("Person", foreign_keys=[teacher_id])
    campus = relationship("Campus", foreign_keys=[campus_id])
    room = relationship("Room", foreign_keys=[room_id])
    enrollments = relationship("CohortEnrollment", back_populates="cohort", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="cohort", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Cohort {self.code} Course: {self.course_id}>"
