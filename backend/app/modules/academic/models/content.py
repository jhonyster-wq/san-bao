import uuid
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class CourseClassContent(Base, AuditMixin):
    """
    Contenido, guías pedagógicas, diapositivas y grabaciones subidas por el docente organizadas por curso y clase.
    """

    __tablename__ = "course_class_contents"
    __table_args__ = {"schema": "academic"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = Column(String(36), ForeignKey("academic.courses.id", ondelete="CASCADE"), nullable=False, index=True)
    cohort_id = Column(String(36), ForeignKey("academic.cohorts.id", ondelete="SET NULL"), nullable=True, index=True)
    class_number = Column(Integer, default=1, nullable=False, comment="Número correlativo de clase (1, 2, 3...)")
    class_title = Column(String(255), nullable=False, comment="Tema o título de la sesión de clase")
    resource_title = Column(String(255), nullable=False, comment="Nombre del archivo o recurso pedagógico")
    resource_type = Column(
        String(50),
        default="DOCUMENTO_PDF",
        nullable=False,
        comment="DOCUMENTO_PDF, PRESENTACION_PPT, VIDEO_CLASE, LECTURA_COMPLEMENTARIA, ENLACE_WEB",
    )
    attachment_url = Column(String(500), nullable=True, comment="Ruta local o URL al archivo/grabación")
    description = Column(Text, nullable=True, comment="Orientaciones docentes y descripción del material")
    file_size_text = Column(String(50), nullable=True, default="PDF 2.4 MB")
    uploaded_by_id = Column(String(36), ForeignKey("core.users.id", ondelete="SET NULL"), nullable=True)
    uploaded_by_name = Column(String(150), nullable=True)
    is_published = Column(Boolean, default=True, nullable=False)

    course = relationship("Course", backref="class_contents")

    def __repr__(self):
        return f"<CourseClassContent Clase {self.class_number}: {self.resource_title}>"
