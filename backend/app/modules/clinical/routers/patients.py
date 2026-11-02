from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException
from app.modules.clinical.schemas.patient import PatientCreate, PatientUpdate, PatientResponse
from app.modules.clinical.services.clinical_service import ClinicalService
from app.shared.responses import APIResponse, PaginatedResponse

router = APIRouter(prefix="/clinical/patients", tags=["Clínica: Fichas de Pacientes"])


@router.post("", response_model=APIResponse[PatientResponse], status_code=status.HTTP_201_CREATED, summary="Registrar nuevo paciente")
def create_patient(
    payload: PatientCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ClinicalService(db)
    try:
        patient = service.create_patient(payload)
        return APIResponse(message="Paciente registrado exitosamente", data=patient)
    except EntityAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get("", response_model=APIResponse[PaginatedResponse[PatientResponse]], summary="Buscar pacientes por nombre, RUT o ficha")
def list_patients(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ClinicalService(db)
    skip = (page - 1) * page_size
    items, total = service.list_patients(search=search, skip=skip, limit=page_size)
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return APIResponse(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


@router.get("/{patient_id}", response_model=APIResponse[PatientResponse], summary="Consultar ficha de paciente (auditado por Ley 20.584)")
def get_patient(
    patient_id: str,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ClinicalService(db)
    try:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
        patient = service.get_patient(patient_id=patient_id, user_id=current_user.id, ip=ip, ua=ua)
        return APIResponse(data=patient)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get("/{patient_id}/access-logs", response_model=APIResponse[list], summary="Consultar auditoría de accesos a la ficha (Ley 20.584)")
def get_patient_access_logs(
    patient_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ClinicalService(db)
    logs = service.get_patient_access_logs(patient_id)
    return APIResponse(
        data=[
            {
                "id": log.id,
                "action": log.action,
                "user_id": log.user_id,
                "created_at": log.created_at,
                "ip_address": log.ip_address,
            }
            for log in logs
        ]
    )
