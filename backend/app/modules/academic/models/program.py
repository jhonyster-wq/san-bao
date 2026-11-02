import uuid
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, Numeric, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class Program(Base, AuditMixin):
    """
    Carrera o Programa de Formación impartido por el Instituto de Medicina China Clásica SpA.
    Ejemplos:
    - Formación Profesional en Acupuntura y Medicina Tradicional China
    - Diplomado en Fitoterapia Tradicional China
    - Curso de Especialización en Tuina y Ventosas
    """

    __tablename__ = "programs"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    program_type = Column(String(50), default="DIPLOMADO", nullable=False, comment="DIPLOMADO, CURSO, FORMACION_CONTINUA, CARRERA")
    modality = Column(String(50), default="PRESENCIAL", nullable=False, comment="Diplomado: PRESENCIAL, SEMIPRESENCIAL | Curso: PRESENCIAL, VIRTUAL, HIBRIDO")
    degree_title = Column(String(255), nullable=True, comment="Título o Diploma otorgado al egreso")
    description = Column(Text, nullable=True)
    total_semesters = Column(Integer, default=6, nullable=False)
    total_theoretical_hours = Column(Integer, default=0, nullable=False)
    total_practical_hours = Column(Integer, default=0, nullable=False)
    min_clinical_hours = Column(Integer, default=0, nullable=False, comment="Horas de práctica clínica obligatorias")
    is_active = Column(Boolean, default=True, nullable=False)

    curriculums = relationship("Curriculum", back_populates="program", cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="program", foreign_keys="Course.program_id")

    def __repr__(self):
        return f"<Program {self.code}: {self.name}>"


class Curriculum(Base, AuditMixin):
    """Malla Curricular o Plan de Estudios versionado de un programa (ej: Malla 2024, Malla 2026)."""

    __tablename__ = "curriculums"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    program_id = Column(String(36), ForeignKey("academic.programs.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)
    version_name = Column(String(100), nullable=False, default="Plan Vigente")
    effective_year = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    program = relationship("Program", back_populates="curriculums")
    courses = relationship("CurriculumCourse", back_populates="curriculum", cascade="all, delete-orphan")


class Course(Base, AuditMixin):
    """
    Catálogo de Asignaturas teóricas, prácticas y clínicas.
    Ejemplos:
    - Fundamentos de Medicina China Clásica
    - Diagnóstico por Pulso y Lengua
    - Puntos y Meridianos Acupunturales I
    - Práctica Clínica Supervisada I
    """

    __tablename__ = "courses"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    program_id = Column(String(36), ForeignKey("academic.programs.id", ondelete="SET NULL"), nullable=True, index=True, comment="Programa o Curso al que pertenece")
    teacher_id = Column(String(36), ForeignKey("core.people.id", ondelete="SET NULL"), nullable=True, index=True, comment="Docente titular asignado a la asignatura (Registro RRHH Activo)")
    co_teacher_id = Column(String(36), ForeignKey("core.people.id", ondelete="SET NULL"), nullable=True, index=True, comment="Segundo docente / co-docente asignado a la asignatura (Registro RRHH Activo)")
    semester = Column(Integer, default=1, nullable=False, comment="Semestre o nivel dentro de la malla curricular (1, 2, 3...)")
    theoretical_hours = Column(Integer, default=0, nullable=False)
    practical_hours = Column(Integer, default=0, nullable=False)
    clinical_hours = Column(Integer, default=0, nullable=False, comment="Horas de atención con pacientes")
    credits = Column(Integer, default=4, nullable=False)
    is_clinical_practice = Column(Boolean, default=False, nullable=False, comment="Indica si es asignatura de campo clínico")
    is_active = Column(Boolean, default=True, nullable=False)

    program = relationship("Program", back_populates="courses", foreign_keys=[program_id])
    teacher = relationship("Person", foreign_keys=[teacher_id])
    co_teacher = relationship("Person", foreign_keys=[co_teacher_id])

    def __repr__(self):
        return f"<Course {self.code}: {self.name}>"


class CurriculumCourse(Base, AuditMixin):
    """Asociación de una asignatura a una malla específica, definiendo semestre y prerrequisito (Normalizada 3NF/BCNF)."""

    __tablename__ = "curriculum_courses"
    __table_args__ = (
        UniqueConstraint("curriculum_id", "course_id", name="uq_curriculum_course"),
        Index("ix_curriculum_courses_curr_sem", "curriculum_id", "semester"),
        {"schema": "academic"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    curriculum_id = Column(String(36), ForeignKey("academic.curriculums.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(String(36), ForeignKey("academic.courses.id", ondelete="CASCADE"), nullable=False, index=True)
    semester = Column(Integer, nullable=False, comment="Semestre dentro de la malla (1, 2, 3...)")
    is_mandatory = Column(Boolean, default=True, nullable=False)
    prerequisite_course_id = Column(String(36), ForeignKey("academic.courses.id"), nullable=True, index=True)

    curriculum = relationship("Curriculum", back_populates="courses")
    course = relationship("Course", foreign_keys=[course_id])
    prerequisite = relationship("Course", foreign_keys=[prerequisite_course_id])
