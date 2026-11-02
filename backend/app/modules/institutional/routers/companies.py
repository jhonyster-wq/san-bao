from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_superuser
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException
from app.modules.institutional.models.user import User
from app.modules.institutional.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse
from app.modules.institutional.services.company_service import CompanyService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/companies", tags=["Sociedades Institucionales"])


@router.get("", response_model=APIResponse[List[CompanyResponse]], summary="Listar todas las sociedades")
def list_companies(
    only_active: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna las sociedades configuradas en el sistema (Instituto y Clínica)."""
    service = CompanyService(db)
    companies = service.list_all(only_active=only_active)
    return APIResponse(data=companies)


@router.get("/{company_id}", response_model=APIResponse[CompanyResponse], summary="Obtener detalle de una sociedad")
def get_company(
    company_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = CompanyService(db)
    try:
        company = service.get_by_id(company_id)
        return APIResponse(data=company)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("", response_model=APIResponse[CompanyResponse], status_code=status.HTTP_201_CREATED, summary="Registrar nueva sociedad")
def create_company(
    payload: CompanyCreate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    service = CompanyService(db)
    try:
        company = service.create(payload)
        return APIResponse(message="Sociedad creada exitosamente", data=company)
    except EntityAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.put("/{company_id}", response_model=APIResponse[CompanyResponse], summary="Actualizar datos de una sociedad")
def update_company(
    company_id: str,
    payload: CompanyUpdate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
):
    service = CompanyService(db)
    try:
        company = service.update(company_id, payload)
        return APIResponse(message="Sociedad actualizada exitosamente", data=company)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
