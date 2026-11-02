from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException, InvalidRUTException
from app.modules.institutional.models.user import User
from app.modules.institutional.schemas.person import PersonCreate, PersonUpdate, PersonResponse
from app.modules.institutional.services.person_service import PersonService
from app.shared.responses import APIResponse, PaginatedResponse

router = APIRouter(prefix="/people", tags=["Maestro de Personas"])


@router.get("", response_model=APIResponse[PaginatedResponse[PersonResponse]], summary="Listar y buscar personas")
def list_people(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Búsqueda y paginación en el registro maestro de personas por nombre, RUT o email."""
    service = PersonService(db)
    skip = (page - 1) * page_size
    items, total = service.list_all(skip=skip, limit=page_size, search=search)
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    paginated = PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
    return APIResponse(data=paginated)


@router.get("/{person_id}", response_model=APIResponse[PersonResponse], summary="Obtener persona por ID")
def get_person(
    person_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PersonService(db)
    try:
        person = service.get_by_id(person_id)
        return APIResponse(data=person)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("", response_model=APIResponse[PersonResponse], status_code=status.HTTP_201_CREATED, summary="Registrar persona")
def create_person(
    payload: PersonCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea una persona física validando formalmente su RUT con el algoritmo Módulo 11."""
    service = PersonService(db)
    try:
        person = service.create(payload)
        return APIResponse(message="Persona registrada exitosamente", data=person)
    except (InvalidRUTException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except EntityAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.put("/{person_id}", response_model=APIResponse[PersonResponse], summary="Actualizar persona")
def update_person(
    person_id: str,
    payload: PersonUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = PersonService(db)
    try:
        person = service.update(person_id, payload)
        return APIResponse(message="Datos actualizados exitosamente", data=person)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
