from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class TeacherSummary(BaseModel):
    id: str
    name: Optional[str] = None
    rut: Optional[str] = None
    email: Optional[str] = None
    specialty: Optional[str] = None
    employee_number: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    hr_status: str = "ACTIVO EN RRHH"
    model_config = ConfigDict(from_attributes=True)


class CourseBase(BaseModel):
    code: str = Field(..., max_length=50, description="Código de asignatura ej: MTC-101")
    name: str = Field(..., max_length=255, description="Nombre de la asignatura")
    description: Optional[str] = None
    program_id: Optional[str] = Field(None, description="ID del Programa o Curso al que pertenece")
    teacher_id: Optional[str] = Field(None, description="ID del Docente titular 1 asignado (Registro RRHH Activo)")
    co_teacher_id: Optional[str] = Field(None, description="ID del Segundo Docente / Co-docente asignado (Registro RRHH Activo)")
    semester: int = Field(1, ge=1, le=12, description="Semestre o nivel en la malla curricular")
    theoretical_hours: int = Field(0, ge=0)
    practical_hours: int = Field(0, ge=0)
    clinical_hours: int = Field(0, ge=0)
    credits: int = Field(4, ge=0)
    is_clinical_practice: bool = False
    is_active: bool = True


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    program_id: Optional[str] = None
    teacher_id: Optional[str] = None
    co_teacher_id: Optional[str] = None
    semester: Optional[int] = Field(None, ge=1, le=12)
    theoretical_hours: Optional[int] = Field(None, ge=0)
    practical_hours: Optional[int] = Field(None, ge=0)
    clinical_hours: Optional[int] = Field(None, ge=0)
    credits: Optional[int] = Field(None, ge=0)
    is_clinical_practice: Optional[bool] = None
    is_active: Optional[bool] = None


class CourseResponse(CourseBase):
    id: str
    teacher: Optional[TeacherSummary] = None
    teacher_name: Optional[str] = None
    teacher_rut: Optional[str] = None
    teacher_specialty: Optional[str] = None
    teacher_employee_number: Optional[str] = None
    co_teacher: Optional[TeacherSummary] = None
    co_teacher_name: Optional[str] = None
    co_teacher_rut: Optional[str] = None
    co_teacher_specialty: Optional[str] = None
    co_teacher_employee_number: Optional[str] = None
    program_name: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ProgramBase(BaseModel):
    code: str = Field(..., max_length=50, description="Código del programa ej: DIP-MTC-01, CUR-TUI-01")
    name: str = Field(..., max_length=255, description="Nombre del diplomado o curso")
    program_type: str = Field("DIPLOMADO", max_length=50, description="DIPLOMADO, CURSO, FORMACION_CONTINUA, CARRERA")
    modality: str = Field("PRESENCIAL", max_length=50, description="Diplomado: PRESENCIAL, SEMIPRESENCIAL | Curso: PRESENCIAL, VIRTUAL, HIBRIDO")
    degree_title: Optional[str] = Field(None, max_length=255, description="Diploma o certificación otorgada")
    description: Optional[str] = None
    total_semesters: int = Field(2, ge=1, description="Duración en semestres o módulos")
    total_theoretical_hours: int = Field(0, ge=0)
    total_practical_hours: int = Field(0, ge=0)
    min_clinical_hours: int = Field(0, ge=0)
    is_active: bool = True


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=255)
    program_type: Optional[str] = Field(None, max_length=50)
    modality: Optional[str] = Field(None, max_length=50)
    degree_title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    total_semesters: Optional[int] = Field(None, ge=1)
    total_theoretical_hours: Optional[int] = Field(None, ge=0)
    total_practical_hours: Optional[int] = Field(None, ge=0)
    min_clinical_hours: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ProgramResponse(ProgramBase):
    id: str
    modality_label: Optional[str] = None
    courses_count: int = 0
    courses: List[CourseResponse] = []
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class CurriculumBase(BaseModel):
    program_id: str
    code: str = Field(..., max_length=50)
    version_name: str = Field("Plan Vigente", max_length=100)
    effective_year: int
    is_active: bool = True


class CurriculumCreate(CurriculumBase):
    pass


class CurriculumCourseItem(BaseModel):
    course: CourseResponse
    semester: int
    is_mandatory: bool
    prerequisite_course_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class CurriculumResponse(CurriculumBase):
    id: str
    courses: List[CurriculumCourseItem] = []
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class AddCourseToCurriculumRequest(BaseModel):
    course_id: str
    semester: int
    is_mandatory: bool = True
    prerequisite_course_id: Optional[str] = None


class AssignTeacherRequest(BaseModel):
    teacher_id: Optional[str] = Field(None, description="ID de la Persona (Docente Titular 1 en RRHH Activo) o None para desasignar")
    co_teacher_id: Optional[str] = Field(None, description="ID de la Persona (Segundo Docente / Co-docente en RRHH Activo) o None para desasignar")


class AssignCourseToProgramRequest(BaseModel):
    course_id: Optional[str] = Field(None, description="ID de la Asignatura a asociar al programa")
    semester: Optional[int] = Field(None, ge=1, le=12, description="Semestre en la malla curricular")
    teacher_id: Optional[str] = Field(None, description="ID del Docente Titular 1 (RRHH Activo)")
    co_teacher_id: Optional[str] = Field(None, description="ID del Segundo Docente / Co-docente (RRHH Activo)")
