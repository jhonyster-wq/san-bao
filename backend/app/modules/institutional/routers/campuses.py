from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundException
from app.modules.institutional.models.campus import Campus, Room
from app.modules.institutional.schemas.campus import CampusCreate, CampusResponse, RoomBase, RoomCreate, RoomResponse
from app.shared.responses import APIResponse

router = APIRouter(prefix="/campuses", tags=["Sedes y Recintos"])


@router.get("", response_model=APIResponse[List[CampusResponse]], summary="Listar sedes y sus salas/boxes")
def list_campuses(
    company_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Campus).filter(Campus.deleted_at.is_(None), Campus.is_active == True)
    if company_id:
        query = query.filter((Campus.company_id == company_id) | (Campus.company_id.is_(None)))
    campuses = query.all()
    return APIResponse(data=campuses)


@router.post("", response_model=APIResponse[CampusResponse], status_code=status.HTTP_201_CREATED, summary="Registrar sede")
def create_campus(
    payload: CampusCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campus = Campus(
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        address=payload.address,
        city=payload.city,
        company_id=payload.company_id,
        is_active=payload.is_active,
    )
    db.add(campus)
    db.commit()
    db.refresh(campus)
    return APIResponse(message="Sede creada exitosamente", data=campus)


@router.post("/{campus_id}/rooms", response_model=APIResponse[RoomResponse], status_code=status.HTTP_201_CREATED, summary="Agregar sala o box clínico")
def add_room(
    campus_id: str,
    payload: RoomBase,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campus = db.query(Campus).filter(Campus.id == campus_id, Campus.deleted_at.is_(None)).first()
    if not campus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sede no encontrada")

    room = Room(
        campus_id=campus_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        room_type=payload.room_type,
        capacity=payload.capacity,
        is_active=payload.is_active,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return APIResponse(message="Recinto registrado exitosamente", data=room)
