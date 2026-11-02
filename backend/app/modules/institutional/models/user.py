import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class User(Base, AuditMixin):
    """
    Cuenta de acceso digital al sistema.
    Vinculada de forma única 1:1 con la persona física (core.people).
    """

    __tablename__ = "users"
    __table_args__ = {"schema": "core"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), ForeignKey("core.people.id"), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False, comment="Acceso root/auditor transversal")
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    person = relationship("Person", back_populates="user")
    company_roles = relationship("UserCompanyRole", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username} (active={self.is_active})>"
