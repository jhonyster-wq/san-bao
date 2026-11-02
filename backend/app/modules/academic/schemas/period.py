from typing import Optional, List, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict
from app.modules.academic.schemas.program import CourseResponse


class AcademicPeriodBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    year: int
    semester_number: int = 1
    start_date: date
    end_date: date
    is_enrollment_open: bool = True
    is_active: bool = True


class AcademicPeriodCreate(AcademicPeriodBase):
    pass


class AcademicPeriodResponse(AcademicPeriodBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CohortBase(BaseModel):
    course_id: str
    academic_period_id: str
    code: str = Field("SECC-01", max_length=50)
    teacher_id: Optional[str] = None
    campus_id: Optional[str] = None
    room_id: Optional[str] = None
    schedule: Optional[Any] = None
    quota: int = 30
    status: str = "OPEN"


class CohortCreate(CohortBase):
    pass


class CohortResponse(CohortBase):
    id: str
    course: Optional[CourseResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
