from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class RoomBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    room_type: str = Field("CLASSROOM", description="CLASSROOM, CLINICAL_BOX, OFFICE, AUDITORIUM")
    capacity: int = 1
    is_active: bool = True


class RoomCreate(RoomBase):
    campus_id: str


class RoomResponse(RoomBase):
    id: str
    campus_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CampusBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field("Santiago", max_length=100)
    company_id: Optional[str] = Field(None, description="Sociedad asociada o NULL si es sede compartida")
    is_active: bool = True


class CampusCreate(CampusBase):
    pass


class CampusResponse(CampusBase):
    id: str
    rooms: List[RoomResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
