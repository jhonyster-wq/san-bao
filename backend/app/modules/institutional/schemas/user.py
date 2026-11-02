from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.modules.institutional.schemas.person import PersonResponse


class PermissionResponse(BaseModel):
    id: str
    code: str
    name: str
    module: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class RoleResponse(BaseModel):
    id: str
    code: str
    name: str
    scope: str
    description: Optional[str] = None
    permissions: List[PermissionResponse] = []
    model_config = ConfigDict(from_attributes=True)


class UserCompanyRoleResponse(BaseModel):
    id: str
    company_id: str
    role: RoleResponse
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    username: str = Field(..., max_length=100)
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    person_id: str
    password: str = Field(..., min_length=6, description="Contraseña en texto plano a ser hasheada")


class UserResponse(UserBase):
    id: str
    person_id: str
    person: Optional[PersonResponse] = None
    company_roles: List[UserCompanyRoleResponse] = []
    last_login_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AssignRoleRequest(BaseModel):
    user_id: str
    company_id: str
    role_id: str
