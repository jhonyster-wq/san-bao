import pytest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.modules.institutional.models import Company, Person
from app.modules.hr.models import (
    HREmployee,
    HRContract,
    EmployeeType,
    ContractType,
    LeaveType,
    LeaveStatus,
    FeeReceiptStatus,
    PayrollStatus,
)
from app.modules.integrations.models import DTEStatus, SignatureStatus

client = TestClient(app)


@pytest.fixture
def test_context():
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    assert login_res.status_code == 200, f"Login falló: {login_res.text}"
    data = login_res.json()["data"]
    token = data["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    companies = data["available_companies"]
    instituto = next(c for c in companies if "77.123.456-9" in c["rut"] or "77123456-9" in c["rut"])
    clinica = next(c for c in companies if "76.987.654-5" in c["rut"] or "76987654-5" in c["rut"])

    # Crear persona para docente/colaborador si no existe
    docente_rut = "14.234.567-6"
    res_person = client.post(
        "/api/v1/institutional/people",
        headers=auth_headers,
        json={
            "rut": docente_rut,
            "first_name": "Marcela",
            "last_name": "Pérez",
            "email": "marcela.perez.hrtest@sanbao.cl",
            "gender": "FEMALE",
        },
    )
    if res_person.status_code == 201:
        docente_person = res_person.json()["data"]
    else:
        # Ya existe
        list_p = client.get("/api/v1/institutional/people?page=1&page_size=100", headers=auth_headers).json()["data"]["items"]
        docente_person = next(
            p for p in list_p
            if "14234567" in p["rut"]
            or "14.234.567-6" in p["rut"]
            or "marcela.perez" in (p.get("email") or "")
        )

    return {
        "auth_headers": auth_headers,
        "instituto_id": instituto["id"],
        "clinica_id": clinica["id"],
        "docente_person_id": docente_person["id"],
        "docente_rut": docente_rut,
    }


def test_hr_employee_contract_payroll_and_fee_receipt(test_context):
    """Prueba completa del Módulo de RRHH: contratación, liquidación y boleta de honorarios."""
    auth_headers = test_context["auth_headers"]
    instituto_id = test_context["instituto_id"]
    docente_person_id = test_context["docente_person_id"]

    # 1. Registrar Colaborador (Docente)
    import uuid as py_uuid
    emp_code = f"DOC-{py_uuid.uuid4().hex[:6].upper()}"
    emp_payload = {
        "company_id": instituto_id,
        "person_id": docente_person_id,
        "employee_number": emp_code,
        "job_title": "Docente Titular de Fitoterapia y Acupuntura",
        "department": "Académico",
        "employee_type": "TEACHER",
        "hire_date": "2026-03-01",
        "notes": "Especialista en Medicina Tradicional China",
    }
    res_emp = client.post("/api/v1/hr/employees", json=emp_payload, headers=auth_headers)
    assert res_emp.status_code == 201, f"Error creando empleado: {res_emp.text}"
    employee = res_emp.json()
    emp_id = employee["id"]
    assert employee["employee_number"] == emp_code
    assert employee["status"] == "ACTIVE"

    # 2. Registrar Contrato Laboral Indefinido
    contract_payload = {
        "employee_id": emp_id,
        "contract_type": "INDEFINITE",
        "start_date": "2026-03-01",
        "base_salary": 800000.00,
        "weekly_hours": 40,
        "afp_name": "MODELO",
        "health_system": "FONASA",
        "health_quote_pct": 7.00,
    }
    res_contract = client.post("/api/v1/hr/contracts", json=contract_payload, headers=auth_headers)
    assert res_contract.status_code == 201, f"Error creando contrato: {res_contract.text}"
    contract = res_contract.json()
    contract_id = contract["id"]
    assert contract["status"] == "ACTIVE"

    # 3. Solicitar y Aprobar Permiso / Vacaciones
    leave_payload = {
        "employee_id": emp_id,
        "leave_type": "VACATION",
        "start_date": "2026-07-15",
        "end_date": "2026-07-20",
        "days_count": 5,
        "reason": "Vacaciones de invierno",
    }
    res_leave = client.post("/api/v1/hr/leave-requests", json=leave_payload, headers=auth_headers)
    assert res_leave.status_code == 201
    leave = res_leave.json()
    assert leave["status"] == "PENDING"

    res_approve = client.put(f"/api/v1/hr/leave-requests/{leave['id']}/approve", headers=auth_headers)
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "APPROVED"

    # 4. Generar Liquidación de Remuneración Mensual
    payroll_payload = {
        "company_id": instituto_id,
        "employee_id": emp_id,
        "contract_id": contract_id,
        "period_month": 4,
        "period_year": 2026,
        "worked_days": 30,
        "bonuses": 50000.00,
        "overtime_amount": 0.00,
        "non_taxable_allowances": 40000.00,  # Colación + movilización
    }
    res_payroll = client.post("/api/v1/hr/payrolls/generate", json=payroll_payload, headers=auth_headers)
    assert res_payroll.status_code in (200, 201), f"Error generando liquidación: {res_payroll.text}"
    payroll = res_payroll.json()
    
    # Validaciones legales chilenas:
    # Sueldo base: 800.000 + Gratificación 25% (200.000, topeada en 190.000) + Bono 50.000 = 1.040.000 imponible
    assert Decimal(str(payroll["base_salary"])) == Decimal("800000.00")
    assert Decimal(str(payroll["legal_gratuity"])) == Decimal("190000.00")
    assert Decimal(str(payroll["gross_taxable_salary"])) == Decimal("1040000.00")
    assert Decimal(str(payroll["total_earnings"])) == Decimal("1080000.00")
    # Descuentos: AFP (~11.45%), Salud (7%), AFC (0.6%)
    assert Decimal(str(payroll["pension_deduction"])) > 0
    assert Decimal(str(payroll["health_deduction"])) == Decimal("72800.00")  # 7% de 1.040.000
    assert Decimal(str(payroll["net_salary"])) > 0
    assert payroll["status"] == "APPROVED"

    # 5. Emitir Boleta de Honorarios Profesional (BHE)
    bhe_code = f"BHE-{py_uuid.uuid4().hex[:6].upper()}"
    fee_payload = {
        "company_id": instituto_id,
        "employee_id": emp_id,
        "receipt_number": bhe_code,
        "issue_date": "2026-04-30",
        "period_month": 4,
        "period_year": 2026,
        "description": "Docencia extraordinaria seminario Moxibustión",
        "gross_amount": 200000.00,
        "retention_rate": 13.75,
    }
    res_fee = client.post("/api/v1/hr/fee-receipts", json=fee_payload, headers=auth_headers)
    assert res_fee.status_code == 201, f"Error emitiendo boleta de honorarios: {res_fee.text}"
    fee = res_fee.json()
    assert Decimal(str(fee["retention_amount"])) == Decimal("27500.00")  # 13.75% de 200.000
    assert Decimal(str(fee["net_amount"])) == Decimal("172500.00")      # 200.000 - 27.500
    assert fee["status"] == "APPROVED"


def test_dte_and_integrations_flow(test_context):
    """Prueba del Módulo de Integraciones: Emisión de DTE (Boleta/Factura SII), Webhooks y Firma."""
    auth_headers = test_context["auth_headers"]
    instituto_id = test_context["instituto_id"]
    clinica_id = test_context["clinica_id"]
    docente_person_id = test_context["docente_person_id"]

    # 1. Registrar un Webhook Endpoint para la Clínica
    wh_payload = {
        "company_id": clinica_id,
        "url": "https://api.sanbao.cl/ext/webhooks/listener",
        "description": "Sistema externo de notificaciones SMS/WhatsApp",
        "secret": "supersecretkey123",
        "subscribed_events": ["dte.issued", "payment.confirmed"],
    }
    res_wh = client.post("/api/v1/integrations/webhooks/endpoints", json=wh_payload, headers=auth_headers)
    assert res_wh.status_code == 201, f"Error creando webhook: {res_wh.text}"
    wh = res_wh.json()
    assert wh["is_active"] is True

    # 2. Emitir Documento Tributario Electrónico (Boleta Exenta - Prestación Médica / Acupuntura)
    dte_payload = {
        "company_id": clinica_id,
        "dte_type": 41,  # Boleta Electrónica Exenta
        "receiver_rut": "17.123.456-5",
        "receiver_name": "Rodrigo Silva",
        "receiver_commune": "Providencia",
        "items": [
            {
                "name": "Sesión de Acupuntura Clínica y Moxibustión",
                "quantity": 1,
                "unit_price": 45000.00,
                "is_exempt": True,
                "total": 45000.00,
            }
        ],
    }
    res_dte = client.post("/api/v1/integrations/dte/emit", json=dte_payload, headers=auth_headers)
    assert res_dte.status_code == 201, f"Error emitiendo DTE: {res_dte.text}"
    dte = res_dte.json()
    assert dte["dte_type"] == 41
    assert dte["folio"] >= 1001
    assert Decimal(str(dte["exempt_amount"])) == Decimal("45000.00")
    assert Decimal(str(dte["iva_amount"])) == Decimal("0.00")  # Exento de IVA
    assert Decimal(str(dte["total_amount"])) == Decimal("45000.00")
    assert dte["sii_status"] == "ACCEPTED"
    assert "<TED version=\"1.0\">" in dte["digital_stamp"]  # Timbre Electrónico DTE

    # 3. Firma Electrónica Simple de Documento
    sig_payload = {
        "company_id": instituto_id,
        "document_type": "CONTRATO_DOCENTE_2026",
        "document_id": dte["id"],  # vinculamos a un ID
        "signer_person_id": docente_person_id,
        "document_content_to_hash": "Contrato de Prestación de Servicios Docentes San Bao 2026...",
        "signer_ip": "190.160.10.22",
    }
    res_sig = client.post("/api/v1/integrations/signatures/sign", json=sig_payload, headers=auth_headers)
    assert res_sig.status_code == 201, f"Error firmando documento: {res_sig.text}"
    signature = res_sig.json()
    assert len(signature["document_hash"]) == 64  # SHA-256
    token = signature["signature_token"]

    # 4. Verificar validez de la firma
    res_verify = client.get(f"/api/v1/integrations/signatures/verify/{token}")
    assert res_verify.status_code == 200
    assert res_verify.json()["status"] == "SIGNED"


def test_business_intelligence_executive_dashboard(test_context):
    """Prueba del Módulo de Business Intelligence: Dashboard Ejecutivo consolidado y por sociedad."""
    auth_headers = test_context["auth_headers"]
    instituto_id = test_context["instituto_id"]
    clinica_id = test_context["clinica_id"]

    # 1. Dashboard Consolidado
    res_consolidated = client.get("/api/v1/bi/dashboard/executive", headers=auth_headers)
    assert res_consolidated.status_code == 200, f"Error BI consolidado: {res_consolidated.text}"
    dash_cons = res_consolidated.json()
    assert "financial" in dash_cons
    assert "academic" in dash_cons
    assert "clinical" in dash_cons
    assert Decimal(str(dash_cons["financial"]["total_revenue"])) >= 0
    assert Decimal(str(dash_cons["financial"]["total_expenses"])) >= 0
    assert dash_cons["academic"]["total_programs"] >= 0
    assert dash_cons["clinical"]["total_patients"] >= 0

    # 2. Dashboard Específico para el Instituto de Medicina China
    res_inst = client.get(f"/api/v1/bi/dashboard/executive?company_id={instituto_id}", headers=auth_headers)
    assert res_inst.status_code == 200
    dash_inst = res_inst.json()
    assert dash_inst["company_id"] == instituto_id
    assert "Instituto" in dash_inst["company_name"] or "San Bao" in dash_inst["company_name"]

    # 3. Dashboard Específico para la Clínica San Bao
    res_clin = client.get(f"/api/v1/bi/dashboard/executive?company_id={clinica_id}", headers=auth_headers)
    assert res_clin.status_code == 200
    dash_clin = res_clin.json()
    assert dash_clin["company_id"] == clinica_id


def test_fase6_digital_signature_contracts_promissory_notes_and_enrollment_regularization(test_context):
    """
    Fase 6 (Requerimiento I):
    - Generar Contrato Educacional y Pagaré en el momento de la matrícula según convenio.
    - Enviar documentos al proveedor genérico de firma y registrar estados (GENERADO, ENVIADO_A_FIRMA, FIRMADO, RECHAZADO, VENCIDO).
    - Conservar identidad del firmante, fecha/hora, hash SHA-256, evidencia de firma, sello de tiempo e historial de eventos.
    - Bloquear la regularización de matrícula si falta cualquiera de las firmas obligatorias.
    - Regularizar automáticamente la matrícula únicamente cuando TODOS los documentos obligatorios estén FIRMADOS.
    """
    auth_headers = test_context["auth_headers"]

    # 1. Generar Contrato Educacional + Pagaré al momento de la matrícula (10 cuotas)
    bundle_res = client.post(
        "/api/v1/integrations/signatures/enrollment-bundle",
        headers=auth_headers,
        json={
            "signer_rut": "19.876.543-0",
            "signer_name": "Diego Valenzuela Rojas",
            "installments_count": 10,
            "total_amount": 2600000,
            "provider_name": "GENERIC_REST_ESIGN_PROVIDER",
            "send_to_provider": True,
        },
    )
    assert bundle_res.status_code == 201
    bundle = bundle_res.json()["data"]
    onboarding_id = bundle["onboarding_id"]
    assert bundle["enrollment_regularized"] is False
    docs = bundle["documents"]
    assert len(docs) == 2
    contrato_doc = next(d for d in docs if d["document_type"] == "CONTRATO_EDUCACIONAL")
    pagare_doc = next(d for d in docs if d["document_type"] == "PAGARE_ARANCEL")
    assert contrato_doc["status"] == "ENVIADO_A_FIRMA"
    assert pagare_doc["status"] == "ENVIADO_A_FIRMA"
    assert len(contrato_doc["events_history"]) == 2  # GENERADO -> ENVIADO_A_FIRMA

    # 2. Firmar únicamente el Contrato Educacional (el Pagaré sigue pendiente)
    sign_ctr_res = client.post(
        f"/api/v1/integrations/signatures/documents/{contrato_doc['document_id']}/provider-callback",
        headers=auth_headers,
        json={
            "status": "FIRMADO",
            "signer_rut": "19876543-0",
            "signer_name": "Diego Valenzuela Rojas",
            "signer_ip": "190.161.42.18",
        },
    )
    assert sign_ctr_res.status_code == 200
    ctr_signed = sign_ctr_res.json()["data"]
    assert ctr_signed["status"] == "FIRMADO"
    assert ctr_signed["archived_document_uri"].startswith("archive://")
    assert ctr_signed["timestamp_seal"].startswith("TSA-CL-19799-")
    assert ctr_signed["signature_evidence"]["evidence_validated"] is True
    # Como falta el Pagaré obligatorio, la matrícula AÚN NO está regularizada
    assert ctr_signed["enrollment_regularization"]["enrollment_regularized"] is False

    # 3. Intentar forzar la regularización faltando el Pagaré -> bloqueado con 400
    reg_blocked = client.post(
        f"/api/v1/integrations/signatures/onboardings/{onboarding_id}/regularize",
        headers=auth_headers,
    )
    assert reg_blocked.status_code == 400
    assert "PAGARE_ARANCEL" in reg_blocked.json()["detail"]

    # 4. Probar estado VENCIDO o RECHAZADO en el Pagaré -> sigue bloqueando la regularización
    rej_pag_res = client.post(
        f"/api/v1/integrations/signatures/documents/{pagare_doc['document_id']}/provider-callback",
        headers=auth_headers,
        json={"status": "RECHAZADO", "reason": "Observación en fecha de vencimiento"},
    )
    assert rej_pag_res.status_code == 200
    assert rej_pag_res.json()["data"]["status"] == "RECHAZADO"
    assert rej_pag_res.json()["data"]["enrollment_regularization"]["enrollment_regularized"] is False

    # 5. Firmar finalmente el Pagaré obligatorio -> se regulariza automáticamente la matrícula
    sign_pag_res = client.post(
        f"/api/v1/integrations/signatures/documents/{pagare_doc['document_id']}/provider-callback",
        headers=auth_headers,
        json={
            "status": "FIRMADO",
            "signer_rut": "19876543-0",
            "signer_name": "Diego Valenzuela Rojas",
            "signer_ip": "190.161.42.18",
        },
    )
    assert sign_pag_res.status_code == 200
    pag_signed = sign_pag_res.json()["data"]
    assert pag_signed["status"] == "FIRMADO"
    assert pag_signed["enrollment_regularization"]["enrollment_regularized"] is True

    # Verificar endpoint explícito de regularización ahora responde 200 OK
    reg_ok = client.post(
        f"/api/v1/integrations/signatures/onboardings/{onboarding_id}/regularize",
        headers=auth_headers,
    )
    assert reg_ok.status_code == 200
    assert reg_ok.json()["data"]["enrollment_regularized"] is True


def test_fase7_transactional_integration_bus_dlq_and_transversal_blocking_with_clinical_continuity(test_context):
    """
    Fase 7 (Requerimientos J y K):
    - J: Catálogo de 12 eventos de negocio, publicación con idempotencia, backoff exponencial (2^n),
         Cola de Mensajes Fallidos (DLQ), alertas de error y reprocesamiento.
    - K: Motor de bloqueo transversal configurable y auditable por morosidad, excepciones autorizadas con vigencia,
         rehabilitación automática al confirmarse pago, y salvaguarda obligatoria de continuidad de atención clínica de pacientes.
    """
    auth_headers = test_context["auth_headers"]
    person_id = test_context["docente_person_id"]

    # 1. Catálogo de 12 eventos oficiales (Req. J)
    cat_res = client.get("/api/v1/integrations/transactional-bus/events-catalog", headers=auth_headers)
    assert cat_res.status_code == 200
    assert cat_res.json()["data"]["total"] == 12

    # 2. Publicar evento con idempotencia y verificar control de duplicados
    evt_1 = client.post(
        "/api/v1/integrations/transactional-bus/publish",
        headers=auth_headers,
        json={
            "idempotency_key": "EVT-IDEM-2026-0001",
            "event_name": "person.upserted",
            "source_module": "ERP_CORE",
            "target_module": "GESTOR_CLINICO",
            "entity_reference": person_id,
        },
    )
    assert evt_1.status_code == 200
    assert evt_1.json()["data"]["idempotent_replay"] is False
    assert evt_1.json()["data"]["status"] == "SUCCESS"

    evt_dup = client.post(
        "/api/v1/integrations/transactional-bus/publish",
        headers=auth_headers,
        json={
            "idempotency_key": "EVT-IDEM-2026-0001",
            "event_name": "person.upserted",
        },
    )
    assert evt_dup.status_code == 200
    assert evt_dup.json()["data"]["idempotent_replay"] is True
    assert evt_dup.json()["data"]["duplicate_ignored"] is True

    # 3. Probar reintento con backoff exponencial (intento 2 de 3 -> backoff 4s) y caída a DLQ (intento 3 de 3 -> DLQ + alerta)
    evt_retry = client.post(
        "/api/v1/integrations/transactional-bus/publish",
        headers=auth_headers,
        json={
            "idempotency_key": "EVT-FAIL-RETRY-2026-0002",
            "event_name": "clinical.encounter_closed",
            "attempt_number": 2,
            "max_attempts": 3,
            "base_backoff_seconds": 2,
            "simulate_failure": True,
            "error_detail": "Timeout transitorio en receptor clínico",
        },
    )
    assert evt_retry.status_code == 200
    assert evt_retry.json()["data"]["status"] == "ERROR_RETRYING"
    assert evt_retry.json()["data"]["backoff_seconds"] == 4
    assert evt_retry.json()["data"]["dead_letter_queued"] is False

    evt_dlq = client.post(
        "/api/v1/integrations/transactional-bus/publish",
        headers=auth_headers,
        json={
            "idempotency_key": "EVT-FAIL-DLQ-2026-0003",
            "event_name": "clinical.practice_hours_recorded",
            "attempt_number": 3,
            "max_attempts": 3,
            "base_backoff_seconds": 2,
            "simulate_failure": True,
            "error_detail": "Fallo definitivo tras 3 intentos -> enviar a DLQ",
        },
    )
    assert evt_dlq.status_code == 200
    dlq_data = evt_dlq.json()["data"]
    assert dlq_data["status"] == "DEAD_LETTER_QUEUE"
    assert dlq_data["dead_letter_queued"] is True
    assert dlq_data["error_alert_sent"] is True

    # Reprocesar desde la Cola de Mensajes Fallidos (DLQ)
    reproc_res = client.post(
        f"/api/v1/integrations/transactional-bus/dlq/{dlq_data['operation_id']}/reprocess",
        headers=auth_headers,
    )
    assert reproc_res.status_code == 200
    assert reproc_res.json()["data"]["status"] == "RECOVERED"
    assert reproc_res.json()["data"]["dead_letter_queued"] is False

    # 4. Motor de Bloqueo Transversal (Req. K)
    rest_res = client.post(
        "/api/v1/integrations/restrictions/apply",
        headers=auth_headers,
        json={
            "person_id": person_id,
            "rule_code": "RULE-MOROSIDAD-ARANCEL-30D",
            "origin_condition": "Morosidad de 45 días en cuota #4 de Arancel",
            "restricted_scopes": ["ACADEMIC_NEW_ENROLLMENT", "ACADEMIC_CERTIFICATES"],
            "applied_by": "finanzas@sanbao.cl",
        },
    )
    assert rest_res.status_code == 201
    restriction_id = rest_res.json()["data"]["restriction_id"]
    assert rest_res.json()["data"]["status"] == "ACTIVE"

    # a) Evaluar acceso académico restringido -> debe estar bloqueado (allowed == False)
    eval_acad = client.post(
        "/api/v1/integrations/restrictions/evaluate-access",
        headers=auth_headers,
        json={"person_id": person_id, "access_scope": "ACADEMIC_NEW_ENROLLMENT", "user_role": "ALUMNO"},
    )
    assert eval_acad.status_code == 200
    assert eval_acad.json()["data"]["allowed"] is False

    # b) Evaluar acceso clínico para continuidad de atención de un paciente -> SIEMPRE PERMITIDO (allowed == True)
    eval_clin = client.post(
        "/api/v1/integrations/restrictions/evaluate-access",
        headers=auth_headers,
        json={"person_id": person_id, "access_scope": "CLINICAL_PATIENT_CONTINUITY", "user_role": "ALUMNO_PRACTICA"},
    )
    assert eval_clin.status_code == 200
    assert eval_clin.json()["data"]["allowed"] is True
    assert eval_clin.json()["data"]["clinical_continuity_safeguard_applied"] is True

    # c) Autorizar excepción con vigencia -> habilita acceso académico durante la vigencia
    exc_res = client.post(
        f"/api/v1/integrations/restrictions/{restriction_id}/authorize-exception",
        headers=auth_headers,
        json={
            "authorized_by": "Dirección Académica San Bao",
            "reason": "Compromiso de pago firmado para fin de mes",
            "valid_from": "2026-11-01",
            "valid_until": "2026-11-30",
        },
    )
    assert exc_res.status_code == 200
    assert exc_res.json()["data"]["status"] == "EXCEPTION_AUTHORIZED"

    eval_exc = client.post(
        "/api/v1/integrations/restrictions/evaluate-access",
        headers=auth_headers,
        json={
            "person_id": person_id,
            "access_scope": "ACADEMIC_NEW_ENROLLMENT",
            "user_role": "ALUMNO",
            "evaluation_date": "2026-11-18",
        },
    )
    assert eval_exc.status_code == 200
    assert eval_exc.json()["data"]["allowed"] is True
    assert eval_exc.json()["data"]["exception_applied"] is True

    # d) Publicar evento payment.confirmed -> rehabilita automáticamente la restricción
    pay_evt = client.post(
        "/api/v1/integrations/transactional-bus/publish",
        headers=auth_headers,
        json={
            "idempotency_key": "EVT-PAY-CONF-REHAB-2026-0004",
            "event_name": "payment.confirmed",
            "person_id": person_id,
            "entity_reference": person_id,
        },
    )
    assert pay_evt.status_code == 200
    assert pay_evt.json()["data"]["auto_rehabilitated_restrictions"] >= 1


def test_fase8_financial_intelligence_kpis_aes256_separate_keys_15y_retention_and_portability(test_context):
    """
    Fase 8 (Requerimientos L y M):
    - L: Indicadores de Inteligencia Financiera (Ratio de Berry, DSO, BEP, ROFE, % Ingreso Neto Efectivo de Clientes y COGS)
         con fórmula, fuente, cuentas involucradas, período, nulos, sociedad, centro de costo y fecha/hora <= 24h.
         Bloqueo de mezcla de importes entre sociedades sin regla de consolidación aprobada.
    - M: Cifrado AES-256 de campos sensibles con gestión separada de claves, protección de logs, gestión de incidentes,
         conservación obligatoria de fichas clínicas por al menos 15 años (bloqueo de eliminación) y mecanismo de entrega y portabilidad.
    """
    from app.core.security import AES256FieldCipher, sanitize_sensitive_log_payload

    auth_headers = test_context["auth_headers"]
    instituto_id = test_context["instituto_id"]
    clinica_id = test_context["clinica_id"]

    # 1. Requerimiento L: Impedir mezclar importes de distintas sociedades sin regla de consolidación aprobada
    no_comp_headers = {"Authorization": auth_headers["Authorization"]}
    res_mix_blocked = client.get("/api/v1/bi/financial-intelligence", headers=no_comp_headers)
    assert res_mix_blocked.status_code == 400

    # Consultar Inteligencia Financiera para la sociedad Instituto y un centro de costo específico
    res_fi = client.get(
        f"/api/v1/bi/financial-intelligence?company_id={instituto_id}&period=2026-11&cost_center=CC-101%20Docencia%20y%20Aranceles%20Escuela%20San%20Bao",
        headers=auth_headers,
    )
    assert res_fi.status_code == 200
    fi_data = res_fi.json()["data"]
    assert fi_data["company_id"] == instituto_id
    assert fi_data["max_refresh_interval_hours"] == 24
    assert fi_data["updated_at"] is not None

    indicators = fi_data["indicators"]
    required_kpi_codes = {
        "BERRY_RATIO",
        "DSO",
        "BEP",
        "ROFE",
        "NET_EFFECTIVE_CLIENT_REVENUE_PCT",
        "COGS",
    }
    assert required_kpi_codes.issubset(set(indicators.keys()))

    for code in required_kpi_codes:
        kpi = indicators[code]
        assert kpi["formula"]
        assert kpi["data_source"]
        assert len(kpi["involved_accounts"]) >= 2
        assert kpi["period"] == "2026-11"
        assert kpi["null_handling"]
        assert kpi["company_id"] == instituto_id
        assert kpi["cost_center"] == "CC-101 Docencia y Aranceles Escuela San Bao"
        assert kpi["updated_at"]

    # 2. Requerimiento M: Cifrado AES-256 con clave separada, protección de logs y diagnóstico de cumplimiento técnico
    raw_anamnesis = "Síndrome de Deficiencia de Yin de Riñón con Calor Vacío; pulso filiforme y rápido."
    ciphertext = AES256FieldCipher.encrypt(raw_anamnesis)
    assert ciphertext.startswith("AES256GCM$")
    assert raw_anamnesis not in ciphertext
    assert AES256FieldCipher.decrypt(ciphertext) == raw_anamnesis

    sanitized = sanitize_sensitive_log_payload(
        {"user": "tutor", "password": "123", "traditional_anamnesis": {"pulse": "Xian"}}
    )
    assert sanitized["password"] == "***REDACTED_PROTECTED_LOG***"
    assert sanitized["traditional_anamnesis"] == "***REDACTED_PROTECTED_LOG***"

    comp_status_res = client.get("/api/v1/institutional/auth/security-compliance-status", headers=auth_headers)
    assert comp_status_res.status_code == 200
    cs_data = comp_status_res.json()["data"]
    assert cs_data["aes256_field_encryption_operational"] is True
    assert cs_data["separate_key_management_enforced"] is True
    assert cs_data["clinical_record_retention_years"] == 15

    # Registrar incidente de seguridad en bitácora audit.security_incidents
    sec_inc_res = client.post(
        "/api/v1/institutional/auth/security-incidents",
        headers=auth_headers,
        json={
            "company_id": clinica_id,
            "category": "UNAUTHORIZED_CLINICAL_ACCESS",
            "severity": "ALTA",
            "title": "Intento denegado de acceso de perfil financiero a ficha clínica",
            "description": "Bloqueado automáticamente por guardia RBAC Ley 20.584.",
        },
    )
    assert sec_inc_res.status_code == 201
    assert sec_inc_res.json()["data"]["incident_code"].startswith("SEC-INC-2026-")

    # 3. Requerimiento M: Conservación por al menos 15 años de fichas clínicas y Portabilidad para el paciente
    clin_headers = {"Authorization": auth_headers["Authorization"], "X-Company-ID": clinica_id}
    patients = client.get("/api/v1/clinical/patients", headers=clin_headers).json()["data"]["items"]
    if not patients:
        pat_create = client.post(
            "/api/v1/clinical/patients",
            headers=clin_headers,
            json={"person_id": test_context["docente_person_id"], "blood_type": "A+"},
        )
        patient_id = pat_create.json()["data"]["id"]
    else:
        patient_id = patients[0]["id"]

    practitioners = client.get("/api/v1/clinical/practitioners", headers=clin_headers).json()["data"]
    if not practitioners:
        pr_create = client.post(
            "/api/v1/clinical/practitioners",
            headers=clin_headers,
            json={
                "person_id": test_context["docente_person_id"],
                "license_number": "RNPI-998811",
                "specialty": "Acupuntura",
                "is_tutor": True,
            },
        )
        practitioner_id = pr_create.json()["data"]["id"]
    else:
        practitioner_id = practitioners[0]["id"]

    enc_create = client.post(
        "/api/v1/clinical/encounters",
        headers=clin_headers,
        json={
            "patient_id": patient_id,
            "practitioner_id": practitioner_id,
            "reason_for_consultation": "Lumbalgia crónica por insuficiencia de Yang de Riñón",
            "zang_fu_syndrome": "Deficiencia de Yang de Riñón",
            "therapeutic_principle": "Tonificar y calentar el Yang de Riñón con moxibustión en Du4 y V23",
        },
    )
    assert enc_create.status_code == 201
    encounter_id = enc_create.json()["data"]["id"]

    # Intentar eliminar la ficha clínica antes de 15 años -> bloqueado con 403 Forbidden
    del_res = client.delete(f"/api/v1/clinical/encounters/{encounter_id}", headers=clin_headers)
    assert del_res.status_code == 403
    assert "15 años" in del_res.json()["detail"]

    # Solicitar entrega y portabilidad de la ficha clínica (Ley 20.584 / Ley 21.719)
    port_res = client.get(f"/api/v1/clinical/patients/{patient_id}/portability-export", headers=clin_headers)
    assert port_res.status_code == 200
    port_data = port_res.json()["data"]
    assert port_data["minimum_retention_years"] == 15
    assert port_data["encounters_count"] >= 1
    created_enc = next(e for e in port_data["encounters"] if e["encounter_id"] == encounter_id)
    assert created_enc["aes256_encrypted_at_rest"] is True
    assert created_enc["aes256_integrity_verified"] is True
    assert len(port_data["portability_package_sha256"]) == 64



