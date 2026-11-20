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


@router.get("/financial-intelligence", summary="L: Indicadores de Inteligencia Financiera (Ratio de Berry, DSO, BEP, ROFE, % Ingreso Neto Efectivo y COGS) por sociedad y centro de costo")
def get_financial_intelligence_kpis(
    company_id: Optional[str] = None,
    period: str = "2026-11",
    cost_center: Optional[str] = None,
    consolidation_rule_approved: bool = False,
    x_company_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException, status
    from app.core.exceptions import SanBaoException
    from app.shared.responses import APIResponse

    target_comp = company_id or x_company_id
    try:
        data = BIService.get_financial_intelligence_report(
            db=db,
            company_id=target_comp,
            period=period,
            cost_center=cost_center,
            consolidation_rule_approved=consolidation_rule_approved,
        )
        return APIResponse(
            message="Indicadores de Inteligencia Financiera actualizados (vigencia <= 24h)",
            data=data,
        )
    except SanBaoException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

