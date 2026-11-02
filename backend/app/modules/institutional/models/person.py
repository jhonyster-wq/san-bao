import uuid
from sqlalchemy import Column, String, Date, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin
from app.shared.validators.rut import ChileanRUT


class Person(Base, AuditMixin):
    """
    Entidad Maestra Transversal: Persona Natural.
    Representa al ser humano físico en el ecosistema San Bao.
    Evita la duplicación de datos: un paciente puede ser también alumno o terapeuta sin registrarse dos veces.
    """

    __tablename__ = "people"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rut = Column(String(12), unique=True, nullable=False, index=True, comment="RUT Chileno único formal")
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False, comment="Primer apellido")
    second_last_name = Column(String(100), nullable=True, comment="Segundo apellido")
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    birth_date = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True, comment="MALE, FEMALE, OTHER, PREFER_NOT_TO_SAY")
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="person", uselist=False)

    @property
    def full_name(self) -> str:
        """Nombre completo legible de la persona."""
        parts = [self.first_name, self.last_name]
        if self.second_last_name:
            parts.append(self.second_last_name)
        return " ".join(parts)

    @property
    def name(self) -> str:
        """Alias para full_name para compatibilidad transversal de esquemas."""
        return self.full_name

    @property
    def formatted_rut(self) -> str:
        """Retorna el RUT con puntos y guion."""
        return ChileanRUT.format(self.rut, with_dots=True)

    def __repr__(self):
        return f"<Person {self.full_name} ({self.rut})>"
