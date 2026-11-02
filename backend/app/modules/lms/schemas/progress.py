from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class LMSEnrollmentResponse(BaseModel):
    id: str
    course_id: str
    user_id: str
    progress_percentage: Decimal
    status: str
    completed_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LessonProgressUpdate(BaseModel):
    lesson_id: str
    is_completed: bool = True


class AssignmentCreate(BaseModel):
    lesson_id: str
    title: str = Field(..., max_length=255)
    instructions: str
    max_score: Decimal = Decimal("7.0")
    due_date: Optional[datetime] = None


class AssignmentResponse(BaseModel):
    id: str
    lesson_id: str
    title: str
    instructions: str
    max_score: Decimal
    due_date: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SubmissionCreate(BaseModel):
    assignment_id: str
    content_text: Optional[str] = None
    attachment_url: Optional[str] = None


class SubmissionGradeRequest(BaseModel):
    score: Decimal = Field(..., ge=1.0, le=7.0, description="Nota en escala 1.0 a 7.0")
    feedback: Optional[str] = None


class SubmissionResponse(BaseModel):
    id: str
    assignment_id: str
    user_id: str
    content_text: Optional[str] = None
    attachment_url: Optional[str] = None
    submitted_at: datetime
    score: Optional[Decimal] = None
    feedback: Optional[str] = None
    status: str
    model_config = ConfigDict(from_attributes=True)
