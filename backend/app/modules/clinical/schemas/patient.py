from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.modules.institutional.schemas.person import PersonResponse


class PatientBase(BaseModel):
    record_number: Optional[str] = Field(None, max_length=50, description="Número correlativo de ficha ej: FICH-2026-0001 (autogenerado si es None)")
    emergency_contact_name: Optional[str] = Field(None, max_length=100)
    emergency_contact_phone: Optional[str] = Field(None, max_length=50)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=50)
    blood_type: Optional[str] = Field(None, max_length=10)
    allergies: List[str] = []
    chronic_conditions: List[str] = []
    general_notes: Optional[str] = None
    is_active: bool = True


class PatientCreate(PatientBase):
    person_id: str = Field(..., description="ID de la persona registrada en core.people")


class PatientUpdate(BaseModel):
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: Optional[List[str]] = None
    chronic_conditions: Optional[List[str]] = None
    general_notes: Optional[str] = None
    is_active: Optional[bool] = None


class PatientResponse(PatientBase):
    id: str
    person_id: str
    record_number: str
    person: Optional[PersonResponse] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
