import uuid
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin

# Tabla pivote M2M entre Roles y Permisos
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("core.roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("core.permissions.id", ondelete="CASCADE"), primary_key=True),
    schema="core",
)


class Role(Base, AuditMixin):
    """
    Rol en el sistema RBAC:
    - SUPERADMIN: Control total transversal
    - ADMIN_ACADEMICO: Administrador del Instituto
    - ADMIN_CLINICO: Administrador de Servicios Clínicos
    - DOCENTE: Profesor de aula teórica
    - TUTOR_CLINICO: Terapeuta docente supervisor de alumnos en práctica
    - TERAPEUTA: Profesional de salud de la clínica
    - ALUMNO: Estudiante del Instituto
    - PACIENTE: Usuario paciente portal clínico
    - FINANZAS: Personal de cobranza, tesorería y contabilidad
    """

    __tablename__ = "roles"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    scope = Column(String(50), default="GLOBAL", nullable=False, comment="GLOBAL, ACADEMIC, CLINICAL, FINANCE")
    is_active = Column(Boolean, default=True, nullable=False)

    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    user_company_roles = relationship("UserCompanyRole", back_populates="role")

    def __repr__(self):
        return f"<Role {self.code} ({self.name})>"


class Permission(Base, AuditMixin):
    """Permiso granular dentro de un módulo (ej: clinical:records:view, academic:grades:edit)."""

    __tablename__ = "permissions"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    module = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")

    def __repr__(self):
        return f"<Permission {self.code}>"


class UserCompanyRole(Base, AuditMixin):
    """
    Asociación de autorización bi-societaria.
    Determina qué rol tiene un usuario en una sociedad específica:
    Ejemplo: Un usuario puede ser 'DOCENTE' en el Instituto y 'TERAPEUTA' en Servicios Clínicos.
    """

    __tablename__ = "user_company_roles"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String(36), ForeignKey("core.roles.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="company_roles")
    company = relationship("Company")
    role = relationship("Role", back_populates="user_company_roles")

    def __repr__(self):
        return f"<UserCompanyRole user={self.user_id} company={self.company_id} role={self.role_id}>"
