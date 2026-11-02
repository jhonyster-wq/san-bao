from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.institutional.models import User
from app.modules.bi.schemas import ExecutiveDashboardResponse
from app.modules.bi.services import BIService

router = APIRouter(prefix="/bi", tags=["Inteligencia de Negocios y Dashboards"])


@router.get("/dashboard/executive", response_model=ExecutiveDashboardResponse)
def get_executive_dashboard(
    x_company_id: Optional[str] = Header(None),
    company_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna los indicadores clave (KPIs) financieros, académicos y clínicos consolidados o por sociedad."""
    target_company = company_id or (UUID(x_company_id) if x_company_id else None)
    return BIService.get_executive_dashboard(db, target_company)
