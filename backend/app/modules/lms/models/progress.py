import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class LMSEnrollment(Base, AuditMixin):
    """Matrícula o acceso activo de un usuario al aula virtual de un curso."""

    __tablename__ = "lms_enrollments"
    __table_args__ = {"schema": "lms"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = Column(String(36), ForeignKey("lms.lms_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False, index=True)
    progress_percentage = Column(Numeric(5, 2), default=0.0, nullable=False)
    status = Column(String(50), default="ACTIVE", nullable=False, comment="ACTIVE, COMPLETED, SUSPENDED")
    completed_at = Column(DateTime(timezone=True), nullable=True)

    course = relationship("LMSCourse", back_populates="enrollments")
    user = relationship("User")

    def __repr__(self):
        return f"<LMSEnrollment user={self.user_id} course={self.course_id} progress={self.progress_percentage}%>"


class LessonProgress(Base, AuditMixin):
    """Marca de avance de cada lección por alumno."""

    __tablename__ = "lesson_progress"
    __table_args__ = {"schema": "lms"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lesson_id = Column(String(36), ForeignKey("lms.lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_completed = Column(Boolean, default=True, nullable=False)
    completed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    lesson = relationship("Lesson")
    user = relationship("User")


class Assignment(Base, AuditMixin):
    """Actividad o tarea asignada en una lección."""

    __tablename__ = "assignments"
    __table_args__ = {"schema": "lms"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lesson_id = Column(String(36), ForeignKey("lms.lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    instructions = Column(Text, nullable=False)
    max_score = Column(Numeric(4, 1), default=7.0, nullable=False, comment="Puntaje máximo (ej: 7.0)")
    due_date = Column(DateTime(timezone=True), nullable=True)

    lesson = relationship("Lesson", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")


class Submission(Base, AuditMixin):
    """Entrega de tarea realizada por un estudiante."""

    __tablename__ = "submissions"
    __table_args__ = {"schema": "lms"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assignment_id = Column(String(36), ForeignKey("lms.assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False, index=True)
    content_text = Column(Text, nullable=True)
    attachment_url = Column(String(500), nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    score = Column(Numeric(3, 1), nullable=True, comment="Calificación asignada (1.0 a 7.0)")
    feedback = Column(Text, nullable=True)
    graded_by = Column(String(36), ForeignKey("core.users.id"), nullable=True)
    status = Column(String(50), default="SUBMITTED", nullable=False, comment="SUBMITTED, GRADED")

    assignment = relationship("Assignment", back_populates="submissions")
    student_user = relationship("User", foreign_keys=[user_id])
