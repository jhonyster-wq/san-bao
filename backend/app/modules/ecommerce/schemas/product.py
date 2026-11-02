from typing import Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class ProductBase(BaseModel):
    sku: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)
    description: Optional[str] = None
    price_clp: Decimal = Field(..., gt=0, description="Precio en pesos chilenos")
    promotional_price_clp: Optional[Decimal] = None
    is_digital: bool = True
    lms_course_id: Optional[str] = Field(None, description="Aula virtual vinculada para enrolamiento automático")
    stock: Optional[int] = None
    is_active: bool = True


class ProductCreate(ProductBase):
    company_id: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_clp: Optional[Decimal] = None
    promotional_price_clp: Optional[Decimal] = None
    lms_course_id: Optional[str] = None
    stock: Optional[int] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: str
    company_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
