from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class LessonCreate(BaseModel):
    module_id: str
    title: str = Field(..., max_length=255)
    content_type: str = Field("TEXT", description="VIDEO, DOCUMENT, TEXT, QUIZ")
    content_body: Optional[str] = None
    video_url: Optional[str] = None
    attachment_url: Optional[str] = None
    duration_minutes: int = 15
    order_index: int = 1
    is_published: bool = True


class LessonResponse(BaseModel):
    id: str
    module_id: str
    title: str
    content_type: str
    content_body: Optional[str] = None
    video_url: Optional[str] = None
    attachment_url: Optional[str] = None
    duration_minutes: int
    order_index: int
    is_published: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CourseModuleCreate(BaseModel):
    course_id: str
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    order_index: int = 1
    is_published: bool = True


class CourseModuleResponse(BaseModel):
    id: str
    course_id: str
    title: str
    description: Optional[str] = None
    order_index: int
    is_published: bool
    lessons: List[LessonResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LMSCourseCreate(BaseModel):
    code: str = Field(..., max_length=50)
    title: str = Field(..., max_length=255)
    summary: Optional[str] = None
    cover_image_url: Optional[str] = None
    instructor_name: Optional[str] = None
    academic_course_id: Optional[str] = None
    academic_cohort_id: Optional[str] = None
    is_published: bool = True


class LMSCourseResponse(BaseModel):
    id: str
    code: str
    title: str
    summary: Optional[str] = None
    cover_image_url: Optional[str] = None
    instructor_name: Optional[str] = None
    academic_course_id: Optional[str] = None
    is_published: bool
    modules: List[CourseModuleResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
