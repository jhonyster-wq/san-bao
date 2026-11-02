import uuid
from sqlalchemy import Column, String, Boolean, Text
from app.core.database import Base
from app.core.audit import AuditMixin


class Company(Base, AuditMixin):
    """
    Representa una de las personas jurídicas que integran el ecosistema San Bao:
    1. Instituto de Medicina China Clásica SpA (Escuela)
    2. Servicios Clínicos San Bao SpA (Clínica)
    """

    __tablename__ = "companies"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rut = Column(String(12), unique=True, nullable=False, index=True, comment="RUT jurídico de la SpA")
    legal_name = Column(String(255), nullable=False, comment="Razón Social legal ante el SII")
    trade_name = Column(String(255), nullable=False, comment="Nombre de fantasía institucional")
    tax_activity = Column(String(255), nullable=True, comment="Giro comercial registrado")
    address = Column(String(255), nullable=True, comment="Domicilio tributario legal")
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Company {self.trade_name} (RUT: {self.rut})>"
