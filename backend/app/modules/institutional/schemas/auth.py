from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.modules.institutional.schemas.company import CompanyResponse


class LoginRequest(BaseModel):
    username: str = Field(..., description="Nombre de usuario o RUT")
    password: str = Field(..., description="Contraseña de acceso")


class AvailableCompanyContext(BaseModel):
    id: str
    rut: str
    trade_name: str
    legal_name: str
    roles: List[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    full_name: str
    available_companies: List[AvailableCompanyContext] = []
    active_company: Optional[AvailableCompanyContext] = None


class SwitchCompanyRequest(BaseModel):
    company_id: str = Field(..., description="ID de la sociedad a la cual conmutar contexto")


class CurrentUserContext(BaseModel):
    user_id: str
    username: str
    full_name: str
    is_superuser: bool
    active_company_id: Optional[str] = None
    active_company_name: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
