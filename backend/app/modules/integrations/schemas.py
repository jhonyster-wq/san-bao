from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.modules.integrations.models import DTEStatus, SignatureStatus


class DTEItem(BaseModel):
    name: str
    quantity: Decimal = Field(default=Decimal("1.00"), gt=0)
    unit_price: Decimal = Field(gt=0)
    is_exempt: bool = True
    total: Decimal


class DTEDocumentCreate(BaseModel):
    company_id: str
    dte_type: int = Field(..., description="39: Boleta Afecta, 41: Boleta Exenta, 33: Factura Afecta, 34: Factura Exenta, 61: NC")
    receiver_rut: str
    receiver_name: str
    receiver_address: Optional[str] = None
    receiver_commune: Optional[str] = None
    receiver_activity: Optional[str] = None
    items: List[DTEItem]
    reference_id: Optional[UUID] = None


class DTEDocumentResponse(BaseModel):
    id: UUID
    company_id: str
    dte_type: int
    folio: int
    issue_date: date
    issuer_rut: str
    issuer_name: str
    receiver_rut: str
    receiver_name: str
    receiver_address: Optional[str] = None
    receiver_commune: Optional[str] = None
    receiver_activity: Optional[str] = None
    net_amount: Decimal
    exempt_amount: Decimal
    iva_amount: Decimal
    total_amount: Decimal
    items: List[Dict[str, Any]]
    sii_status: DTEStatus
    sii_track_id: Optional[str] = None
    digital_stamp: Optional[str] = None
    pdf_url: Optional[str] = None
    reference_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookEndpointCreate(BaseModel):
    company_id: str
    url: str
    description: Optional[str] = None
    secret: str
    subscribed_events: List[str]


class WebhookEndpointResponse(BaseModel):
    id: UUID
    company_id: str
    url: str
    description: Optional[str] = None
    subscribed_events: List[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    endpoint_id: UUID
    event_name: str
    payload: Dict[str, Any]
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    success: bool
    attempts: int
    delivered_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DigitalSignatureCreate(BaseModel):
    company_id: str
    document_type: str
    document_id: UUID
    signer_person_id: str
    document_content_to_hash: str  # Texto o representación canónica del documento a hashear
    signer_ip: Optional[str] = None


class DigitalSignatureResponse(BaseModel):
    id: UUID
    company_id: str
    document_type: str
    document_id: UUID
    signer_person_id: str
    document_hash: str
    signature_token: str
    signer_ip: Optional[str] = None
    status: SignatureStatus
    signed_at: datetime

    model_config = ConfigDict(from_attributes=True)
