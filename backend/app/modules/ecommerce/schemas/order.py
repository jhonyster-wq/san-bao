from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from app.shared.validators.rut import ChileanRUT
from app.modules.ecommerce.schemas.product import ProductResponse


class OrderItemInput(BaseModel):
    product_id: str
    quantity: int = Field(1, ge=1)


class CheckoutRequest(BaseModel):
    customer_name: str = Field(..., max_length=255)
    customer_email: EmailStr
    customer_rut: str = Field(..., description="RUT chileno del comprador")
    customer_phone: Optional[str] = None
    items: List[OrderItemInput] = Field(..., min_length=1)
    payment_gateway: str = Field("WEBPAY_PLUS", description="WEBPAY_PLUS, FLOW, MERCADOPAGO")

    @field_validator("customer_rut")
    def validate_rut(cls, v: str) -> str:
        cleaned = ChileanRUT.clean(v)
        if not ChileanRUT.validate(cleaned):
            raise ValueError(f"El RUT '{v}' no es válido según algoritmo Módulo 11")
        return cleaned


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    product: Optional[ProductResponse] = None
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: str
    company_id: str
    order_number: str
    customer_name: str
    customer_email: str
    customer_rut: str
    total_amount: Decimal
    payment_status: str
    payment_gateway: str
    paid_at: Optional[datetime] = None
    items: List[OrderItemResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PaymentConfirmationRequest(BaseModel):
    gateway: str = "WEBPAY_PLUS"
    transaction_id: str
    authorization_code: Optional[str] = "AUTH-123456"
    status: str = "SUCCESS"  # SUCCESS or REJECTED


class PaymentConfirmationResponse(BaseModel):
    order: OrderResponse
    user_created: bool
    user_id: Optional[str] = None
    enrolled_courses: List[str] = []
    receipt_number: Optional[str] = None
