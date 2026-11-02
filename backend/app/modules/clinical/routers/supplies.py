from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_company_context
from app.core.exceptions import EntityNotFoundException, SanBaoException
from app.modules.institutional.models.company import Company
from app.modules.clinical.schemas.supply import (
    ClinicalSupplyResponse,
    ShiftSupplyDispatchCreate,
    ShiftSupplyDispatchResponse,
    ShiftSupplyReturnUpdate,
)
from app.modules.clinical.services.supply_service import SupplyService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/clinical/supplies", tags=["Clínica: Insumos y Entrega de Turno"])


@router.get("", response_model=APIResponse[List[ClinicalSupplyResponse]], summary="Listar los 27 insumos clínicos oficiales")
def list_supplies(
    category: Optional[str] = Query(None, description="AGUJAS, MOXA, AURICULO, DESCARTABLE, EQUIPAMIENTO"),
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SupplyService(db)
    # Auto-inicializar si no existen
    items = service.list_supplies(company_id=active_company.id, category=category)
    if not items and not category:
        items = service.seed_official_supplies(company_id=active_company.id)
    return APIResponse(data=items)


@router.post("/seed", response_model=APIResponse[List[ClinicalSupplyResponse]], status_code=status.HTTP_201_CREATED, summary="Inicializar catálogo de insumos oficiales")
def seed_supplies(
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SupplyService(db)
    items = service.seed_official_supplies(company_id=active_company.id)
    return APIResponse(message="Catálogo de 27 insumos clínicos inicializado con éxito", data=items)


@router.post("/dispatches", response_model=APIResponse[ShiftSupplyDispatchResponse], status_code=status.HTTP_201_CREATED, summary="Secretaria registra entrega de insumos a terapeuta para su turno")
def create_shift_dispatch(
    payload: ShiftSupplyDispatchCreate,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    La Secretaria Clínica entrega el kit de insumos (agujas, moxas, auriculoterapia,
    descartables y equipos como Electro, Encendedor y Parlante) al terapeuta al inicio de su turno.
    """
    service = SupplyService(db)
    try:
        dispatch = service.create_shift_dispatch(
            data=payload,
            dispatcher_user_id=current_user.id,
            company_id=active_company.id,
        )
        return APIResponse(message="Despacho de insumos de turno registrado exitosamente", data=dispatch)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/dispatches", response_model=APIResponse[List[ShiftSupplyDispatchResponse]], summary="Consultar entregas de insumos por turno y sede")
def list_shift_dispatches(
    campus_id: Optional[str] = Query(None, description="Sede Santiago o Viña del Mar"),
    shift_date: Optional[date] = Query(None, description="Fecha de turno"),
    practitioner_id: Optional[str] = Query(None, description="Terapeuta"),
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SupplyService(db)
    dispatches = service.list_shift_dispatches(
        company_id=active_company.id,
        campus_id=campus_id,
        shift_date=shift_date,
        practitioner_id=practitioner_id,
    )
    return APIResponse(data=dispatches)


@router.post("/dispatches/{dispatch_id}/return", response_model=APIResponse[ShiftSupplyDispatchResponse], summary="Registrar devolución de equipos e insumos al cierre de turno")
def record_shift_return(
    dispatch_id: str,
    payload: ShiftSupplyReturnUpdate,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = SupplyService(db)
    try:
        dispatch = service.record_shift_return(
            dispatch_id=dispatch_id,
            data=payload,
            verifier_user_id=current_user.id,
        )
        return APIResponse(message="Devolución de turno registrada y verificada exitosamente", data=dispatch)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
