from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class EvaluationCreate(BaseModel):
    cohort_id: str
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    weight_percentage: Decimal = Field(..., ge=1, le=100, description="Ponderación porcentual (ej: 30.0)")
    evaluation_date: date


class EvaluationResponse(BaseModel):
    id: str
    cohort_id: str
    name: str
    description: Optional[str] = None
    weight_percentage: Decimal
    evaluation_date: date
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GradeRecord(BaseModel):
    student_id: str
    score: Decimal = Field(..., ge=1.0, le=7.0, description="Nota en escala chilena 1.0 a 7.0")
    feedback: Optional[str] = None

    @field_validator("score")
    def validate_score_scale(cls, v: Decimal) -> Decimal:
        if v < Decimal("1.0") or v > Decimal("7.0"):
            raise ValueError("La calificación debe estar entre 1.0 y 7.0 (escala chilena)")
        return v


class GradeResponse(BaseModel):
    id: str
    evaluation_id: str
    student_id: str
    score: Decimal
    feedback: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AttendanceItem(BaseModel):
    student_id: str
    is_present: bool = True
    is_excused: bool = False
    notes: Optional[str] = None


class BatchAttendanceCreate(BaseModel):
    cohort_id: str
    class_date: date
    attendances: List[AttendanceItem]


class ClinicalPracticeHourCreate(BaseModel):
    student_id: str
    cohort_id: Optional[str] = None
    tutor_id: str = Field(..., description="ID de la persona tutor clínico que valida las horas")
    activity_date: date
    hours_completed: int = Field(3, ge=1, le=12)
    patient_encounter_id: Optional[str] = None
    comments: Optional[str] = None


class ClinicalPracticeHourResponse(BaseModel):
    id: str
    student_id: str
    tutor_id: str
    activity_date: date
    hours_completed: int
    status: str
    comments: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
