from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from app.modules.institutional.schemas.person import PersonResponse
from app.modules.academic.schemas.program import ProgramResponse
from app.modules.academic.schemas.period import AcademicPeriodResponse, CohortResponse


class StudentBase(BaseModel):
    student_number: str = Field(..., max_length=50)
    admission_date: date
    status: str = "REGULAR"
    notes: Optional[str] = None


class StudentCreate(BaseModel):
    person_id: str
    student_number: Optional[str] = None  # Si es nulo, el sistema lo autogenera ej: MAT-2026-0001
    admission_date: Optional[date] = None
    status: str = "REGULAR"
    notes: Optional[str] = None


class StudentResponse(StudentBase):
    id: str
    person_id: str
    person: Optional[PersonResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EnrollmentCreate(BaseModel):
    student_id: str
    program_id: str
    academic_period_id: str
    enrollment_date: Optional[date] = None
    # Parámetros para generación automática del arancel en Finanzas
    total_tuition_amount: Decimal = Field(..., description="Monto total del arancel del período en pesos CLP (ej: 2500000)")
    installments_count: int = Field(10, ge=1, le=12, description="Cantidad de cuotas pactadas")
    first_due_date: Optional[date] = None


class EnrollmentResponse(BaseModel):
    id: str
    student_id: str
    program_id: str
    academic_period_id: str
    enrollment_date: date
    status: str
    program: Optional[ProgramResponse] = None
    academic_period: Optional[AcademicPeriodResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CohortEnrollmentCreate(BaseModel):
    enrollment_id: str
    cohort_id: str


class CohortEnrollmentResponse(BaseModel):
    id: str
    enrollment_id: str
    student_id: str
    cohort_id: str
    cohort: Optional[CohortResponse] = None
    final_grade: Optional[Decimal] = None
    attendance_percentage: Decimal
    status: str
    model_config = ConfigDict(from_attributes=True)
