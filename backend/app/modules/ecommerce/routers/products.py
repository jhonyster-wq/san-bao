from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_company_context
from app.core.exceptions import EntityAlreadyExistsException, EntityNotFoundException, SanBaoException
from app.modules.institutional.models.company import Company
from app.modules.ecommerce.schemas.product import ProductCreate, ProductResponse
from app.modules.ecommerce.services.ecommerce_service import ECommerceService, ECommerceHubService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/ecommerce/products", tags=["E-Commerce: Catálogo de Productos y Cursos"])


@router.get("/hub/overview", summary="Consolidado Integral de Comercio Electrónico, Formación Continua y LMS")
def get_ecommerce_hub_overview(
    category: Optional[str] = Query(None, description="Filtro de categoría: TODOS, SEMINARIO, FORMACION_CONTINUA, CURSO, DIPLOMADO"),
    search: Optional[str] = Query(None, description="Búsqueda por nombre, código SKU o docente"),
    db: Session = Depends(get_db),
):
    service = ECommerceHubService(db)
    data = service.get_hub_overview(category_filter=category, search=search)
    return APIResponse(message="Suite de Comercio Electrónico y Formación Continua cargada exitosamente", data=data)


@router.get("/hub/lookup-participant", summary="Autocompletar participante por RUT y verificar si es alumno San Bao")
def lookup_participant(
    rut: str = Query(..., description="RUT del participante"),
    db: Session = Depends(get_db),
):
    service = ECommerceHubService(db)
    data = service.lookup_participant_by_rut(rut=rut)
    return APIResponse(data=data)


@router.get("/hub/validate-promo", summary="Validar cupón o promoción comercial y calcular descuento")
def validate_promo_code(
    code: str = Query(..., description="Código de cupón promocional"),
    product_id: Optional[str] = Query(None, description="ID del curso o programa seleccionado"),
    db: Session = Depends(get_db),
):
    service = ECommerceHubService(db)
    try:
        data = service.validate_promotion_code(code=code, product_id=product_id)
        return APIResponse(message=data["message"], data=data)
    except SanBaoException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/hub/enroll-and-pay", status_code=status.HTTP_201_CREATED, summary="Inscripción en línea, pago electrónico, registro automático y emisión de comprobante/DTE")
def process_online_enrollment_and_payment(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    service = ECommerceHubService(db)
    try:
        result = service.process_online_enrollment_and_payment(payload)
        return APIResponse(
            message="Inscripción en línea confirmada, participante matriculado en Gestión Académica / LMS y Boleta Exenta SII emitida",
            data=result,
        )
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/hub/catalog", status_code=status.HTTP_201_CREATED, summary="Publicar nuevo Curso, Seminario o Programa de Formación Continua sincronizado con Académico y LMS")
def create_catalog_course_or_seminar(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    service = ECommerceHubService(db)
    try:
        result = service.create_catalog_item(payload)
        return APIResponse(message="Programa comercial publicado y sincronizado con el Módulo Académico y LMS", data=result)
    except SanBaoException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/hub/promotions", status_code=status.HTTP_201_CREATED, summary="Crear cupón de descuento, beca o actividad comercial")
def create_ecommerce_promotion(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    service = ECommerceHubService(db)
    try:
        result = service.create_promotion(payload)
        return APIResponse(message="Promoción o actividad comercial creada exitosamente", data=result)
    except SanBaoException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/hub/promotions/{promo_id}/toggle", summary="Activar o pausar promoción comercial")
def toggle_ecommerce_promotion(
    promo_id: str,
    db: Session = Depends(get_db),
):
    service = ECommerceHubService(db)
    try:
        result = service.toggle_promotion(promo_id)
        return APIResponse(message="Estado de promoción actualizado", data=result)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=APIResponse[List[ProductResponse]], summary="Catálogo público de cursos y productos")
def list_products(
    company_id: Optional[str] = Query(None, description="Filtrar por sociedad emisora"),
    only_active: bool = True,
    db: Session = Depends(get_db),
):
    """Endpoint público: no requiere autenticación para que los visitantes puedan ver el catálogo."""
    service = ECommerceService(db)
    products = service.list_products(company_id=company_id, only_active=only_active)
    return APIResponse(data=products)


@router.post("", response_model=APIResponse[ProductResponse], status_code=status.HTTP_201_CREATED, summary="Publicar producto o curso en tienda online")
def create_product(
    payload: ProductCreate,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ECommerceService(db)
    try:
        product = service.create_product(payload, company_id=active_company.id)
        return APIResponse(message="Producto publicado exitosamente", data=product)
    except EntityAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
