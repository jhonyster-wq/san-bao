from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundException
from app.modules.lms.schemas.progress import (
    LMSEnrollmentResponse,
    LessonProgressUpdate,
    AssignmentCreate,
    AssignmentResponse,
    SubmissionCreate,
    SubmissionGradeRequest,
    SubmissionResponse,
)
from app.modules.lms.models.progress import LMSEnrollment, Submission
from app.modules.lms.services.lms_service import LMSService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/lms", tags=["LMS: Avance y Actividades"])


@router.post("/courses/{course_id}/enroll", response_model=APIResponse[LMSEnrollmentResponse], status_code=status.HTTP_201_CREATED, summary="Matricular usuario en curso LMS")
def enroll_user(
    course_id: str,
    user_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_user_id = user_id or current_user.id
    service = LMSService(db)
    enrollment = service.enroll_user(course_id, target_user_id)
    return APIResponse(message="Usuario enrolado en aula virtual", data=enrollment)


@router.get("/my-courses", response_model=APIResponse[List[LMSEnrollmentResponse]], summary="Mis cursos activos en el LMS")
def get_my_courses(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enrollments = (
        db.query(LMSEnrollment)
        .filter(LMSEnrollment.user_id == current_user.id, LMSEnrollment.deleted_at.is_(None))
        .all()
    )
    return APIResponse(data=enrollments)


@router.post("/lessons/progress", response_model=APIResponse[dict], summary="Marcar lección como completada")
def update_lesson_progress(
    payload: LessonProgressUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LMSService(db)
    try:
        progress = service.mark_lesson_progress(
            lesson_id=payload.lesson_id,
            user_id=current_user.id,
            is_completed=payload.is_completed,
        )
        return APIResponse(message="Progreso actualizado exitosamente", data={"is_completed": progress.is_completed})
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/assignments", response_model=APIResponse[AssignmentResponse], status_code=status.HTTP_201_CREATED, summary="Crear tarea o actividad")
def create_assignment(
    payload: AssignmentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LMSService(db)
    assignment = service.create_assignment(payload)
    return APIResponse(message="Tarea programada exitosamente", data=assignment)


@router.post("/submissions", response_model=APIResponse[SubmissionResponse], status_code=status.HTTP_201_CREATED, summary="Entregar tarea de estudiante")
def submit_assignment(
    payload: SubmissionCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LMSService(db)
    submission = service.submit_assignment(payload, user_id=current_user.id)
    return APIResponse(message="Tarea entregada exitosamente", data=submission)


@router.post("/submissions/{submission_id}/grade", response_model=APIResponse[SubmissionResponse], summary="Calificar entrega de estudiante")
def grade_submission(
    submission_id: str,
    payload: SubmissionGradeRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LMSService(db)
    try:
        submission = service.grade_submission(submission_id, payload, graded_by=current_user.id)
        return APIResponse(message="Entrega calificada exitosamente", data=submission)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
