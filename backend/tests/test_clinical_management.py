from datetime import date
from decimal import Decimal
import pytest
from app.modules.clinical.models.patient import Patient
from app.modules.clinical.models.practitioner import Practitioner
from app.modules.clinical.models.appointment import Appointment
from app.modules.clinical.models.encounter import ClinicalEncounter
from app.modules.clinical.models.access_log import ClinicalAccessLog


def get_auth_token_and_clinica(client):
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    token = login_res.json()["data"]["access_token"]
    companies = login_res.json()["data"]["available_companies"]
    clinica = next(c for c in companies if "Clínicos" in c["legal_name"] or "76987654" in c["rut"])
    return token, clinica["id"]


def test_patient_registration_and_record_number(client):
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Registrar Persona Física como Paciente
    person_res = client.post(
        "/api/v1/institutional/people",
        headers=headers,
        json={
            "rut": "18.987.654-8",
            "first_name": "Valentina",
            "last_name": "Morales",
            "second_last_name": "Silva",
            "email": "valentina.morales@sanbao.cl",
            "phone": "+56 9 8899 1122",
            "gender": "FEMALE",
        },
    )
    assert person_res.status_code == 201
    person_id = person_res.json()["data"]["id"]

    # 2. Crear Ficha de Paciente en Clínica San Bao
    patient_res = client.post(
        "/api/v1/clinical/patients",
        headers=headers,
        json={
            "person_id": person_id,
            "emergency_contact_name": "Rodrigo Morales",
            "emergency_contact_phone": "+56 9 1122 3344",
            "emergency_contact_relationship": "Padre",
            "blood_type": "O+",
            "allergies": ["Penicilina", "AINEs"],
            "chronic_conditions": ["Cefaleas tensionales frecuentes"],
            "general_notes": "Paciente consulta por insomnio y contracturas cervicales",
        },
    )
    assert patient_res.status_code == 201
    patient_data = patient_res.json()["data"]
    assert "FICH-" in patient_data["record_number"]
    assert patient_data["blood_type"] == "O+"
    assert "Penicilina" in patient_data["allergies"]


def test_practitioner_registration(client):
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # Registrar persona para el terapeuta / tutor
    person_res = client.post(
        "/api/v1/institutional/people",
        headers=headers,
        json={
            "rut": "14.234.567-6",
            "first_name": "Master",
            "last_name": "Li",
            "email": "master.li@sanbao.cl",
            "phone": "+56 9 1234 5678",
        },
    )
    assert person_res.status_code == 201
    person_id = person_res.json()["data"]["id"]

    # Registrar como Profesional y Tutor Clínico
    practitioner_res = client.post(
        "/api/v1/clinical/practitioners",
        headers=headers,
        json={
            "person_id": person_id,
            "license_number": "RNPI-887766-MINSAL",
            "specialty": "Acupuntura, Moxibustión y Fitoterapia Tradicional China",
            "is_tutor": True,
        },
    )
    assert practitioner_res.status_code == 201
    prac_data = practitioner_res.json()["data"]
    assert prac_data["is_tutor"] is True
    assert prac_data["license_number"] == "RNPI-887766-MINSAL"


def test_appointment_booking_and_box_conflict_detection(client):
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # Obtener paciente, terapeuta, sede y box clínico
    patients = client.get("/api/v1/clinical/patients", headers=headers).json()["data"]["items"]
    patient_id = patients[0]["id"]

    practitioners = client.get("/api/v1/clinical/practitioners", headers=headers).json()["data"]
    practitioner_id = practitioners[0]["id"]

    campuses = client.get("/api/v1/institutional/campuses", headers=headers).json()["data"]
    campus_id = campuses[0]["id"]
    box_room = next(r for r in campuses[0]["rooms"] if r["room_type"] == "CLINICAL_BOX")
    box_id = box_room["id"]

    # 1. Agendar cita exitosa de 10:00 a 11:00
    appt_payload = {
        "company_id": clinica_id,
        "patient_id": patient_id,
        "practitioner_id": practitioner_id,
        "campus_id": campus_id,
        "room_id": box_id,
        "appointment_date": "2026-06-15",
        "start_time": "10:00",
        "end_time": "11:00",
        "reason": "Evaluación diagnóstica MTC por lumbalgia",
    }
    appt_res = client.post(
        "/api/v1/clinical/appointments",
        headers=headers,
        json=appt_payload,
    )
    assert appt_res.status_code == 201

    # 2. Intentar agendar otra cita en el mismo box en horario solapado (10:30 a 11:30)
    conflict_payload = {
        "company_id": clinica_id,
        "patient_id": patient_id,
        "practitioner_id": practitioner_id,
        "campus_id": campus_id,
        "room_id": box_id,
        "appointment_date": "2026-06-15",
        "start_time": "10:30",
        "end_time": "11:30",
        "reason": "Intento de sobrecupo en mismo box",
    }
    conflict_res = client.post(
        "/api/v1/clinical/appointments",
        headers=headers,
        json=conflict_payload,
    )
    # Debe rechazar por conflicto de horario en el box
    assert conflict_res.status_code == 400


def test_tcm_encounter_flow_and_academic_hours_cross_accreditation(client):
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Recuperar Paciente, Profesional y un Alumno de la Escuela
    patient = client.get("/api/v1/clinical/patients", headers=headers).json()["data"]["items"][0]
    practitioner = client.get("/api/v1/clinical/practitioners", headers=headers).json()["data"][0]
    students = client.get("/api/v1/academic/students", headers=headers).json()["data"]
    student_id = students[0]["id"] if students else None

    # Horas previas del alumno antes de la sesión
    initial_hours = 0
    if student_id:
        initial_hours_res = client.get(
            f"/api/v1/academic/students/{student_id}/clinical-hours/summary",
            headers=headers,
        )
        initial_hours = initial_hours_res.json()["data"]["total_approved_hours"]

    # 2. Registrar Atención Clínica de MTC realizada por el Alumno bajo Supervisión
    encounter_payload = {
        "patient_id": patient["id"],
        "practitioner_id": practitioner["id"],
        "student_id": student_id,
        "reason_for_consultation": "Cefalea pulsátil frontal, dolor en hipocondrios y fatiga postprandial",
        "current_illness_history": "Cuadro de 3 meses de evolución agravado por estrés laboral.",
        "traditional_anamnesis": {
            "sleep": "Despertares nocturnos entre 1:00 y 3:00 AM (horario de Hígado)",
            "appetite_digestion": "Distensión abdominal tras ingerir alimentos grasos o fríos",
            "thirst": "Deseo de bebidas a temperatura tibia, boca amarga por las mañanas",
            "emotional_state": "Irritabilidad frecuente y frustración",
        },
        "tongue_diagnosis": {
            "body_color": "Rojo en los bordes",
            "body_shape": "Hinchada con marcas dentales moderadas",
            "coating_color": "Blanca fina en el centro, algo amarilla en la raíz",
            "coating_moisture": "Normal a ligeramente pegajosa",
        },
        "pulse_diagnosis": {
            "left_wrist": {"cun": "Normal", "guan": "Tenso (Xian)", "chi": "Profundo y débil"},
            "right_wrist": {"cun": "Normal", "guan": "Débil y resbaladizo (Hua)", "chi": "Normal"},
            "general_qualities": ["Tenso", "Resbaladizo en Bazo"],
            "rate_bpm": 74,
        },
        "zang_fu_syndrome": "Estancamiento de Qi de Hígado con Insuficiencia de Qi de Bazo (Madera ataca a la Tierra)",
        "therapeutic_principle": "Drenar el Qi de Hígado, armonizar y tonificar el Qi de Bazo y Calmar el Shen",
        "treatment_plan": {
            "acupuncture_points": ["H3 (Taichong)", "IG4 (Hegu)", "B6 (Sanyinjiao)", "E36 (Zusanli)", "Yintang"],
            "needle_technique": "Dispersión suave en Cuatro Barreras (H3 + IG4), tonificación en B6 y E36",
            "moxibustion": "Moxa indirecta en aguja en E36 durante 15 minutos",
            "auriculotherapy": ["Shenmen", "Hígado", "Bazo"],
        },
        "recommendations": "Evitar comidas picantes, ultraprocesadas y café; incorporar infusiones de Manzanilla y Menta.",
    }

    enc_res = client.post(
        "/api/v1/clinical/encounters",
        headers=headers,
        json=encounter_payload,
    )
    assert enc_res.status_code == 201
    enc_data = enc_res.json()["data"]
    encounter_id = enc_data["id"]
    # Como intervino un alumno en práctica, debe quedar inicialmente en DRAFT
    assert enc_data["status"] == "DRAFT"
    assert "H3 (Taichong)" in enc_data["treatment_plan"]["acupuncture_points"]

    # 3. El Tutor Clínico revisa, califica y firma electrónicamente la atención
    sign_payload = {
        "tutor_feedback": "Excelente diagnóstico diferencial de Madera atacando Tierra. Puntos bien seleccionados y adecuada manipulación.",
        "tutor_grade": "6.8",
        "hours_to_credit": 3,
    }
    sign_res = client.post(
        f"/api/v1/clinical/encounters/{encounter_id}/sign",
        headers=headers,
        json=sign_payload,
    )
    assert sign_res.status_code == 200
    signed_data = sign_res.json()["data"]
    assert signed_data["status"] == "SIGNED"
    assert signed_data["signed_at"] is not None
    assert Decimal(str(signed_data["tutor_grade"])) == Decimal("6.8")

    # 4. VERIFICACIÓN CRUZADA: Las horas de práctica clínica deben haberse acreditado automáticamente en la Escuela
    if student_id:
        summary_res = client.get(
            f"/api/v1/academic/students/{student_id}/clinical-hours/summary",
            headers=headers,
        )
        assert summary_res.status_code == 200
        new_hours = summary_res.json()["data"]["total_approved_hours"]
        assert new_hours == initial_hours + 3


def test_clinical_access_confidentiality_logs_law_20584(client):
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    patient = client.get("/api/v1/clinical/patients", headers=headers).json()["data"]["items"][0]
    patient_id = patient["id"]

    # Consultar la ficha del paciente para detonar el registro de acceso
    view_res = client.get(
        f"/api/v1/clinical/patients/{patient_id}",
        headers=headers,
    )
    assert view_res.status_code == 200

    # Consultar los logs de auditoría inmutables del paciente
    logs_res = client.get(
        f"/api/v1/clinical/patients/{patient_id}/access-logs",
        headers=headers,
    )
    assert logs_res.status_code == 200
    logs = logs_res.json()["data"]
    assert len(logs) > 0
    actions = [l["action"] for l in logs]
    assert "VIEW_RECORD" in actions


def test_clinical_payment_request_to_finance_flow(client):
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Dirección Clínica crea una solicitud de pago hacia Finanzas con factura adjunta
    create_res = client.post(
        "/api/v1/clinical/management/payment-requests",
        headers=headers,
        json={
            "supplier_rut": "76.501.220-8",
            "supplier_name": "Importadora Insumos Acupuntura Pacífico SpA",
            "invoice_type": "FACTURA_AFECTA_33",
            "invoice_number": "FAC-33-99001",
            "category": "INSUMOS_CLINICOS",
            "campus_code": "SEDE-CENTRAL",
            "amount_clp": 380000,
            "concept": "Compra de 100 cajas de agujas 25x30 y moxa sin humo",
            "attachment_filename": "Factura_DTE33_99001_Pacifico.pdf",
            "attachment_mime_type": "application/pdf",
            "attachment_data_url": "data:application/pdf;base64,JVBERi0xLjQK",
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()["data"]
    req_id = created["id"]
    assert created["status"] == "PENDIENTE_FINANZAS"
    assert created["attachment_filename"] == "Factura_DTE33_99001_Pacifico.pdf"

    # 2. Finanzas visualiza el adjunto e ingresa la factura al Libro de Cuentas por Pagar (CxP)
    reg_res = client.post(
        f"/api/v1/clinical/management/payment-requests/{req_id}/register-payable",
        headers=headers,
    )
    assert reg_res.status_code == 200
    reg_data = reg_res.json()["data"]
    assert reg_data["status"] == "FACTURA_INGRESADA_CXP"
    assert reg_data["payable_id"] is not None

    # 3. Finanzas realiza el pago y el estado de la solicitud de Dirección Clínica cambia a PAGADA
    pay_res = client.post(
        f"/api/v1/clinical/management/payment-requests/{req_id}/pay",
        headers=headers,
        json={
            "payment_method": "TRANSFER",
            "payment_reference": "TRF-SANT-99001",
        },
    )
    assert pay_res.status_code == 200
    paid_data = pay_res.json()["data"]
    assert paid_data["status"] == "PAGADA"
    assert paid_data["payment_reference"] == "TRF-SANT-99001"
    assert paid_data["journal_entry_number"] is not None

    # 4. Dirección Clínica consulta el listado y verifica que figura PAGADA
    list_res = client.get("/api/v1/clinical/management/payment-requests", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()["data"]["items"]
    found = next((x for x in items if x["id"] == req_id), None)
    assert found is not None
    assert found["status"] == "PAGADA"
