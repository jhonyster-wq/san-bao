from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.modules.institutional.schemas.person import PersonResponse


class PractitionerBase(BaseModel):
    license_number: Optional[str] = Field(None, max_length=100)
    specialty: str = Field("Acupuntura y Medicina Tradicional China", max_length=100)
    is_tutor: bool = Field(False, description="Acreditado como Tutor Clínico supervisor")
    is_active: bool = True


class PractitionerCreate(PractitionerBase):
    person_id: str


class PractitionerResponse(PractitionerBase):
    id: str
    person_id: str
    person: Optional[PersonResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
