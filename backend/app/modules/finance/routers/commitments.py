from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_company_context
from app.core.exceptions import EntityNotFoundException
from app.modules.institutional.models.company import Company
from app.modules.finance.models.commitment import PaymentCommitment
from app.modules.finance.schemas.commitment import PaymentCommitmentResponse
from app.shared.responses import APIResponse

router = APIRouter(prefix="/finance/commitments", tags=["Finanzas: Aranceles y Compromisos de Pago"])


@router.get("", response_model=APIResponse[List[PaymentCommitmentResponse]], summary="Listar compromisos de pago de la sociedad activa")
def list_commitments(
    person_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(PaymentCommitment).filter(
        PaymentCommitment.company_id == active_company.id,
        PaymentCommitment.deleted_at.is_(None),
    )
    if person_id:
        q = q.filter(PaymentCommitment.person_id == person_id)
    if status_filter:
        q = q.filter(PaymentCommitment.status == status_filter)

    commitments = q.order_by(PaymentCommitment.created_at.desc()).all()
    return APIResponse(data=commitments)


@router.get("/{commitment_id}", response_model=APIResponse[PaymentCommitmentResponse], summary="Obtener detalle de compromiso y cuotas")
def get_commitment(
    commitment_id: str,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    commitment = (
        db.query(PaymentCommitment)
        .filter(
            PaymentCommitment.id == commitment_id,
            PaymentCommitment.company_id == active_company.id,
            PaymentCommitment.deleted_at.is_(None),
        )
        .first()
    )
    if not commitment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compromiso financiero no encontrado")
    return APIResponse(data=commitment)
