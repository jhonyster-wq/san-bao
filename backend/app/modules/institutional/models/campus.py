import uuid
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class Campus(Base, AuditMixin):
    """Sedes físicas o virtuales donde operan la Escuela y la Clínica."""

    __tablename__ = "campuses"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=True, comment="Sociedad propietaria o NULL si es sede compartida")
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True, default="Santiago")
    is_active = Column(Boolean, default=True, nullable=False)

    rooms = relationship("Room", back_populates="campus", cascade="all, delete-orphan")


class Room(Base, AuditMixin):
    """Salas de clases teóricas, boxes de atención clínica u oficinas administrativas."""

    __tablename__ = "rooms"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campus_id = Column(String(36), ForeignKey("core.campuses.id"), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    room_type = Column(String(50), nullable=False, default="CLASSROOM", comment="CLASSROOM, CLINICAL_BOX, OFFICE, AUDITORIUM")
    capacity = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    campus = relationship("Campus", back_populates="rooms")
