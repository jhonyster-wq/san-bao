from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import date

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundException, SanBaoException
from app.modules.academic.services.teacher_portal_service import TeacherPortalService
from app.modules.academic.schemas.teacher_portal import (
    TeacherCourseResponse,
    EvaluationCreateRequest,
    TeacherGradeEntryRequest,
    BatchAttendanceSaveRequest,
    ContentUploadRequest,
)
from app.shared.responses import APIResponse

router = APIRouter(prefix="/academic/teacher", tags=["Portal Docente: Cursos, Notas, Asistencia y Contenidos"])


@router.get("/courses", response_model=APIResponse[List[Dict[str, Any]]], summary="Cursos y asignaturas asignadas al docente")
def list_teacher_courses(
    teacher_id: Optional[str] = Query(None, description="ID del docente (opcional para filtro)"),
    db: Session = Depends(get_db),
):
    service = TeacherPortalService(db)
    courses = service.list_teacher_assigned_courses(teacher_person_id=teacher_id)
    return APIResponse(data=courses)


@router.get("/courses/{course_id}/grades", response_model=APIResponse[Dict[str, Any]], summary="Planilla de notas de la cátedra")
def get_course_grades(
    course_id: str,
    cohort_id: Optional[str] = Query(None, description="ID de cohorte"),
    db: Session = Depends(get_db),
):
    service = TeacherPortalService(db)
    try:
        data = service.get_course_students_and_grades(course_id=course_id, cohort_id=cohort_id)
        return APIResponse(data=data)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/courses/{course_id}/evaluations", response_model=APIResponse[Dict[str, Any]], summary="Crear nueva evaluación programada")
def create_course_evaluation(
    course_id: str,
    payload: EvaluationCreateRequest,
    db: Session = Depends(get_db),
):
    service = TeacherPortalService(db)
    try:
        ev = service.create_course_evaluation(course_id=course_id, payload=payload)
        return APIResponse(message="Evaluación programada creada exitosamente", data=ev)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/courses/{course_id}/grades", response_model=APIResponse[Dict[str, Any]], summary="Registrar calificación por alumno")
def record_student_grade(
    course_id: str,
    payload: TeacherGradeEntryRequest,
    db: Session = Depends(get_db),
):
    service = TeacherPortalService(db)
    try:
        res = service.record_student_grade(course_id=course_id, payload=payload)
        return APIResponse(message="Calificación registrada exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/courses/{course_id}/attendance", response_model=APIResponse[Dict[str, Any]], summary="Planilla de asistencia por clase")
def get_course_attendance(
    course_id: str,
    cohort_id: Optional[str] = Query(None),
    class_date: Optional[date] = Query(None, description="Fecha de clase (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    service = TeacherPortalService(db)
    try:
        data = service.get_course_attendance(course_id=course_id, cohort_id=cohort_id, class_date=class_date)
        return APIResponse(data=data)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/courses/{course_id}/attendance", response_model=APIResponse[Dict[str, Any]], summary="Registrar asistencia por alumno en lote")
def record_session_attendance(
    course_id: str,
    payload: BatchAttendanceSaveRequest,
    db: Session = Depends(get_db),
):
    service = TeacherPortalService(db)
    try:
        res = service.record_session_attendance(course_id=course_id, payload=payload)
        return APIResponse(message="Asistencia guardada exitosamente", data=res)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get("/courses/{course_id}/contents", response_model=APIResponse[Dict[str, Any]], summary="Contenidos didácticos y materiales por clase")
def list_course_contents(
    course_id: str,
    db: Session = Depends(get_db),
):
    service = TeacherPortalService(db)
    try:
        data = service.list_course_class_contents(course_id=course_id)
        return APIResponse(data=data)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/courses/{course_id}/contents", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Subir material o contenido pedagógico por clase")
def upload_course_content(
    course_id: str,
    payload: ContentUploadRequest,
    db: Session = Depends(get_db),
):
    service = TeacherPortalService(db)
    try:
        res = service.upload_course_class_content(course_id=course_id, payload=payload)
        return APIResponse(message="Contenido pedagógico publicado exitosamente", data=res)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete("/contents/{content_id}", response_model=APIResponse[None], summary="Eliminar contenido pedagógico")
def delete_course_content(
    content_id: str,
    db: Session = Depends(get_db),
):
    service = TeacherPortalService(db)
    try:
        service.delete_course_class_content(content_id=content_id)
        return APIResponse(message="Contenido eliminado exitosamente")
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
