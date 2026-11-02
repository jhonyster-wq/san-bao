from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundException
from app.modules.clinical.schemas.practitioner import PractitionerCreate, PractitionerResponse
from app.modules.clinical.services.clinical_service import ClinicalService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/clinical/practitioners", tags=["Clínica: Profesionales y Terapeutas"])


@router.post("", response_model=APIResponse[PractitionerResponse], status_code=status.HTTP_201_CREATED, summary="Registrar profesional o terapeuta")
def create_practitioner(
    payload: PractitionerCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ClinicalService(db)
    try:
        practitioner = service.create_practitioner(payload)
        return APIResponse(message="Profesional registrado exitosamente", data=practitioner)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get("", response_model=APIResponse[List[PractitionerResponse]], summary="Listar profesionales y tutores clínicos")
def list_practitioners(
    only_tutors: bool = Query(False, description="Filtrar únicamente tutores clínicos de práctica"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ClinicalService(db)
    practitioners = service.list_practitioners(only_active=True, only_tutors=only_tutors)
    return APIResponse(data=practitioners)
