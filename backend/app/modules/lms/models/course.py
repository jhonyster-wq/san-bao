import uuid
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class LMSCourse(Base, AuditMixin):
    """
    Curso o Aula Virtual en la plataforma de aprendizaje (LMS) San Bao.
    Puede estar vinculado a una asignatura curricular de la Escuela o ser un curso abierto/diplomado.
    """

    __tablename__ = "lms_courses"
    __table_args__ = {"schema": "lms"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    academic_course_id = Column(String(36), ForeignKey("academic.courses.id", ondelete="SET NULL"), nullable=True, index=True)
    academic_cohort_id = Column(String(36), ForeignKey("academic.cohorts.id", ondelete="SET NULL"), nullable=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    cover_image_url = Column(String(500), nullable=True)
    instructor_name = Column(String(100), nullable=True)
    is_published = Column(Boolean, default=True, nullable=False)

    modules = relationship("CourseModule", back_populates="course", cascade="all, delete-orphan", order_by="CourseModule.order_index")
    enrollments = relationship("LMSEnrollment", back_populates="course", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LMSCourse {self.code}: {self.title}>"


class CourseModule(Base, AuditMixin):
    """Unidad o Módulo didáctico dentro de un curso (ej: Unidad 1: Puntos Shu Antiguos)."""

    __tablename__ = "course_modules"
    __table_args__ = {"schema": "lms"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = Column(String(36), ForeignKey("lms.lms_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=1, nullable=False)
    is_published = Column(Boolean, default=True, nullable=False)

    course = relationship("LMSCourse", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module", cascade="all, delete-orphan", order_by="Lesson.order_index")

    def __repr__(self):
        return f"<CourseModule #{self.order_index} {self.title}>"


class Lesson(Base, AuditMixin):
    """Lección o clase individual: video explicativo, lectura, documento PDF o actividad."""

    __tablename__ = "lessons"
    __table_args__ = {"schema": "lms"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    module_id = Column(String(36), ForeignKey("lms.course_modules.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content_type = Column(String(50), default="TEXT", nullable=False, comment="VIDEO, DOCUMENT, TEXT, QUIZ")
    content_body = Column(Text, nullable=True, comment="Contenido en Markdown, HTML o URL de video")
    video_url = Column(String(500), nullable=True)
    attachment_url = Column(String(500), nullable=True)
    duration_minutes = Column(Integer, default=15, nullable=False)
    order_index = Column(Integer, default=1, nullable=False)
    is_published = Column(Boolean, default=True, nullable=False)

    module = relationship("CourseModule", back_populates="lessons")
    assignments = relationship("Assignment", back_populates="lesson", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lesson #{self.order_index} {self.title}>"
