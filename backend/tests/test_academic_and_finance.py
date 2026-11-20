from datetime import date
from decimal import Decimal
import pytest
from app.modules.institutional.models.company import Company
from app.modules.institutional.models.person import Person
from app.modules.academic.models.student import Student, Enrollment, CohortEnrollment
from app.modules.academic.models.program import Program, Course
from app.modules.academic.models.period import AcademicPeriod, Cohort
from app.modules.finance.models.commitment import PaymentCommitment, Installment


def get_auth_token_and_instituto(client):
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    token = login_res.json()["data"]["access_token"]
    companies = login_res.json()["data"]["available_companies"]
    instituto = next(c for c in companies if "Instituto" in c["legal_name"] or "77123456" in c["rut"])
    return token, instituto["id"]


def test_academic_curriculum_and_program_setup(client):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Crear Programa
    prog_res = client.post(
        "/api/v1/academic/programs",
        headers=headers,
        json={
            "code": "MTC-PRO",
            "name": "Formación Profesional en Acupuntura y Medicina China",
            "degree_title": "Acupunturista y Terapeuta en MTC",
            "total_semesters": 6,
            "min_clinical_hours": 300,
        },
    )
    assert prog_res.status_code == 201
    program_id = prog_res.json()["data"]["id"]

    # 2. Crear Asignaturas
    course_res1 = client.post(
        "/api/v1/academic/programs/courses",
        headers=headers,
        json={
            "code": "MTC-101-PRO",
            "name": "Fundamentos de Medicina Tradicional China",
            "theoretical_hours": 60,
            "practical_hours": 20,
            "clinical_hours": 0,
            "credits": 5,
        },
    )
    assert course_res1.status_code == 201
    course1_id = course_res1.json()["data"]["id"]

    course_res2 = client.post(
        "/api/v1/academic/programs/courses",
        headers=headers,
        json={
            "code": "CLI-301",
            "name": "Práctica Clínica Supervisada I",
            "theoretical_hours": 10,
            "practical_hours": 10,
            "clinical_hours": 80,
            "is_clinical_practice": True,
            "credits": 6,
        },
    )
    assert course_res2.status_code == 201
    course2_id = course_res2.json()["data"]["id"]

    # 3. Crear Malla Curricular y asociar asignaturas
    curr_res = client.post(
        "/api/v1/academic/programs/curriculums",
        headers=headers,
        json={
            "program_id": program_id,
            "code": "MALLA-2026",
            "version_name": "Plan de Estudios 2026",
            "effective_year": 2026,
        },
    )
    assert curr_res.status_code == 201
    curriculum_id = curr_res.json()["data"]["id"]

    add_res = client.post(
        f"/api/v1/academic/programs/curriculums/{curriculum_id}/courses",
        headers=headers,
        json={"course_id": course1_id, "semester": 1, "is_mandatory": True},
    )
    assert add_res.status_code == 200


def test_full_enrollment_with_automatic_tuition_commitment(client):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Crear Período Académico
    period_res = client.post(
        "/api/v1/academic/periods",
        headers=headers,
        json={
            "code": "2026-1",
            "name": "Primer Semestre 2026",
            "year": 2026,
            "semester_number": 1,
            "start_date": "2026-03-01",
            "end_date": "2026-07-31",
            "is_enrollment_open": True,
        },
    )
    assert period_res.status_code == 201
    period_id = period_res.json()["data"]["id"]

    # 2. Registrar Persona (con RUT chileno válido Módulo 11)
    person_res = client.post(
        "/api/v1/institutional/people",
        headers=headers,
        json={
            "rut": "15.678.910-0",
            "first_name": "Catalina",
            "last_name": "Valenzuela",
            "email": "catalina.valenzuela@sanbao.cl",
            "phone": "+56 9 7788 9900",
        },
    )
    assert person_res.status_code == 201
    person_id = person_res.json()["data"]["id"]

    # 3. Admitir como Estudiante
    student_res = client.post(
        "/api/v1/academic/students",
        headers=headers,
        json={"person_id": person_id, "admission_date": "2026-02-15"},
    )
    assert student_res.status_code == 201
    student_data = student_res.json()["data"]
    student_id = student_data["id"]
    assert "MAT-2026" in student_data["student_number"]

    # 4. Obtener Programa creado previamente
    prog_res = client.get("/api/v1/academic/programs", headers=headers)
    program_id = prog_res.json()["data"][0]["id"]

    # 5. Formalizar Matrícula con Arancel de $2.500.000 en 10 cuotas
    enroll_payload = {
        "student_id": student_id,
        "program_id": program_id,
        "academic_period_id": period_id,
        "enrollment_date": "2026-02-20",
        "total_tuition_amount": "2500000",
        "installments_count": 10,
        "first_due_date": "2026-03-05",
    }
    enroll_res = client.post(
        "/api/v1/academic/students/enrollments",
        headers=headers,
        json=enroll_payload,
    )
    assert enroll_res.status_code == 201
    enrollment_id = enroll_res.json()["data"]["id"]

    # 6. VERIFICACIÓN FINANCIERA: Comprobar que se generó el compromiso y sus 10 cuotas
    commitments_res = client.get(
        f"/api/v1/finance/commitments?person_id={person_id}",
        headers=headers,
    )
    assert commitments_res.status_code == 200
    commitments = commitments_res.json()["data"]
    assert len(commitments) == 1
    tuition_commitment = commitments[0]
    assert Decimal(str(tuition_commitment["total_amount"])) == Decimal("2500000")
    assert Decimal(str(tuition_commitment["balance"])) == Decimal("2500000")
    assert len(tuition_commitment["installments"]) == 10
    # Cada cuota debe ser de $250.000
    assert Decimal(str(tuition_commitment["installments"][0]["amount"])) == Decimal("250000")


def test_payment_recording_and_debt_reduction(client):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # Buscar la persona matriculada
    commitments_res = client.get("/api/v1/finance/commitments", headers=headers)
    assert len(commitments_res.json()["data"]) > 0
    commitment = commitments_res.json()["data"][0]
    person_id = commitment["person_id"]

    # 1. Registrar Pago de $500.000 (cubre exactamente las cuotas 1 y 2)
    pay_res = client.post(
        "/api/v1/finance/payments",
        headers=headers,
        json={
            "company_id": instituto_id,
            "person_id": person_id,
            "amount": "500000",
            "payment_method": "TRANSFER",
            "reference_number": "TRF-BANCO-CHILE-998811",
            "notes": "Pago cuotas marzo y abril",
        },
    )
    assert pay_res.status_code == 201
    pay_data = pay_res.json()["data"]
    assert Decimal(str(pay_data["amount"])) == Decimal("500000")
    # Debe tener 2 aplicaciones (cuota 1 y cuota 2)
    assert len(pay_data["allocations"]) == 2

    # 2. Consultar estado financiero actualizado del estudiante
    status_res = client.get(
        f"/api/v1/finance/payments/students/{person_id}/status",
        headers=headers,
    )
    assert status_res.status_code == 200
    financial_status = status_res.json()["data"]
    assert Decimal(str(financial_status["total_paid"])) == Decimal("500000")
    assert Decimal(str(financial_status["total_balance"])) == Decimal("2000000")


def test_cohort_evaluation_and_grading_flow(client):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Obtener período y curso
    periods = client.get("/api/v1/academic/periods", headers=headers).json()["data"]
    period_id = periods[0]["id"]

    programs = client.get("/api/v1/academic/programs", headers=headers).json()["data"]
    program_id = programs[0]["id"]

    # 2. Registrar asignatura y abrir Cohorte/Sección
    course_res = client.post(
        "/api/v1/academic/programs/courses",
        headers=headers,
        json={"code": "PULSO-201", "name": "Semiología del Pulso y Lengua en MTC", "credits": 4},
    )
    course_id = course_res.json()["data"]["id"]

    cohort_res = client.post(
        "/api/v1/academic/periods/cohorts",
        headers=headers,
        json={
            "course_id": course_id,
            "academic_period_id": period_id,
            "code": "SECC-PULSO-01",
            "quota": 25,
        },
    )
    assert cohort_res.status_code == 201
    cohort_id = cohort_res.json()["data"]["id"]

    # 3. Obtener el estudiante que tiene compromiso financiero creado en test_full_enrollment_with_automatic_tuition_commitment
    students = client.get("/api/v1/academic/students", headers=headers).json()["data"]
    student = next((s for s in students if s.get("student_number") == "SANBAO-2026-001"), students[-1])
    student_id = student["id"]

    # Matricular en la cohorte
    # Obtener el enrollment_id
    commitments = client.get(f"/api/v1/finance/commitments?person_id={student['person_id']}", headers=headers).json()["data"]
    enrollment_id = commitments[0]["enrollment_id"]

    cohort_enroll_res = client.post(
        "/api/v1/academic/students/enrollments/cohorts",
        headers=headers,
        json={"enrollment_id": enrollment_id, "cohort_id": cohort_id},
    )
    assert cohort_enroll_res.status_code == 201

    # 4. Programar 2 Evaluaciones (50% y 50%)
    eval1_res = client.post(
        "/api/v1/academic/students/evaluations",
        headers=headers,
        json={
            "cohort_id": cohort_id,
            "name": "Certamen Teórico de Pulso",
            "weight_percentage": "50.0",
            "evaluation_date": "2026-05-10",
        },
    )
    assert eval1_res.status_code == 201
    eval1_id = eval1_res.json()["data"]["id"]

    eval2_res = client.post(
        "/api/v1/academic/students/evaluations",
        headers=headers,
        json={
            "cohort_id": cohort_id,
            "name": "Evaluación Práctica de Lengua y Diagnóstico",
            "weight_percentage": "50.0",
            "evaluation_date": "2026-06-20",
        },
    )
    assert eval2_res.status_code == 201
    eval2_id = eval2_res.json()["data"]["id"]

    # 5. Calificar al estudiante (escala chilena 1.0 a 7.0)
    grade1_res = client.post(
        f"/api/v1/academic/students/evaluations/{eval1_id}/grades",
        headers=headers,
        json={"student_id": student_id, "score": "5.5", "feedback": "Buen reconocimiento de pulso tenso"},
    )
    assert grade1_res.status_code == 200

    grade2_res = client.post(
        f"/api/v1/academic/students/evaluations/{eval2_id}/grades",
        headers=headers,
        json={"student_id": student_id, "score": "6.5", "feedback": "Excelente diagnóstico diferencial"},
    )
    assert grade2_res.status_code == 200

    # 6. Intentar registrar una nota fuera de rango (ej: 7.5 o 0.5) y verificar validación
    invalid_grade_res = client.post(
        f"/api/v1/academic/students/evaluations/{eval1_id}/grades",
        headers=headers,
        json={"student_id": student_id, "score": "8.0"},
    )
    assert invalid_grade_res.status_code == 422 or invalid_grade_res.status_code == 400


def test_clinical_practice_hours_logging(client):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    students = client.get("/api/v1/academic/students", headers=headers).json()["data"]
    student = next((s for s in students if s.get("student_number") == "SANBAO-2026-001"), students[-1])
    student_id = student["id"]

    # Consultar horas previas antes de acreditar
    pre_summary = client.get(
        f"/api/v1/academic/students/{student_id}/clinical-hours/summary",
        headers=headers,
    ).json()["data"]["total_approved_hours"]

    # Usar al administrador como tutor clínico
    login_info = client.get("/api/v1/institutional/auth/me", headers=headers).json()["data"]
    user_person_id = client.get("/api/v1/institutional/people", headers=headers).json()["data"]["items"][0]["id"]

    # Acreditar sesión de práctica clínica de 4 horas
    hours_res = client.post(
        "/api/v1/academic/students/clinical-hours",
        headers=headers,
        json={
            "student_id": student_id,
            "tutor_id": user_person_id,
            "activity_date": "2026-05-15",
            "hours_completed": 4,
            "comments": "Atención supervisada de paciente con síndrome de insuficiencia de Qi de Bazo",
        },
    )
    assert hours_res.status_code == 201

    # Acreditar otra sesión de 3 horas
    hours_res2 = client.post(
        "/api/v1/academic/students/clinical-hours",
        headers=headers,
        json={
            "student_id": student_id,
            "tutor_id": user_person_id,
            "activity_date": "2026-05-22",
            "hours_completed": 3,
            "comments": "Tratamiento acupuntural en canal Tai Yin",
        },
    )
    assert hours_res2.status_code == 201

    # Consultar resumen acumulado: debe sumar +7 horas adicionales
    summary_res = client.get(
        f"/api/v1/academic/students/{student_id}/clinical-hours/summary",
        headers=headers,
    )
    assert summary_res.status_code == 200
    assert summary_res.json()["data"]["total_approved_hours"] == pre_summary + 7


def test_fase5_finance_exemptions_packs_reversals_oc_3way_reconciliation_dte_and_honorarios(client, db_session):
    """
    Fase 5:
    - E.1: Excepciones de cobro académico (PAGADO, PENDIENTE, MOROSO, EXENTO; tipos BECA, PRÁCTICA, CONGELAMIENTO) sin eliminar cargo.
    - E.2: Packs de sesiones clínicas con estados VIGENTE, AGOTADO, ANULADO.
    - E.3: Reversos de pagos sin eliminar el pago original, con motivo, usuario responsable, fecha, monto y referencia contable.
    - E.4, E.5 y E.6: Tesorería dual por sociedad, Órdenes de Compra obligatorias imputadas a centro de costo y alertas de sobregiro.
    - F: Conciliación bancaria automática de 3 vías (Cartola <-> Pagos <-> Asientos), cola de revisión e impedimento de doble conciliación.
    - G: DTE SII con clasificación tributaria parametrizable y bloqueo de doble emisión por operación.
    - H: Liquidación de honorarios Ley 21.133 desde horas académicas y clínicas validadas (Bruto = horas x valor hora, Retención = bruto x tasa vigente, Líquido = bruto - retención).
    """
    from app.modules.finance.models.commitment import Payment, Installment, FinanceJournalEntry
    from app.modules.clinical.models.patient import Patient
    from app.modules.institutional.models.person import Person

    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # Inicializar datos maestros del hub financiero
    col_res = client.get("/api/v1/finance/hub/collections", headers=headers)
    assert col_res.status_code == 200

    # E.1: Aplicar excepción de cobro académico (BECA) sobre una cuota pendiente sin eliminar el cargo original
    target_inst = db_session.query(Installment).filter(Installment.balance > 0).first()
    assert target_inst is not None
    original_charge = float(target_inst.amount)

    ex_res = client.post(
        f"/api/v1/finance/hub/installments/{target_inst.id}/apply-exemption",
        headers=headers,
        json={
            "exemption_type": "BECA",
            "reason": "Beca de Excelencia Académica Semestre 2026-2",
            "valid_from": "2026-08-01",
            "valid_until": "2026-12-31",
            "authorized_by": "Comité de Becas & Dirección de Finanzas",
        },
    )
    assert ex_res.status_code == 200
    ex_data = ex_res.json()["data"]
    assert ex_data["status"] == "EXENTO"
    assert ex_data["exemption_type"] == "BECA"
    assert ex_data["original_charge_amount_preserved"] == original_charge
    assert ex_data["current_balance"] == 0.0

    # E.2: Packs de sesiones clínicas (VIGENTE -> AGOTADO -> ANULADO)
    patient = db_session.query(Patient).first()
    if not patient:
        person = db_session.query(Person).first()
        patient = Patient(person_id=person.id, record_number="FICH-2026-8801", is_active=True)
        db_session.add(patient)
        db_session.commit()

    pack_res = client.post(
        "/api/v1/finance/hub/clinical-packs",
        headers=headers,
        json={
            "patient_id": patient.id,
            "service_type": "ACUPUNTURA",
            "total_sessions": 2,
            "used_sessions": 1,
            "amount_paid_clp": 65000,
            "cost_center": "CC-201 Clínica San Bao - Acupuntura Providencia",
        },
    )
    assert pack_res.status_code == 201
    pack_data = pack_res.json()["data"]
    pack_id = pack_data["pack_id"]
    assert pack_data["status"] == "VIGENTE"

    # Consumir la sesión restante -> pasa a AGOTADO
    pack_use_res = client.put(
        f"/api/v1/finance/hub/clinical-packs/{pack_id}/status",
        headers=headers,
        json={"action": "CONSUME", "sessions_to_use": 1},
    )
    assert pack_use_res.status_code == 200
    assert pack_use_res.json()["data"]["status"] == "AGOTADO"

    # E.3: Reversos de pagos (sin eliminar nunca el pago original)
    target_payment = db_session.query(Payment).filter(Payment.is_reversed == False).first()
    assert target_payment is not None
    orig_pay_id = target_payment.id

    rev_res = client.post(
        f"/api/v1/finance/hub/payments/{orig_pay_id}/reverse",
        headers=headers,
        json={
            "reason": "Devolución por pago duplicado en transferencia electrónica",
            "responsible_user": "auditor.finanzas@sanbao.cl",
        },
    )
    assert rev_res.status_code == 201
    rev_data = rev_res.json()["data"]
    assert rev_data["original_payment_id"] == orig_pay_id
    assert rev_data["original_payment_preserved"] is True
    assert rev_data["accounting_reference"].startswith("ASI-REV-")
    # Verificar en BD que el pago original sigue existiendo
    assert db_session.query(Payment).filter(Payment.id == orig_pay_id).first() is not None

    # E.4, E.5 y E.6: Órdenes de Compra obligatorias imputadas a Centro de Costo y alerta de sobregiro
    # 1) Intentar registrar una compra sin Orden de Compra -> bloqueado con 400
    no_oc_res = client.post(
        "/api/v1/finance/hub/purchases",
        headers=headers,
        json={"document_number": "FAC-SIN-OC-001"},
    )
    assert no_oc_res.status_code == 400

    # 2) Emitir Orden de Compra por monto alto para verificar alerta de sobregiro e imputar compra
    oc_res = client.post(
        "/api/v1/finance/hub/purchase-orders",
        headers=headers,
        json={
            "company_key": "clinica",
            "supplier_rut": "76.501.220-8",
            "supplier_name": "Importadora Insumos Acupuntura Pacífico SpA",
            "cost_center": "CC-201 Clínica San Bao - Acupuntura Providencia",
            "concept": "Equipamiento Electroacupuntura y Agujas Anuales",
            "total_amount_clp": 25000000,
        },
    )
    assert oc_res.status_code == 201
    oc_data = oc_res.json()["data"]
    assert oc_data["overdraft_alert"] is True
    oc_id = oc_data["purchase_order_id"]

    pur_res = client.post(
        "/api/v1/finance/hub/purchases",
        headers=headers,
        json={"purchase_order_id": oc_id, "document_number": "FAC-CON-OC-101"},
    )
    assert pur_res.status_code == 201
    assert pur_res.json()["data"]["oc_number"] == oc_data["oc_number"]

    # F: Conciliación Bancaria Automática de 3 Vías (Cartola <-> Pagos <-> Asientos)
    person = db_session.query(Person).first()
    ref_3way = "TRF-3WAY-2026-7788"
    p_3way = Payment(
        company_id=instituto_id,
        person_id=person.id,
        payment_date=date(2026, 11, 18),
        amount=Decimal("260000"),
        payment_method="TRANSFER",
        reference_number=ref_3way,
        cost_center="CC-101 Docencia y Aranceles Escuela San Bao",
    )
    je_3way = FinanceJournalEntry(
        company_id=instituto_id,
        entry_number="ASI-3WAY-7788",
        entry_date=date(2026, 11, 18),
        entry_type="INGRESO",
        glosa="Recaudación cuota arancel TRF-3WAY-2026-7788",
        account_debit_code="1.1.01",
        account_debit_name="Caja y Bancos",
        account_credit_code="1.1.02",
        account_credit_name="CxC Aranceles",
        amount=Decimal("260000"),
        cost_center="CC-101 Docencia y Aranceles Escuela San Bao",
        reference_doc=ref_3way,
        status="POSTED",
    )
    db_session.add_all([p_3way, je_3way])
    db_session.commit()

    rec_3way_res = client.post(
        "/api/v1/finance/hub/reconciliation-3way/run",
        headers=headers,
        json={
            "company_id": instituto_id,
            "statement_lines": [
                {
                    "statement_line_code": "CART-2026-0001",
                    "transaction_date": "2026-11-18",
                    "reference_number": ref_3way,
                    "description": "Abono transferencia cuota arancel",
                    "amount_clp": 260000,
                    "movement_nature": "ABONO",
                },
                {
                    "statement_line_code": "CART-2026-0002",
                    "transaction_date": "2026-11-18",
                    "reference_number": "COM-BANC-99",
                    "description": "Cargo comisión mantención cuenta corriente",
                    "amount_clp": 14500,
                    "movement_nature": "COMISION",
                },
            ],
        },
    )
    assert rec_3way_res.status_code == 200
    rec_3way_data = rec_3way_res.json()["data"]
    assert rec_3way_data["auto_reconciled_count"] == 1
    assert rec_3way_data["review_queue_count"] == 1
    assert rec_3way_data["review_queue"][0]["review_status"] == "PENDIENTE_REVISION"

    # Intentar conciliar el mismo movimiento bancario por segunda vez -> bloqueado con 400
    dup_rec_res = client.post(
        "/api/v1/finance/hub/reconciliation-3way/run",
        headers=headers,
        json={
            "company_id": instituto_id,
            "statement_lines": [
                {
                    "statement_line_code": "CART-2026-0001",
                    "transaction_date": "2026-11-18",
                    "reference_number": ref_3way,
                    "amount_clp": 260000,
                }
            ],
        },
    )
    assert dup_rec_res.status_code == 400

    # G: Emisión controlada de DTE SII y bloqueo de doble facturación para la misma operación
    dte_1 = client.post(
        "/api/v1/finance/hub/dte/emit-controlled",
        headers=headers,
        json={
            "company_id": instituto_id,
            "source_operation_key": "OP-CUOTA-2026-99001",
            "operation_type": "ARANCEL_EDUCACIONAL",
            "receiver_rut": "19876543-0",
            "receiver_name": "Diego Valenzuela Rojas",
            "total_amount": 260000,
        },
    )
    assert dte_1.status_code == 201
    assert dte_1.json()["data"]["dte_type"] == 41

    # Intentar emitir un segundo DTE para la misma operación OP-CUOTA-2026-99001 -> bloqueado con 400
    dte_dup = client.post(
        "/api/v1/finance/hub/dte/emit-controlled",
        headers=headers,
        json={
            "company_id": instituto_id,
            "source_operation_key": "OP-CUOTA-2026-99001",
            "operation_type": "ARANCEL_EDUCACIONAL",
            "total_amount": 260000,
        },
    )
    assert dte_dup.status_code == 400

    # H: Liquidación de honorarios Ley 21.133 parametrizable desde horas académicas y clínicas validadas
    rate_res = client.put(
        "/api/v1/finance/hub/honorarios/retention-rates",
        headers=headers,
        json={"period_year": 2026, "retention_rate_pct": 15.25},
    )
    assert rate_res.status_code == 200
    assert rate_res.json()["data"]["retention_rate_pct"] == 15.25

    liq_res = client.post(
        "/api/v1/finance/hub/honorarios/liquidate-from-hours",
        headers=headers,
        json={
            "period_year": 2026,
            "period_month": 11,
            "academic_hours": 12,
            "clinical_hours": 8,
            "hourly_rate_clp": 25000,
            "cost_center": "CC-101 Docencia y Aranceles Escuela San Bao",
        },
    )
    assert liq_res.status_code == 201
    liq_data = liq_res.json()["data"]
    # Total horas = 20 * $25.000 = $500.000 Bruto
    # Retención 15.25% = $76.250
    # Líquido = $423.750
    assert liq_data["total_hours_validated"] == 20.0
    assert liq_data["gross_amount_clp"] == 500000.0
    assert liq_data["retention_rate_pct"] == 15.25
    assert liq_data["retention_amount_clp"] == 76250.0
    assert liq_data["net_amount_clp"] == 423750.0
    assert "BHE-2026-" in liq_data["previred_sii_export_record"]

