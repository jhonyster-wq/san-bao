from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException
from app.modules.academic.schemas.period import (
    AcademicPeriodCreate,
    AcademicPeriodResponse,
    CohortCreate,
    CohortResponse,
)
from app.modules.academic.models.period import AcademicPeriod, Cohort
from app.modules.academic.services.academic_service import AcademicService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/academic/periods", tags=["Académico: Períodos y Cohortes"])


@router.get("", response_model=APIResponse[List[AcademicPeriodResponse]], summary="Listar períodos académicos")
def list_periods(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    periods = db.query(AcademicPeriod).filter(AcademicPeriod.deleted_at.is_(None)).order_by(AcademicPeriod.year.desc()).all()
    return APIResponse(data=periods)


@router.post("", response_model=APIResponse[AcademicPeriodResponse], status_code=status.HTTP_201_CREATED, summary="Crear período académico")
def create_period(
    payload: AcademicPeriodCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AcademicService(db)
    try:
        period = service.create_academic_period(payload)
        return APIResponse(message="Período académico creado exitosamente", data=period)
    except EntityAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.get("/cohorts", response_model=APIResponse[List[CohortResponse]], summary="Listar cohortes/secciones abiertas")
def list_cohorts(
    period_id: str = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Cohort).filter(Cohort.deleted_at.is_(None))
    if period_id:
        q = q.filter(Cohort.academic_period_id == period_id)
    cohorts = q.all()
    return APIResponse(data=cohorts)


@router.get("/cohorts/{cohort_id}/details", summary="Detalle de cohorte con sede, recinto y alumnos inscritos")
def get_cohort_details(
    cohort_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cohort = db.query(Cohort).filter(Cohort.id == cohort_id, Cohort.deleted_at.is_(None)).first()
    if not cohort:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cohorte no encontrada")

    students_data = []
    for enr in cohort.enrollments:
        if enr.deleted_at is None:
            student = enr.student
            person = student.person if student else None
            students_data.append({
                "enrollment_id": enr.id,
                "student_id": enr.student_id,
                "student_number": student.student_number if student else None,
                "rut": person.rut if person else None,
                "full_name": f"{person.first_name} {person.last_name}" if person else None,
                "email": person.email if person else None,
                "status": enr.status,
            })

    campus = cohort.campus
    room = cohort.room
    teacher = cohort.teacher
    course = cohort.course

    return APIResponse(
        data={
            "cohort_id": cohort.id,
            "cohort_code": cohort.code,
            "course": {
                "id": course.id if course else None,
                "code": course.code if course else None,
                "name": course.name if course else None,
            },
            "campus": {
                "id": campus.id if campus else None,
                "code": campus.code if campus else None,
                "name": campus.name if campus else None,
                "city": campus.city if campus else None,
                "address": campus.address if campus else None,
            } if campus else None,
            "room": {
                "id": room.id if room else None,
                "code": room.code if room else None,
                "name": room.name if room else None,
                "room_type": room.room_type if room else None,
                "capacity": room.capacity if room else None,
            } if room else None,
            "teacher": {
                "id": teacher.id if teacher else None,
                "name": f"{teacher.first_name} {teacher.last_name}" if teacher else None,
            } if teacher else None,
            "schedule": cohort.schedule,
            "quota": cohort.quota,
            "enrolled_count": len(students_data),
            "students": students_data,
        }
    )


@router.post("/cohorts", response_model=APIResponse[CohortResponse], status_code=status.HTTP_201_CREATED, summary="Abrir sección o cohorte de asignatura")
def create_cohort(
    payload: CohortCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AcademicService(db)
    try:
        cohort = service.create_cohort(payload)
        return APIResponse(message="Cohorte abierta exitosamente", data=cohort)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
