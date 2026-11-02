from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.shared.validators.rut import ChileanRUT


class CompanyBase(BaseModel):
    legal_name: str = Field(..., max_length=255, description="Razón Social")
    trade_name: str = Field(..., max_length=255, description="Nombre de fantasía")
    tax_activity: Optional[str] = Field(None, max_length=255, description="Giro comercial")
    address: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    website: Optional[str] = Field(None, max_length=255)
    is_active: bool = True


class CompanyCreate(CompanyBase):
    rut: str = Field(..., description="RUT de la SpA (ej: 77123456-7)")

    @field_validator("rut")
    def validate_rut(cls, v: str) -> str:
        cleaned = ChileanRUT.clean(v)
        if not ChileanRUT.validate(cleaned):
            raise ValueError(f"El RUT '{v}' no es válido según algoritmo Módulo 11")
        return cleaned


class CompanyUpdate(BaseModel):
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    tax_activity: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    is_active: Optional[bool] = None


class CompanyResponse(CompanyBase):
    id: str
    rut: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
