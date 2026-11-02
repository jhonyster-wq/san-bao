from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_company_context
from app.core.exceptions import EntityNotFoundException, SanBaoException
from app.modules.institutional.models.company import Company
from app.modules.ecommerce.models.order import Order
from app.modules.ecommerce.schemas.order import (
    CheckoutRequest,
    OrderResponse,
    PaymentConfirmationRequest,
    PaymentConfirmationResponse,
)
from app.modules.ecommerce.services.ecommerce_service import ECommerceService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/ecommerce/orders", tags=["E-Commerce: Órdenes y Pagos Web"])


@router.post("/checkout", response_model=APIResponse[OrderResponse], status_code=status.HTTP_201_CREATED, summary="Iniciar compra (Checkout público)")
def checkout(
    payload: CheckoutRequest,
    company_id: Optional[str] = Query(None, description="Sociedad titular"),
    db: Session = Depends(get_db),
):
    """
    Endpoint público de compra: Crea una orden en estado PENDING y retorna el total a pagar.
    """
    # Si no se especifica sociedad, asociar a la primera sociedad activa (ej: Instituto SpA)
    if not company_id:
        c = db.query(Company).filter(Company.is_active == True).first()
        company_id = c.id if c else None

    if not company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay sociedad activa configurada para la venta.")

    service = ECommerceService(db)
    try:
        order = service.checkout(payload, company_id=company_id)
        return APIResponse(message="Orden de compra generada exitosamente", data=order)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{order_id}/confirm-payment", response_model=APIResponse[PaymentConfirmationResponse], summary="Confirmar pago de pasarela (Webpay / Flow / MercadoPago)")
def confirm_payment(
    order_id: str,
    payload: PaymentConfirmationRequest,
    db: Session = Depends(get_db),
):
    """
    Endpoint webhook / callback de pasarela de pago:
    - Valida la transacción.
    - Marca orden como PAID.
    - Crea automáticamente cuenta de usuario si no existía.
    - Enrola al comprador en el aula virtual LMS de los cursos comprados.
    - Registra el pago en Finanzas.
    """
    service = ECommerceService(db)
    try:
        result = service.confirm_gateway_payment(order_id, payload)
        return APIResponse(message="Pago confirmado y accesos habilitados exitosamente", data=result)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{order_id}", response_model=APIResponse[OrderResponse], summary="Consultar orden de compra")
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id, Order.deleted_at.is_(None)).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden no encontrada")
    return APIResponse(data=order)
