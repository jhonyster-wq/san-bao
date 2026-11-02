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
            "email": "marcela.perez@sanbao.cl",
            "gender": "FEMALE",
        },
    )
    if res_person.status_code == 201:
        docente_person = res_person.json()["data"]
    else:
        # Ya existe
        list_p = client.get("/api/v1/institutional/people", headers=auth_headers).json()["data"]["items"]
        docente_person = next(p for p in list_p if "14234567" in p["rut"] or "14.234.567-6" in p["rut"])

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
