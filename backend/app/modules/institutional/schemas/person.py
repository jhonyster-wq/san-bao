from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from app.shared.validators.rut import ChileanRUT


class PersonBase(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100, description="Primer apellido")
    second_last_name: Optional[str] = Field(None, max_length=100, description="Segundo apellido")
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=50)
    birth_date: Optional[date] = None
    gender: Optional[str] = Field(None, description="MALE, FEMALE, OTHER, PREFER_NOT_TO_SAY")
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    is_active: bool = True


class PersonCreate(PersonBase):
    rut: str = Field(..., description="RUT de la persona (ej: 12345678-5)")

    @field_validator("rut")
    def validate_rut(cls, v: str) -> str:
        cleaned = ChileanRUT.clean(v)
        if not ChileanRUT.validate(cleaned):
            raise ValueError(f"El RUT '{v}' no es válido según algoritmo Módulo 11")
        return cleaned


class PersonUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    second_last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    is_active: Optional[bool] = None


class PersonResponse(PersonBase):
    id: str
    rut: str
    full_name: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
