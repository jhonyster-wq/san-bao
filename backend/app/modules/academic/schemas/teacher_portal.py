from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import date


class TeacherCourseResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    program_id: Optional[str] = None
    program_name: Optional[str] = None
    program_type: Optional[str] = None
    cohort_id: Optional[str] = None
    cohort_name: Optional[str] = None
    theoretical_hours: int = 0
    practical_hours: int = 0
    clinical_hours: int = 0
    credits: int = 4
    enrolled_students_count: int = 0
    evaluations_count: int = 0
    contents_count: int = 0
    average_attendance_pct: float = 100.0
    average_grade: Optional[float] = None
    is_active: bool = True


class EvaluationCreateRequest(BaseModel):
    name: str = Field(..., description="Nombre de la evaluación (ej: Certamen 1)")
    weight_percentage: float = Field(..., ge=1.0, le=100.0, description="Ponderación porcentual (ej: 25.0)")
    evaluation_date: date = Field(..., description="Fecha de aplicación de la evaluación")
    description: Optional[str] = None
    cohort_id: Optional[str] = None


class TeacherGradeEntryRequest(BaseModel):
    evaluation_id: str
    student_id: str
    score: float = Field(..., ge=1.0, le=7.0, description="Calificación en escala chilena 1.0 a 7.0")
    feedback: Optional[str] = None


class AttendanceRecordItem(BaseModel):
    student_id: str
    status: str = Field(default="PRESENTE", description="PRESENTE, AUSENTE, JUSTIFICADO, ATRASO")
    notes: Optional[str] = None


class BatchAttendanceSaveRequest(BaseModel):
    class_date: date = Field(..., description="Fecha de la sesión de clase")
    class_number: int = Field(default=1, ge=1, description="Número de sesión de clase")
    session_topic: str = Field(..., description="Tema o materia abordada en la clase")
    cohort_id: Optional[str] = None
    records: List[AttendanceRecordItem] = Field(..., description="Lista de asistencias por alumno")


class ContentUploadRequest(BaseModel):
    class_number: int = Field(default=1, ge=1, description="Número correlativo de clase (1, 2, 3...)")
    class_title: str = Field(..., description="Título o tema de la clase")
    resource_title: str = Field(..., description="Nombre descriptivo del material o guía")
    resource_type: str = Field(
        default="DOCUMENTO_PDF",
        description="DOCUMENTO_PDF, PRESENTACION_PPT, VIDEO_CLASE, LECTURA_COMPLEMENTARIA, ENLACE_WEB",
    )
    attachment_url: Optional[str] = Field(default=None, description="URL o ruta de descarga del archivo")
    description: Optional[str] = Field(default=None, description="Instrucciones pedagógicas para el alumno")
    file_size_text: Optional[str] = Field(default="PDF 2.4 MB", description="Tamaño y formato legible")
    cohort_id: Optional[str] = None
    is_published: bool = Field(default=True, description="Visibilidad para los estudiantes")
