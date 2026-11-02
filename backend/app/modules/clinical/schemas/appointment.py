from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict
from app.modules.clinical.schemas.patient import PatientResponse
from app.modules.clinical.schemas.practitioner import PractitionerResponse
from app.modules.institutional.schemas.campus import CampusResponse, RoomResponse


class AppointmentBase(BaseModel):
    patient_id: str
    practitioner_id: str
    student_id: Optional[str] = None
    campus_id: str
    room_id: str
    appointment_date: date
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM ej: 10:00")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM ej: 11:00")
    reason: Optional[str] = None
    notes: Optional[str] = None
    status: str = "SCHEDULED"


class AppointmentCreate(AppointmentBase):
    company_id: Optional[str] = None  # Si es None, toma la sociedad activa de la sesión
    patient_pack_id: Optional[str] = None  # Pack específico a descontar (opcional)
    discount_pack_session: bool = True  # Si tiene pack activo, descuenta automáticamente 1 sesión
    renew_session_price_id: Optional[str] = None  # ID de arancel/pack para renovación si es la última sesión



class AppointmentUpdate(BaseModel):
    practitioner_id: Optional[str] = None
    student_id: Optional[str] = None
    room_id: Optional[str] = None
    appointment_date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class AppointmentResponse(AppointmentBase):
    id: str
    company_id: str
    patient: Optional[PatientResponse] = None
    practitioner: Optional[PractitionerResponse] = None
    room: Optional[RoomResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
