import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from app.core.database import Base


class AuditLog(Base):
    """
    Registro inmutable de trazabilidad y auditoría.
    Almacena quién realizó qué acción, en qué sociedad, cuándo, desde qué IP y sobre qué entidad.
    Fundamental para cumplimiento normativo de la Ley 20.584 (acceso a fichas clínicas) y auditoría contable.
    """

    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "audit"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    company_id = Column(String(36), nullable=True, index=True)
    module = Column(String(50), nullable=False, index=True, comment="AUTH, ACADEMIC, CLINICAL, FINANCE, HR")
    action = Column(String(50), nullable=False, index=True, comment="CREATE, UPDATE, DELETE, LOGIN, CLINICAL_ACCESS, EXPORT")
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(100), nullable=True, index=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(Text, nullable=True, comment="Detalles en JSON o texto explicativo")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog {self.module}:{self.action} on {self.entity_type} by user {self.user_id}>"
