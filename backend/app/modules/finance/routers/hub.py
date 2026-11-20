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


@router.get("/cost-centers", response_model=APIResponse[Dict[str, Any]], summary="Catálogo Maestro de Centros de Costo por Sociedad (Requerimiento E.6)")
def list_cost_centers(
    company_id: Optional[str] = Query(None, description="ID de la sociedad SpA"),
    area_type: Optional[str] = Query(None, description="ACADEMICO, CLINICO, ADMINISTRATIVO, COMERCIAL"),
    db: Session = Depends(get_db),
):
    from app.modules.finance.models.commitment import CostCenter

    # Garantizar que los centros de costo maestros estén inicializados
    service = FinanceHubService(db)
    service.get_erp_financial_suite()

    q = db.query(CostCenter).filter(CostCenter.is_active == True, CostCenter.deleted_at.is_(None))
    if company_id:
        q = q.filter(CostCenter.company_id == company_id)
    if area_type:
        q = q.filter(CostCenter.area_type == area_type.upper())
    items = [
        {
            "id": cc.id,
            "company_id": cc.company_id,
            "code": cc.code,
            "name": cc.name,
            "area_type": cc.area_type,
            "is_active": cc.is_active,
        }
        for cc in q.order_by(CostCenter.code.asc()).all()
    ]
    return APIResponse(
        message="Catálogo Maestro de Centros de Costo por Sociedad",
        data={"items": items, "total": len(items)},
    )


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


# =============================================================================
# 14. FASE 5: EXENCIONES, PACKS, REVERSOS, TESORERÍA DUAL, OC, CONCILIACIÓN 3 VÍAS, DTE Y HONORARIOS
# =============================================================================
@router.post("/installments/{installment_id}/apply-exemption", response_model=APIResponse[Dict[str, Any]], summary="E.1: Aplicar excepción de cobro académico (BECA, PRÁCTICA, CONGELAMIENTO) conservando el cargo original")
def apply_academic_charge_exemption(
    installment_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.apply_academic_charge_exemption(installment_id, payload)
        return APIResponse(message=f"Excepción de cobro ({res['exemption_type']}) aplicada con estado EXENTO", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


@router.post("/clinical-packs", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="E.2: Registrar pack de sesiones clínicas (VIGENTE, AGOTADO, ANULADO) con centro de costo")
def register_clinical_session_pack_finance(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.register_clinical_session_pack_finance(payload)
        return APIResponse(message=f"Pack clínico registrado en estado {res['status']}", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


@router.put("/clinical-packs/{pack_id}/status", response_model=APIResponse[Dict[str, Any]], summary="E.2: Consumir sesiones o anular pack clínico (VIGENTE -> AGOTADO / ANULADO)")
def update_clinical_session_pack_status(
    pack_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.update_clinical_session_pack_status(pack_id, payload)
        return APIResponse(message=f"Estado del pack actualizado a {res['status']}", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


@router.post("/payments/{payment_id}/reverse", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="E.3: Generar reverso auditable asociado al pago original sin eliminar el pago")
def reverse_payment_auditable(
    payment_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.reverse_payment_auditable(payment_id, payload)
        return APIResponse(message=f"Reverso {res['reversal_code']} registrado conservando el pago original", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


@router.post("/purchase-orders", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="E.4, E.5 y E.6: Emitir Orden de Compra imputada a centro de costo con control de compromiso y alerta de sobregiro")
def create_purchase_order_with_cost_center(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.create_purchase_order_with_cost_center(payload)
        return APIResponse(message=f"Orden de Compra {res['oc_number']} emitida e imputada a {res['cost_center']}", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


@router.post("/purchases", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="E.5: Registrar compra exigiendo Orden de Compra aprobada e imputada a centro de costo")
def register_purchase_invoice_requiring_oc(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.register_purchase_invoice_requiring_oc(payload)
        return APIResponse(message=f"Compra registrada y asociada a Orden de Compra {res['oc_number']}", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


@router.post("/reconciliation-3way/run", response_model=APIResponse[Dict[str, Any]], summary="F: Ejecutar conciliación bancaria automática de tres vías (Cartola <-> Pagos <-> Asientos Contables)")
def run_three_way_bank_reconciliation(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.run_three_way_bank_reconciliation(payload)
        return APIResponse(
            message=f"Conciliación 3 vías ejecutada: {res['auto_reconciled_count']} conciliadas, {res['review_queue_count']} en cola de revisión",
            data=res,
        )
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


@router.get("/tax-classifications", response_model=APIResponse[Dict[str, Any]], summary="G: Listar matriz parametrizable de clasificaciones tributarias SII por sociedad")
def list_tax_classifications(db: Session = Depends(get_db)):
    service = FinanceHubService(db)
    return APIResponse(data=service.list_or_upsert_tax_classifications())


@router.post("/tax-classifications", response_model=APIResponse[Dict[str, Any]], summary="G: Configurar clasificación tributaria por sociedad y tipo de operación validada por Finanzas")
def upsert_tax_classification(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    return APIResponse(message="Clasificación tributaria actualizada", data=service.list_or_upsert_tax_classifications(payload))


@router.post("/dte/emit-controlled", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="G: Emitir DTE oficial con clasificación tributaria por sociedad y bloqueo de doble emisión por operación")
def emit_controlled_dte_sii(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.emit_controlled_dte_sii(payload)
        return APIResponse(message=f"DTE Tipo {res['dte_type']} Folio #{res['folio']} procesado", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


@router.post("/dte/{dte_id}/retry-sii", response_model=APIResponse[Dict[str, Any]], summary="G: Reintentar envío al SII de DTE en contingencia")
def retry_contingent_dte_sii(
    dte_id: str,
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.retry_contingent_dte_sii(dte_id)
        return APIResponse(message=f"Reintento SII exitoso para Folio #{res['folio']}", data=res)
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


@router.put("/honorarios/retention-rates", response_model=APIResponse[Dict[str, Any]], summary="H: Configurar tasa de retención de honorarios por período según Ley 21.133")
def upsert_retention_rate_for_period(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    res = service.upsert_retention_rate_for_period(
        period_year=int(payload.get("period_year") or 2026),
        retention_rate_pct=float(payload.get("retention_rate_pct") or 15.25),
    )
    return APIResponse(message="Tasa de retención Ley 21.133 configurada para el período", data=res)


@router.post("/honorarios/liquidate-from-hours", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="H: Liquidar honorarios de docentes y tutores desde horas académicas y clínicas validadas según Ley 21.133")
def liquidate_honorarios_from_validated_hours(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    service = FinanceHubService(db)
    try:
        res = service.liquidate_honorarios_from_validated_hours(payload)
        return APIResponse(
            message=f"Liquidación de honorarios {res['receipt_number']} calculada (Tasa Ley 21.133: {res['retention_rate_pct']}%)",
            data=res,
        )
    except (EntityNotFoundException, SanBaoException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))


