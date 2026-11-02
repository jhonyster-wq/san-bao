import uuid
import enum
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Date,
    Numeric,
    Integer,
    ForeignKey,
    Enum,
    Text,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DTEType(int, enum.Enum):
    FACTURA_AFECTA = 33
    FACTURA_EXENTA = 34
    BOLETA_AFECTA = 39
    BOLETA_EXENTA = 41
    NOTA_CREDITO = 61


class DTEStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ACCEPTED_WITH_REPAIRS = "ACCEPTED_WITH_REPAIRS"


class SignatureStatus(str, enum.Enum):
    PENDING = "PENDING"
    SIGNED = "SIGNED"
    REVOKED = "REVOKED"


class DTEDocument(Base):
    """Documento Tributario Electrónico (DTE) oficial para el SII (Chile)."""
    __tablename__ = "dte_documents"
    __table_args__ = (
        UniqueConstraint("company_id", "dte_type", "folio", name="uq_dte_company_type_folio"),
        Index("ix_dte_company_date", "company_id", "issue_date"),
        {"schema": "integrations"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    dte_type = Column(Integer, nullable=False, index=True)  # 39, 41, 33, 34, 61
    folio = Column(Integer, nullable=False, index=True)
    issue_date = Column(Date, nullable=False)
    
    # Emisor
    issuer_rut = Column(String(20), nullable=False)
    issuer_name = Column(String(255), nullable=False)
    
    # Receptor
    receiver_rut = Column(String(20), nullable=False)
    receiver_name = Column(String(255), nullable=False)
    receiver_address = Column(String(255), nullable=True)
    receiver_commune = Column(String(100), nullable=True)
    receiver_activity = Column(String(255), nullable=True)  # Giro

    # Montos
    net_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    exempt_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    iva_amount = Column(Numeric(12, 2), default=0.00, nullable=False)  # 19% si aplica
    total_amount = Column(Numeric(12, 2), nullable=False)
    
    # Detalle de líneas
    items = Column(JSON, nullable=False)  # [{"name": "...", "qty": 1, "unit_price": 45000, "total": 45000}]
    
    # Datos SII
    sii_status = Column(Enum(DTEStatus), default=DTEStatus.ACCEPTED, nullable=False)
    sii_track_id = Column(String(50), nullable=True)
    digital_stamp = Column(Text, nullable=True)  # Timbre Electrónico DTE (TED)
    pdf_url = Column(String(255), nullable=True)
    reference_id = Column(UUID(as_uuid=True), nullable=True)  # e.g. order_id, installment_id

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class WebhookEndpoint(Base):
    """Configuración de endpoints para webhooks salientes hacia sistemas externos."""
    __tablename__ = "webhook_endpoints"
    __table_args__ = {"schema": "integrations"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    description = Column(String(255), nullable=True)
    secret = Column(String(255), nullable=False)
    subscribed_events = Column(JSON, nullable=False)  # ["payment.confirmed", "clinical.encounter_signed"]
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    deliveries = relationship("WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan")


class WebhookDelivery(Base):
    """Bitácora inmutable de entrega de eventos webhook."""
    __tablename__ = "webhook_deliveries"
    __table_args__ = {"schema": "integrations"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id = Column(UUID(as_uuid=True), ForeignKey("integrations.webhook_endpoints.id"), nullable=False, index=True)
    event_name = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    success = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=1, nullable=False)
    delivered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")


class DigitalSignature(Base):
    """Registro legal de firma electrónica simple y avanzada de documentos institucionales."""
    __tablename__ = "digital_signatures"
    __table_args__ = {"schema": "integrations"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    document_type = Column(String(100), nullable=False)  # CONTRATO_DOCENTE, PAGARE_ARANCEL, CONSENTIMIENTO_CLINICO
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    signer_person_id = Column(String(36), ForeignKey("core.people.id"), nullable=False)
    
    document_hash = Column(String(64), nullable=False)  # SHA-256
    signature_token = Column(String(128), nullable=False, unique=True)
    signer_ip = Column(String(45), nullable=True)
    status = Column(Enum(SignatureStatus), default=SignatureStatus.SIGNED, nullable=False)
    signed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    signer = relationship("Person")


class SystemNotification(Base):
    """Motor institucional de notificaciones transaccionales (Email HTML, WhatsApp/SMS y Portal)."""
    __tablename__ = "notifications"
    __table_args__ = {"schema": "integrations"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    channel = Column(String(30), default="EMAIL_HTML", nullable=False)  # EMAIL_HTML, WHATSAPP, PORTAL_ALERT
    source_module = Column(String(60), nullable=False)  # ACADEMICO, FINANZAS, CLINICA, RRHH, ECOMMERCE
    recipient_name = Column(String(150), nullable=False)
    recipient_contact = Column(String(150), nullable=False)
    subject = Column(String(255), nullable=False)
    body_preview = Column(Text, nullable=True)
    related_entity_ref = Column(String(100), nullable=True)
    status = Column(String(30), default="DELIVERED", nullable=False)  # DELIVERED, PENDING, FAILED
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApprovalWorkflow(Base):
    """Flujos formales de aprobación y visación inter-áreas (Académico, Clínica, RRHH, Finanzas)."""
    __tablename__ = "approval_workflows"
    __table_args__ = {"schema": "integrations"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    workflow_type = Column(String(60), nullable=False)  # PRACTICA_CLINICA, HONORARIOS_DOCENTES, PRESUPUESTO_FINANZAS, CONGELAMIENTO_ACADEMICO, DESPACHO_INSUMOS
    title = Column(String(255), nullable=False)
    origin_area = Column(String(80), nullable=False)
    approver_area = Column(String(80), nullable=False)
    requested_by = Column(String(120), nullable=False)
    approved_by = Column(String(120), nullable=True)
    reference_code = Column(String(80), nullable=True)
    amount_clp = Column(Numeric(12, 0), default=0, nullable=False)
    status = Column(String(30), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)


class IntegrationOperationLog(Base):
    """Bitácora inmutable de operaciones, comunicación inter-modular, trazabilidad y control de reintentos."""
    __tablename__ = "operation_logs"
    __table_args__ = {"schema": "integrations"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    operation_code = Column(String(60), unique=True, nullable=False, index=True)
    source_module = Column(String(60), nullable=False)
    target_module = Column(String(60), nullable=False)
    event_name = Column(String(120), nullable=False, index=True)
    entity_reference = Column(String(120), nullable=True)
    actor_user = Column(String(100), default="system.orchestrator@sanbao.cl", nullable=False)
    status = Column(String(30), default="SUCCESS", nullable=False)  # SUCCESS, ERROR_RETRYING, RECOVERED, FAILED
    attempts = Column(Integer, default=1, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    latency_ms = Column(Integer, default=42, nullable=False)
    error_detail = Column(Text, nullable=True)
    trace_hash = Column(String(64), nullable=False)
    payload_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

