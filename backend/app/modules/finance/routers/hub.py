from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundException, SanBaoException
from app.modules.finance.services.finance_hub_service import FinanceHubService
from app.shared.responses import APIResponse

router = APIRouter(
    prefix="/finance/hub",
    tags=["Finanzas & DTE SII: Cobranza, Recaudo/DTE, Remuneraciones/BHE y Pagarés/Contratos"],
)


# =============================================================================
# 1. COBRANZA Y MOROSIDAD
# =============================================================================
@router.get("/collections", response_model=APIResponse[Dict[str, Any]], summary="Panel de Cobranza, Cuotas y Morosidad")
def get_collections_overview(
    company: Optional[str] = Query(None, description="consolidated | instituto | clinica"),
    status_filter: Optional[str] = Query(None, alias="status", description="ALL | OVERDUE | UP_TO_DATE | PAID"),
    search: Optional[str] = Query(None, description="Búsqueda por RUT, nombre o concepto"),
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    data = service.get_collections_overview(company_filter=company, status_filter=status_filter, search=search)
    return APIResponse(data=data)


@router.post("/commitments", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Crear compromiso financiero en cuotas y generar pagaré")
def create_commitment_plan(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.create_commitment_plan(payload)
        return APIResponse(message="Compromiso financiero y plan de cuotas creado exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/collections/action", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Registrar notificación o gestión de cobranza")
def register_collection_action(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.register_collection_action(payload)
        return APIResponse(message="Gestión de cobranza registrada y enviada exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/commitments/{commitment_id}/renegotiate", response_model=APIResponse[Dict[str, Any]], summary="Repactar deuda vencida en nuevas cuotas y generar convenio")
def renegotiate_commitment(
    commitment_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.renegotiate_overdue_commitment(commitment_id, payload)
        return APIResponse(message="Deuda repactada y Convenio de Pago generado exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# 2. RECAUDO Y DOCUMENTOS TRIBUTARIOS (DTE SII)
# =============================================================================
@router.get("/revenue-dte", response_model=APIResponse[Dict[str, Any]], summary="Listado de recaudaciones y Documentos Tributarios Electrónicos (DTE SII)")
def list_revenue_and_dtes(
    company: Optional[str] = Query(None, description="consolidated | instituto | clinica"),
    dte_type: Optional[int] = Query(None, description="Filtrar por tipo DTE: 33, 34, 39, 41, 61"),
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    data = service.list_revenue_and_dtes(company_filter=company, dte_type=dte_type)
    return APIResponse(data=data)


@router.post("/payments", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Registrar pago/recaudo e imputar a cuota con emisión automática de DTE SII")
def record_payment_with_dte(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.record_payment_with_optional_dte(payload)
        return APIResponse(message="Pago recaudado e imputado exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/dte/emit", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Emitir DTE oficial ante el SII con Timbre Electrónico TED")
def emit_official_dte(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.emit_official_dte(payload)
        return APIResponse(message=f"DTE Folio #{res['folio']} emitido y aceptado por SII", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# 3. REMUNERACIONES Y HONORARIOS (LIQUIDACIONES + BHE SII)
# =============================================================================
@router.get("/remunerations", response_model=APIResponse[Dict[str, Any]], summary="Resumen de Nómina de Sueldos, Leyes Sociales y Boletas de Honorarios (BHE)")
def get_remunerations_overview(
    company: Optional[str] = Query(None, description="consolidated | instituto | clinica"),
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    data = service.get_remunerations_overview(company_filter=company)
    return APIResponse(data=data)


@router.post("/payrolls", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Calcular y emitir Liquidación de Sueldo mensual legal")
def generate_payroll(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.generate_employee_payroll(payload)
        return APIResponse(message="Liquidación de remuneraciones calculada y emitida exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/fee-receipts", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Registrar Boleta de Honorarios Electrónica (BHE) con retención SII")
def issue_bhe_receipt(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.issue_bhe_receipt(payload)
        return APIResponse(message="Boleta de Honorarios Electrónica (BHE) registrada exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/remunerations/{item_type}/{item_id}/pay", response_model=APIResponse[Dict[str, Any]], summary="Marcar Liquidación de Sueldo o BHE como Pagada")
def mark_remuneration_paid(
    item_type: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.mark_remuneration_paid(item_type, item_id)
        return APIResponse(message="Pago de remuneración/honorario registrado como PAGADO", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# 4. GENERA CONTRATO Y PAGARÉ (FIRMA DIGITAL LEY N° 19.799)
# =============================================================================
@router.get("/legal-documents", response_model=APIResponse[Dict[str, Any]], summary="Listar Contratos, Pagarés y Convenios con estado de Firma Digital")
def list_legal_documents(
    company: Optional[str] = Query(None, description="consolidated | instituto | clinica"),
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    data = service.list_legal_documents(company_filter=company)
    return APIResponse(data=data)


@router.post("/legal-documents", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Generar Contrato o Pagaré a la Orden")
def generate_legal_document(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.generate_legal_document(payload)
        return APIResponse(message=f"Documento {res['document_code']} generado exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/legal-documents/{doc_id}/sign", response_model=APIResponse[Dict[str, Any]], summary="Estampar Firma Electrónica SHA-256 en Contrato o Pagaré")
def sign_legal_document(
    doc_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.sign_legal_document(doc_id, payload)
        return APIResponse(message=f"Documento {res['document_code']} firmado electrónicamente con éxito", data=res)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/signatures/verify/{query_code}", response_model=APIResponse[Dict[str, Any]], summary="Verificar autenticidad criptográfica de Firma Digital por Token, Folio o Hash")
def verify_signature(
    query_code: str,
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.verify_signature_or_document(query_code)
        return APIResponse(data=res)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# =============================================================================
# 5 A 13. SUITE ERP FINANCIERA INTEGRAL (CxP, TESORERÍA, PRESUPUESTOS,
#         CENTROS DE COSTOS, CONTABILIDAD, CONCILIACIÓN Y UNIDADES DE NEGOCIO)
# =============================================================================
@router.get("/erp-suite", response_model=APIResponse[Dict[str, Any]], summary="Consolidado Integral 13 Áreas de Finanzas (Sociedades, CxC, CxP, Tesorería, Presupuestos, Contabilidad, Conciliación, Reportes y Unidades de Negocio)")
def get_erp_financial_suite(
    company: Optional[str] = Query(None, description="consolidated | instituto | clinica"),
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    data = service.get_erp_financial_suite(company_filter=company)
    return APIResponse(data=data)


@router.post("/payables", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Registrar nueva Cuenta por Pagar (CxP / Factura Proveedor / Arriendo / Previred / F29)")
def create_payable(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.create_payable(payload)
        return APIResponse(message="Cuenta por Pagar (CxP) registrada exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/payables/{payable_id}/pay", response_model=APIResponse[Dict[str, Any]], summary="Pagar Cuenta por Pagar (CxP) y generar egreso en Tesorería + Asiento Contable")
def pay_payable(
    payable_id: str,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.pay_payable(payable_id, payload)
        return APIResponse(message="Cuenta por Pagar pagada, egresada en Tesorería y contabilizada en Libro Diario", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/treasury-movements", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Registrar movimiento de Ingreso o Egreso en Tesorería")
def create_treasury_movement(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.create_treasury_movement(payload)
        return APIResponse(message="Movimiento de Tesorería registrado exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/bank-reconciliation/{movement_id}/reconcile", response_model=APIResponse[Dict[str, Any]], summary="Conciliar partida bancaria entre Cartola Bancaria y Libro Banco")
def reconcile_bank_movement(
    movement_id: str,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.reconcile_bank_movement(movement_id, payload)
        return APIResponse(message="Partida bancaria conciliada exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/budgets", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Crear partida presupuestaria asignada a Sociedad, Centro de Costo y Unidad de Negocio")
def create_budget_item(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.create_or_update_budget_item(payload)
        return APIResponse(message="Partida presupuestaria creada exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/journal-entries", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Registrar asiento contable cuadrado (Debe = Haber) en el Libro Diario")
def create_journal_entry(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.create_journal_entry(payload)
        return APIResponse(message=f"Asiento contable {res['entry_number']} contabilizado en Libro Diario", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

