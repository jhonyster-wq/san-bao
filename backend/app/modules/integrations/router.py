from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Body, Depends, Header, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.institutional.models import User
from app.modules.integrations.schemas import (
    DTEDocumentCreate,
    DTEDocumentResponse,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    DigitalSignatureCreate,
    DigitalSignatureResponse,
)
from app.modules.integrations.services import (
    DTEService,
    WebhookDispatcherService,
    DigitalSignatureService,
    IntegrationsHubService,
)
from app.shared.responses import APIResponse

router = APIRouter(prefix="/integrations", tags=["Integraciones, DTE SII y Firma"])


@router.get("/hub/overview", summary="Consolidado Integral de los 10 Aspectos de Integración, Automatización, Firma y Trazabilidad")
def get_integrations_hub_overview(db: Session = Depends(get_db)):
    service = IntegrationsHubService(db)
    data = service.get_hub_overview()
    return APIResponse(message="Centro de Integración, Automatización y Trazabilidad cargado exitosamente", data=data)


@router.post("/hub/notifications", status_code=status.HTTP_201_CREATED, summary="Emitir y despachar notificación multicanal (Email HTML, WhatsApp, Portal)")
def create_and_send_notification(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    service = IntegrationsHubService(db)
    res = service.send_notification(payload)
    return APIResponse(message="Notificación institucional despachada y registrada en bitácora", data=res)


@router.post("/hub/approvals", status_code=status.HTTP_201_CREATED, summary="Crear nuevo flujo de aprobación inter-área")
def create_approval_workflow(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    service = IntegrationsHubService(db)
    res = service.create_approval_request(payload)
    return APIResponse(message="Flujo de aprobación creado exitosamente", data=res)


@router.post("/hub/approvals/{workflow_id}/decide", summary="Aprobar o rechazar solicitud en flujo de aprobación")
def decide_approval_workflow(
    workflow_id: str,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    service = IntegrationsHubService(db)
    res = service.create_or_decide_approval(
        workflow_id=workflow_id,
        decision=payload.get("decision", "APPROVED"),
        approver=payload.get("approver", "Dirección Ejecutiva San Bao"),
        comments=payload.get("comments"),
    )
    return APIResponse(message=f"Flujo {res['code']} actualizado a {res['status']}", data=res)


@router.post("/hub/operations/{operation_id}/retry", summary="Reintentar operación con error en cola de resiliencia")
def retry_operation(
    operation_id: str,
    db: Session = Depends(get_db),
):
    service = IntegrationsHubService(db)
    res = service.retry_failed_operation(operation_id)
    return APIResponse(message=res["message"], data=res)


@router.post("/hub/operations/retry-all", summary="Reintentar todas las operaciones pendientes en cola de errores")
def retry_all_operations(db: Session = Depends(get_db)):
    service = IntegrationsHubService(db)
    res = service.retry_all_failed_operations()
    return APIResponse(message=f"{res['recovered_count']} operación(es) recuperada(s) exitosamente", data=res)


@router.post("/hub/sync-all", summary="Ejecutar sincronización inmediata de información entre todas las áreas")
def trigger_cross_area_sync(db: Session = Depends(get_db)):
    service = IntegrationsHubService(db)
    res = service.trigger_cross_area_sync()
    return APIResponse(message="Sincronización transversal completada al 100%", data=res)


@router.post("/hub/signatures", status_code=status.HTTP_201_CREATED, summary="Generar Firma Electrónica SHA-256 sobre documento institucional")
def create_quick_digital_signature(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    service = IntegrationsHubService(db)
    res = service.create_quick_signature(payload)
    return APIResponse(message="Documento firmado electrónicamente con sello criptográfico SHA-256", data=res)


@router.post("/dte/emit", response_model=DTEDocumentResponse, status_code=status.HTTP_201_CREATED)
def emit_dte(
    data: DTEDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Emite un Documento Tributario Electrónico (Boleta/Factura Exenta o Afecta) con Timbre Electrónico DTE."""
    return DTEService.emit_dte(db, data)


@router.get("/dte", response_model=List[DTEDocumentResponse])
def list_dtes(
    x_company_id: Optional[str] = Header(None),
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista los DTE emitidos para la sociedad activa."""
    target_company = company_id or x_company_id
    if not target_company:
        return []
    return DTEService.get_dtes_by_company(db, target_company)


@router.post("/webhooks/endpoints", response_model=WebhookEndpointResponse, status_code=status.HTTP_201_CREATED)
def register_webhook(
    data: WebhookEndpointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra un nuevo endpoint receptor de webhooks institucionales."""
    return WebhookDispatcherService.register_endpoint(db, data)


@router.get("/webhooks/endpoints", response_model=List[WebhookEndpointResponse])
def list_webhooks(
    x_company_id: Optional[str] = Header(None),
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista endpoints de webhook activos para la sociedad."""
    target_company = company_id or x_company_id
    if not target_company:
        return []
    return WebhookDispatcherService.list_endpoints(db, target_company)


@router.post("/signatures/sign", response_model=DigitalSignatureResponse, status_code=status.HTTP_201_CREATED)
def sign_document(
    data: DigitalSignatureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Firma electrónicamente un documento institucional generando su hash SHA-256 inmutable."""
    return DigitalSignatureService.sign_document(db, data)


@router.get("/signatures/verify/{token}", response_model=DigitalSignatureResponse)
def verify_signature(
    token: str,
    db: Session = Depends(get_db),
):
    """Verifica la autenticidad e integridad de una firma electrónica mediante su token."""
    sig = DigitalSignatureService.verify_document_signature(db, token)
    if not sig:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firma electrónica no válida o no encontrada.")
    return sig
