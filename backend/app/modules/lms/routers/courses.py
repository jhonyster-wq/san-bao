from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException
from app.modules.lms.schemas.course import (
    LMSCourseCreate,
    LMSCourseResponse,
    CourseModuleCreate,
    CourseModuleResponse,
    LessonCreate,
    LessonResponse,
)
from app.modules.lms.models.course import LMSCourse
from app.modules.lms.services.lms_service import LMSService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/lms/courses", tags=["LMS: Cursos y Contenidos"])


@router.get("", response_model=APIResponse[List[LMSCourseResponse]], summary="Listar cursos del aula virtual")
def list_lms_courses(
    only_published: bool = True,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(LMSCourse).filter(LMSCourse.deleted_at.is_(None))
    if only_published:
        q = q.filter(LMSCourse.is_published == True)
    courses = q.all()
    return APIResponse(data=courses)


@router.post("", response_model=APIResponse[LMSCourseResponse], status_code=status.HTTP_201_CREATED, summary="Crear nuevo curso en el LMS")
def create_lms_course(
    payload: LMSCourseCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LMSService(db)
    try:
        course = service.create_course(payload)
        return APIResponse(message="Curso creado exitosamente en el LMS", data=course)
    except EntityAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.get("/{course_id}", response_model=APIResponse[LMSCourseResponse], summary="Obtener detalle y temario del curso")
def get_lms_course(
    course_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LMSService(db)
    try:
        course = service.get_course(course_id)
        return APIResponse(data=course)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/modules", response_model=APIResponse[CourseModuleResponse], status_code=status.HTTP_201_CREATED, summary="Agregar módulo didáctico a un curso")
def create_course_module(
    payload: CourseModuleCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LMSService(db)
    try:
        module = service.create_module(payload)
        return APIResponse(message="Módulo didáctico agregado exitosamente", data=module)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/lessons", response_model=APIResponse[LessonResponse], status_code=status.HTTP_201_CREATED, summary="Agregar lección o material de estudio")
def create_lesson(
    payload: LessonCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LMSService(db)
    try:
        lesson = service.create_lesson(payload)
        return APIResponse(message="Lección agregada exitosamente", data=lesson)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
