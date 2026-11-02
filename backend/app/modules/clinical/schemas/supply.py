from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class ClinicalSupplyBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    category: str = Field("AGUJAS", max_length=50)
    unit: str = Field("UNIDAD", max_length=30)
    is_returnable: bool = False
    stock_minimum: int = 10
    is_active: bool = True


class ClinicalSupplyCreate(ClinicalSupplyBase):
    pass


class ClinicalSupplyResponse(ClinicalSupplyBase):
    id: str
    company_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ShiftSupplyItemCreate(BaseModel):
    supply_id: str
    quantity_delivered: int = Field(..., ge=1)
    condition_notes: Optional[str] = None


class ShiftSupplyItemReturn(BaseModel):
    item_id: str
    quantity_used: int = Field(0, ge=0)
    quantity_returned: int = Field(0, ge=0)
    condition_notes: Optional[str] = None


class ShiftSupplyItemResponse(BaseModel):
    id: str
    supply_id: str
    quantity_delivered: int
    quantity_used: int
    quantity_returned: int
    condition_notes: Optional[str] = None
    supply: Optional[ClinicalSupplyResponse] = None
    model_config = ConfigDict(from_attributes=True)


class ShiftSupplyDispatchCreate(BaseModel):
    campus_id: str
    practitioner_id: str
    room_id: Optional[str] = None
    shift_date: Optional[date] = None
    shift_type: str = Field("MANANA", description="MANANA, TARDE, COMPLETO")
    notes: Optional[str] = None
    items: List[ShiftSupplyItemCreate]


class ShiftSupplyReturnUpdate(BaseModel):
    items: List[ShiftSupplyItemReturn]
    notes: Optional[str] = None


class ShiftSupplyDispatchResponse(BaseModel):
    id: str
    company_id: str
    campus_id: str
    practitioner_id: str
    dispatcher_user_id: str
    room_id: Optional[str] = None
    dispatch_code: str
    shift_date: date
    shift_type: str
    status: str
    delivered_at: datetime
    returned_at: Optional[datetime] = None
    notes: Optional[str] = None
    items: List[ShiftSupplyItemResponse] = []
    model_config = ConfigDict(from_attributes=True)
