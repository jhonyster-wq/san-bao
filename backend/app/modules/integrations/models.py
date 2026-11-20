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
    source_operation_key = Column(String(120), nullable=True, index=True, comment="G: Identificador único de la operación para impedir doble emisión DTE")
    tax_classification_code = Column(String(60), nullable=True, comment="G: Clasificación tributaria aplicada")
    contingency_mode = Column(Boolean, default=False, nullable=False, comment="G: True si quedó en cola de contingencia SII")
    retry_count = Column(Integer, default=0, nullable=False, comment="G: Cantidad de reintentos de envío al SII")
    rejection_reason = Column(String(255), nullable=True, comment="G: Motivo de rechazo SII si aplica")
    related_dte_id = Column(String(36), nullable=True, comment="G: DTE original referenciado por Nota de Crédito 61")

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

    # Fase 7 (Requerimiento J): Idempotencia, Backoff Exponencial y Cola de Mensajes Fallidos (DLQ)
    idempotency_key = Column(String(120), unique=True, nullable=True, index=True, comment="J: Clave de idempotencia y control de duplicados")
    backoff_seconds = Column(Integer, default=0, nullable=False, comment="J: Backoff exponencial 2^n en segundos")
    next_retry_at = Column(String(40), nullable=True, comment="J: Fecha/hora programada para próximo reintento")
    dead_letter_queued = Column(Boolean, default=False, nullable=False, index=True, comment="J: True si pasó a Cola de Mensajes Fallidos (DLQ)")
    error_alert_sent = Column(Boolean, default=False, nullable=False, comment="J: True si se disparó alerta de error")
    payload_json = Column(Text, nullable=True, comment="J: Payload JSON completo del evento para reprocesamiento")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TransversalRestrictionRule(Base):
    """
    Motor de Reglas Configurables y Auditables para Bloqueo Transversal (Requerimiento K):
    Distingue estrictamente el tipo de acceso y responsabilidad del usuario.
    Garantiza que las restricciones financieras NUNCA impidan el acceso clínico necesario
    para la continuidad de atención de un paciente (preserve_clinical_patient_continuity = True).
    """

    __tablename__ = "transversal_restriction_rules"
    __table_args__ = {"schema": "integrations"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_code = Column(String(60), unique=True, nullable=False, index=True, comment="Ej: RULE-MOROSIDAD-30D")
    name = Column(String(180), nullable=False)
    trigger_condition = Column(String(80), nullable=False, index=True, comment="MOROSIDAD_CUOTAS, DOCUMENTO_FIRMA_PENDIENTE, SANCION_ACADEMICA")
    min_overdue_days = Column(Integer, default=30, nullable=False)
    restricted_scopes_json = Column(Text, nullable=False, comment="JSON de ámbitos restringidos ej: ['ACADEMIC_NEW_ENROLLMENT', 'ACADEMIC_CERTIFICATES']")
    preserve_clinical_patient_continuity = Column(Boolean, default=True, nullable=False, comment="K: True obligatorio — no bloquea atención clínica de pacientes")
    auto_rehabilitate_on_payment = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TransversalRestriction(Base):
    """
    Restricción Transversal Activa o Histórica con Soporte de Excepciones Autorizadas y Rehabilitación Automática (Requerimiento K).
    """

    __tablename__ = "transversal_restrictions"
    __table_args__ = {"schema": "integrations"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    person_id = Column(String(36), ForeignKey("core.people.id"), nullable=False, index=True)
    student_id = Column(String(36), nullable=True, index=True)
    rule_code = Column(String(60), nullable=False, index=True)
    origin_condition = Column(String(200), nullable=False, comment="Condición que origina el bloqueo (ej: Morosidad > 30 días en cuota #3)")
    restricted_scopes_json = Column(Text, nullable=False)
    status = Column(
        String(40),
        default="ACTIVE",
        nullable=False,
        index=True,
        comment="ACTIVE, EXCEPTION_AUTHORIZED, REHABILITATED",
    )
    applied_by = Column(String(150), nullable=False, comment="Responsable o motor que aplicó la restricción")
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Excepción autorizada con vigencia
    exception_authorized_by = Column(String(150), nullable=True)
    exception_reason = Column(String(255), nullable=True)
    exception_valid_from = Column(Date, nullable=True)
    exception_valid_until = Column(Date, nullable=True)

    # Rehabilitación automática o manual
    rehabilitated_at = Column(DateTime(timezone=True), nullable=True)
    rehabilitated_by = Column(String(150), nullable=True)
    rehabilitation_reason = Column(String(255), nullable=True)


