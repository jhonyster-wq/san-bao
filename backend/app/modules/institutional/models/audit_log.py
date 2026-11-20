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


class SecurityIncidentLog(Base):
    """
    Gestión de Incidentes de Seguridad y Cumplimiento Normativo (Requerimiento M):
    Registra incidentes de seguridad, intentos de acceso no autorizado, alertas de integridad y respuesta.
    """

    __tablename__ = "security_incidents"
    __table_args__ = {"schema": "audit"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_code = Column(String(50), unique=True, nullable=False, index=True, comment="Ej: SEC-INC-2026-0001")
    company_id = Column(String(36), nullable=True, index=True)
    reported_by_user_id = Column(String(36), nullable=True, index=True)
    category = Column(String(60), nullable=False, index=True, comment="UNAUTHORIZED_CLINICAL_ACCESS, KEY_ROTATION, DATA_BREACH_ATTEMPT, INTEGRITY_ALERT")
    severity = Column(String(30), default="ALTA", nullable=False, comment="BAJA, MEDIA, ALTA, CRITICA")
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    mitigation_action = Column(Text, nullable=True)
    status = Column(String(40), default="OPEN_INVESTIGATING", nullable=False, comment="OPEN_INVESTIGATING, CONTAINED, RESOLVED_CLOSED")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

