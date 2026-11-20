import uuid
from sqlalchemy import Column, String, Date, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship, validates
from app.core.database import Base
from app.core.audit import AuditMixin
from app.shared.validators.rut import ChileanRUT


class Person(Base, AuditMixin):
    """
    Entidad Maestra Transversal: Persona Natural / Fuente Maestra de Identidad del ERP.
    Representa al individuo o identidad única en el ecosistema San Bao para:
    Alumnos, Pacientes, Docentes, Tutores, Profesionales, Colaboradores y Proveedores.
    El RUT chileno normalizado (sin puntos y con guion, ej: 12345678-K) es la referencia cruzada.
    """

    __tablename__ = "people"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rut = Column(String(12), unique=True, nullable=False, index=True, comment="RUT Chileno único normalizado sin puntos y con guion")
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
    supplier_profile = relationship("Supplier", back_populates="person", uselist=False)

    @validates("rut")
    def _normalize_rut(self, key: str, value: str) -> str:
        """Garantiza que el RUT se almacene siempre normalizado sin puntos y con guion (ej: 12345678-K)."""
        if not value:
            return value
        cleaned = ChileanRUT.clean(str(value))
        return cleaned or str(value).strip()

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

    @property
    def canonical_rut(self) -> str:
        """Retorna el RUT normalizado sin puntos y con guion (referencia cruzada ERP/Clínica)."""
        return ChileanRUT.clean(self.rut)

    def __repr__(self):
        return f"<Person {self.full_name} ({self.rut})>"


class Supplier(Base, AuditMixin):
    """
    Rol de Proveedor vinculado a la fuente maestra de identidad del ERP (core.people).
    Permite que una misma persona natural o proveedor registrado desempeñe el rol de Proveedor
    (además de Alumno, Paciente, Docente, Tutor, Profesional o Colaborador) sin duplicar identidad.
    """

    __tablename__ = "suppliers"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), ForeignKey("core.people.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="SET NULL"), nullable=True, index=True)
    rut = Column(String(12), unique=True, nullable=False, index=True, comment="RUT normalizado sin puntos y con guion")
    business_name = Column(String(255), nullable=False, comment="Razón social o nombre comercial del proveedor")
    trade_category = Column(String(100), default="INSUMOS_CLINICOS", nullable=False, comment="INSUMOS_CLINICOS, SERVICIOS, ARRIENDO, TECNOLOGIA, HONORARIOS")
    tax_activity = Column(String(255), nullable=True, comment="Giro tributario SII")
    bank_name = Column(String(100), nullable=True)
    bank_account_type = Column(String(50), nullable=True)
    bank_account_number = Column(String(60), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    default_cost_center_code = Column(String(120), nullable=True, comment="Centro de costo por defecto para órdenes de compra")
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    person = relationship("Person", back_populates="supplier_profile", foreign_keys=[person_id])
    company = relationship("Company", foreign_keys=[company_id])

    @validates("rut")
    def _normalize_supplier_rut(self, key: str, value: str) -> str:
        if not value:
            return value
        return ChileanRUT.clean(str(value)) or str(value).strip()

