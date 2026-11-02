from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundException, SanBaoException
from app.modules.clinical.schemas.encounter import (
    EncounterCreate,
    EncounterUpdate,
    EncounterSignRequest,
    EncounterResponse,
)
from app.modules.clinical.services.clinical_service import ClinicalService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/clinical/encounters", tags=["Clínica: Ficha y Atenciones MTC"])


@router.post("", response_model=APIResponse[EncounterResponse], status_code=status.HTTP_201_CREATED, summary="Registrar atención clínica MTC (Borrador o Definitiva)")
def create_encounter(
    payload: EncounterCreate,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Registra la atención clínica de Medicina Tradicional China.
    Si interviene un alumno en práctica (`student_id`), la atención queda en estado 'DRAFT'
    hasta que el tutor docente la revise y selle legalmente.
    """
    service = ClinicalService(db)
    try:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
        encounter = service.create_encounter(payload, user_id=current_user.id, ip=ip, ua=ua)
        return APIResponse(message="Atención registrada exitosamente", data=encounter)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{encounter_id}", response_model=APIResponse[EncounterResponse], summary="Consultar atención clínica (auditada por Ley 20.584)")
def get_encounter(
    encounter_id: str,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ClinicalService(db)
    try:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
        encounter = service.get_encounter(encounter_id, user_id=current_user.id, ip=ip, ua=ua)
        return APIResponse(data=encounter)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put("/{encounter_id}", response_model=APIResponse[EncounterResponse], summary="Actualizar borrador de atención clínica")
def update_encounter(
    encounter_id: str,
    payload: EncounterUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ClinicalService(db)
    try:
        encounter = service.update_encounter(encounter_id, payload)
        return APIResponse(message="Atención clínica actualizada exitosamente", data=encounter)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{encounter_id}/sign", response_model=APIResponse[EncounterResponse], summary="Firmar y sellar atención médica electrónicamente")
def sign_encounter(
    encounter_id: str,
    payload: EncounterSignRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Firma electrónicamente la atención médica como profesional tratante o tutor clínico.
    Si la atención fue realizada por un estudiante en práctica:
    - Se registra la retroalimentación y calificación pedagógica del tutor.
    - Se sellan los datos médicos.
    - **Se acreditan automáticamente las horas prácticas clínicas en el Módulo Académico**.
    """
    service = ClinicalService(db)
    try:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
        encounter = service.sign_encounter(
            encounter_id=encounter_id,
            sign_data=payload,
            signing_user_id=current_user.id,
            ip=ip,
            ua=ua,
        )
        return APIResponse(message="Atención médica firmada y horas acreditadas exitosamente", data=encounter)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
