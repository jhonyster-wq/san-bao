from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_company_context
from app.modules.institutional.models.company import Company
from app.modules.finance.schemas.commitment import (
    PaymentCreate,
    PaymentResponse,
    StudentFinancialStatusResponse,
)
from app.modules.finance.services.finance_service import FinanceService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/finance/payments", tags=["Finanzas: Recaudación y Pagos"])


@router.post("", response_model=APIResponse[PaymentResponse], status_code=status.HTTP_201_CREATED, summary="Registrar pago o abono")
def record_payment(
    payload: PaymentCreate,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Registra la recepción de un pago (Transferencia, Webpay, Efectivo) e imputa
    automáticamente a las cuotas pendientes más antiguas.
    """
    # Forzar la sociedad activa de la sesión
    payload.company_id = active_company.id
    service = FinanceService(db)
    payment = service.record_payment(payload, received_by=current_user.id)
    return APIResponse(message="Pago registrado y aplicado a cuotas exitosamente", data=payment)


@router.get("/students/{person_id}/status", response_model=APIResponse[StudentFinancialStatusResponse], summary="Consultar estado financiero y morosidad de un estudiante")
def get_student_financial_status(
    person_id: str,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = FinanceService(db)
    status_data = service.get_person_financial_status(person_id, company_id=active_company.id)
    return APIResponse(data=status_data)
