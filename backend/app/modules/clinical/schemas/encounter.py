from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from app.modules.clinical.schemas.patient import PatientResponse
from app.modules.clinical.schemas.practitioner import PractitionerResponse


class TongueDiagnosis(BaseModel):
    body_color: Optional[str] = Field(None, description="Pálido, Rosado normal, Rojo, Rojo oscuro, Violáceo")
    body_shape: Optional[str] = Field(None, description="Normal, Hinchada, Delgada, Marcas dentales, Fisuras")
    coating_color: Optional[str] = Field(None, description="Blanca, Amarilla, Gris, Negra")
    coating_thickness: Optional[str] = Field(None, description="Fina, Gruesa, Pelada (geográfica)")
    coating_moisture: Optional[str] = Field(None, description="Normal, Seca, Resbaladiza")
    sublingual_veins: Optional[str] = Field(None, description="Normales, Dilatadas, Tortuosas oscuras")


class PulsePosition(BaseModel):
    cun: Optional[str] = Field(None, description="Posición distal (Corazón/Pulmón)")
    guan: Optional[str] = Field(None, description="Posición media (Hígado/Bazo)")
    chi: Optional[str] = Field(None, description="Posición proximal (Riñón)")


class PulseDiagnosis(BaseModel):
    left_wrist: Optional[PulsePosition] = None
    right_wrist: Optional[PulsePosition] = None
    general_qualities: List[str] = Field(default=[], description="Superficial, Profundo, Lento, Rápido, Tenso, Resbaladizo, Débil, etc.")
    rate_bpm: Optional[int] = Field(None, description="Pulsaciones por minuto")


class TraditionalAnamnesis(BaseModel):
    sleep: Optional[str] = None
    appetite_digestion: Optional[str] = None
    thirst: Optional[str] = None
    temperature_sensation: Optional[str] = Field(None, description="Prefiere frío, calor, aversión al viento")
    sweating: Optional[str] = None
    excretion: Optional[str] = None
    pain_characteristics: Optional[str] = None
    emotional_state: Optional[str] = None
    menstruation: Optional[str] = None


class TreatmentPlan(BaseModel):
    acupuncture_points: List[str] = Field(default=[], description="Puntos seleccionados ej: ['E36', 'B6', 'IG4', 'H3']")
    needle_technique: Optional[str] = Field(None, description="Tonificación, Dispersión, Armonización")
    moxibustion: Optional[Union[str, List[str]]] = None
    cupping: Optional[Union[str, List[str]]] = None
    auriculotherapy: Optional[Union[str, List[str]]] = None
    herbal_formula: Optional[Union[str, List[str]]] = None


class EncounterCreate(BaseModel):
    patient_id: str
    appointment_id: Optional[str] = None
    practitioner_id: str
    student_id: Optional[str] = None
    reason_for_consultation: str
    current_illness_history: Optional[str] = None
    traditional_anamnesis: Optional[TraditionalAnamnesis] = None
    tongue_diagnosis: Optional[TongueDiagnosis] = None
    pulse_diagnosis: Optional[PulseDiagnosis] = None
    zang_fu_syndrome: Optional[str] = Field(None, description="Síndrome diagnosticado ej: Insuficiencia de Qi de Bazo")
    eight_principles: Optional[Dict[str, Any]] = None
    therapeutic_principle: Optional[str] = None
    treatment_plan: Optional[TreatmentPlan] = None
    recommendations: Optional[str] = None


class EncounterUpdate(BaseModel):
    reason_for_consultation: Optional[str] = None
    current_illness_history: Optional[str] = None
    traditional_anamnesis: Optional[TraditionalAnamnesis] = None
    tongue_diagnosis: Optional[TongueDiagnosis] = None
    pulse_diagnosis: Optional[PulseDiagnosis] = None
    zang_fu_syndrome: Optional[str] = None
    eight_principles: Optional[Dict[str, Any]] = None
    therapeutic_principle: Optional[str] = None
    treatment_plan: Optional[TreatmentPlan] = None
    recommendations: Optional[str] = None
    tutor_feedback: Optional[str] = None
    tutor_grade: Optional[Decimal] = None


class EncounterSignRequest(BaseModel):
    tutor_feedback: Optional[str] = Field(None, description="Retroalimentación docente para el alumno")
    tutor_grade: Optional[Decimal] = Field(None, ge=1.0, le=7.0, description="Nota de la atención supervisada")
    hours_to_credit: int = Field(3, ge=1, le=8, description="Horas de práctica clínica a certificar para el estudiante")


class EncounterResponse(BaseModel):
    id: str
    patient_id: str
    appointment_id: Optional[str] = None
    practitioner_id: str
    student_id: Optional[str] = None
    encounter_date: datetime
    reason_for_consultation: str
    current_illness_history: Optional[str] = None
    traditional_anamnesis: Optional[Dict[str, Any]] = None
    tongue_diagnosis: Optional[Dict[str, Any]] = None
    pulse_diagnosis: Optional[Dict[str, Any]] = None
    zang_fu_syndrome: Optional[str] = None
    therapeutic_principle: Optional[str] = None
    treatment_plan: Optional[Dict[str, Any]] = None
    recommendations: Optional[str] = None
    tutor_feedback: Optional[str] = None
    tutor_grade: Optional[Decimal] = None
    status: str
    signed_at: Optional[datetime] = None
    signed_by: Optional[str] = None
    patient: Optional[PatientResponse] = None
    practitioner: Optional[PractitionerResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
