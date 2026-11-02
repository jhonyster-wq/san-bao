from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_company_context
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException, SanBaoException
from app.modules.institutional.models.company import Company
from app.modules.academic.models.student import Student, Enrollment, CohortEnrollment
from app.modules.academic.schemas.student import (
    StudentCreate,
    StudentResponse,
    EnrollmentCreate,
    EnrollmentResponse,
    CohortEnrollmentCreate,
    CohortEnrollmentResponse,
)
from app.modules.academic.schemas.evaluation import (
    EvaluationCreate,
    EvaluationResponse,
    GradeRecord,
    GradeResponse,
    ClinicalPracticeHourCreate,
    ClinicalPracticeHourResponse,
)
from app.modules.academic.services.academic_service import AcademicService
from app.shared.responses import APIResponse, PaginatedResponse

router = APIRouter(prefix="/academic/students", tags=["Académico: Alumnos, Matrículas y Calificaciones"])


@router.post("", response_model=APIResponse[StudentResponse], status_code=status.HTTP_201_CREATED, summary="Admitir y crear expediente de estudiante")
def admit_student(
    payload: StudentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AcademicService(db)
    try:
        student = service.admit_student(payload)
        return APIResponse(message="Estudiante admitido exitosamente", data=student)
    except EntityAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.get("", response_model=APIResponse[List[StudentResponse]], summary="Listar estudiantes")
def list_students(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Student).filter(Student.deleted_at.is_(None))
    if status_filter:
        q = q.filter(Student.status == status_filter)
    students = q.all()
    return APIResponse(data=students)


@router.post("/enrollments", response_model=APIResponse[EnrollmentResponse], status_code=status.HTTP_201_CREATED, summary="Formalizar matrícula y generar arancel financiero")
def enroll_student(
    payload: EnrollmentCreate,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Formaliza la matrícula de un estudiante en un programa/período.
    Genera automáticamente el compromiso de pago financiero particionado en cuotas en la sociedad activa (Instituto SpA).
    """
    service = AcademicService(db)
    try:
        enrollment = service.enroll_student(payload, company_id=active_company.id)
        return APIResponse(message="Matrícula formalizada y arancel generado exitosamente", data=enrollment)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/enrollments/cohorts", response_model=APIResponse[CohortEnrollmentResponse], status_code=status.HTTP_201_CREATED, summary="Inscribir asignatura en cohorte")
def enroll_in_cohort(
    payload: CohortEnrollmentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AcademicService(db)
    try:
        item = service.enroll_in_cohort(payload.enrollment_id, payload.cohort_id)
        return APIResponse(message="Asignatura inscrita exitosamente", data=item)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluations", response_model=APIResponse[EvaluationResponse], status_code=status.HTTP_201_CREATED, summary="Crear evaluación en cohorte")
def create_evaluation(
    payload: EvaluationCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AcademicService(db)
    try:
        evaluation = service.create_evaluation(payload)
        return APIResponse(message="Evaluación programada exitosamente", data=evaluation)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/evaluations/{evaluation_id}/grades", response_model=APIResponse[GradeResponse], summary="Registrar calificación (1.0 a 7.0)")
def record_grade(
    evaluation_id: str,
    payload: GradeRecord,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AcademicService(db)
    try:
        grade = service.record_grade(evaluation_id, payload, graded_by=current_user.id)
        return APIResponse(message="Calificación registrada exitosamente", data=grade)
    except (EntityNotFoundException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/clinical-hours", response_model=APIResponse[ClinicalPracticeHourResponse], status_code=status.HTTP_201_CREATED, summary="Acreditar horas de práctica clínica supervisada")
def log_clinical_hours(
    payload: ClinicalPracticeHourCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AcademicService(db)
    try:
        record = service.log_clinical_practice_hours(payload)
        return APIResponse(message="Horas clínicas acreditadas exitosamente", data=record)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{student_id}/clinical-hours/summary", response_model=APIResponse[dict], summary="Obtener total de horas clínicas acumuladas por alumno")
def get_clinical_hours_summary(
    student_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AcademicService(db)
    total_hours = service.get_student_clinical_hours_summary(student_id)
    return APIResponse(data={"student_id": student_id, "total_approved_hours": total_hours})
