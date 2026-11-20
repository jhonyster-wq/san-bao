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


def test_fase4_clinical_field_manager_agenda_segmentation_reas_supplies_and_monthly_closure(client):
    """
    Fase 4:
    - D.1: Agenda por sede/tutor/profesional, confirmaciones, recordatorios 48h y 24h, cancelaciones, NO_SHOW y respeto de consentimientos/Opt-Out.
    - D.2: Segmentación automática semanal de pacientes (ACTIVO <=45d, EN_RIESGO 46-90d, INACTIVO >90d) y campaña de reactivación respetando consentimientos.
    - D.3: Checklist obligatorio de Cierre Sanitario (Decreto 6/2009 REAS / cortopunzantes) con bloqueo si falta control obligatorio y trazabilidad.
    - D.4: Control de insumos por tutor y sesión + KPIs (pacientes atendidos, insumos consumidos, consumo promedio por paciente).
    - D.5: Cierre mensual clínico automático por período, modalidad (Primera sesión, Sesión única, Packs) y prestación (Acupuntura, Tuina, Otras).
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    patients = client.get("/api/v1/clinical/patients", headers=headers).json()["data"]["items"]
    if not patients:
        p_res = client.post(
            "/api/v1/institutional/people",
            headers=headers,
            json={
                "rut": "18.987.654-8",
                "first_name": "Valentina",
                "last_name": "Morales",
                "email": "valentina.morales@sanbao.cl",
                "phone": "+56 9 8899 1122",
            },
        )
        person_id = p_res.json()["data"]["id"]
        pat_res = client.post(
            "/api/v1/clinical/patients",
            headers=headers,
            json={"person_id": person_id, "blood_type": "O+"},
        )
        patient_id = pat_res.json()["data"]["id"]
    else:
        patient_id = patients[0]["id"]

    practitioners = client.get("/api/v1/clinical/practitioners", headers=headers).json()["data"]
    if not practitioners:
        pr_p_res = client.post(
            "/api/v1/institutional/people",
            headers=headers,
            json={
                "rut": "14.234.567-6",
                "first_name": "Master",
                "last_name": "Li",
                "email": "master.li@sanbao.cl",
            },
        )
        pr_res = client.post(
            "/api/v1/clinical/practitioners",
            headers=headers,
            json={
                "person_id": pr_p_res.json()["data"]["id"],
                "license_number": "RNPI-887766-MINSAL",
                "specialty": "Acupuntura",
                "is_tutor": True,
            },
        )
        practitioner_id = pr_res.json()["data"]["id"]
    else:
        practitioner_id = practitioners[0]["id"]

    campuses = client.get("/api/v1/institutional/campuses", headers=headers).json()["data"]
    campus_id = campuses[0]["id"]
    rooms = campuses[0]["rooms"]
    box_room = next((r for r in rooms if r["room_type"] == "CLINICAL_BOX"), rooms[0])

    # Crear cita para pruebas de agenda, recordatorios y cierre mensual
    appt_res = client.post(
        "/api/v1/clinical/appointments",
        headers=headers,
        json={
            "company_id": clinica_id,
            "patient_id": patient_id,
            "practitioner_id": practitioner_id,
            "campus_id": campus_id,
            "room_id": box_room["id"],
            "appointment_date": "2026-11-18",
            "start_time": "16:00",
            "end_time": "17:00",
            "reason": "Primera sesión de Acupuntura y Diagnóstico MTC",
        },
    )
    assert appt_res.status_code == 201
    appt_id = appt_res.json()["data"]["id"]

    # D.1: Confirmar atención y asignar modalidad PRIMERA_SESION y prestación ACUPUNTURA
    res_status = client.put(
        f"/api/v1/clinical/management/appointments/{appt_id}/status-action",
        headers=headers,
        json={
            "action": "CONFIRM",
            "session_modality": "PRIMERA_SESION",
            "service_type": "ACUPUNTURA",
            "amount_paid_clp": 42000,
        },
    )
    assert res_status.status_code == 200
    assert res_status.json()["data"]["status"] == "CONFIRMED"
    assert res_status.json()["data"]["session_modality"] == "PRIMERA_SESION"

    # Enviar recordatorio a 48h y 24h con consentimiento activo
    rem_48 = client.post(
        f"/api/v1/clinical/management/appointments/{appt_id}/reminders",
        headers=headers,
        json={"window_hours": 48, "channel": "WHATSAPP"},
    )
    assert rem_48.status_code == 200
    assert rem_48.json()["data"]["reminder_48h_sent"] is True

    rem_24 = client.post(
        f"/api/v1/clinical/management/appointments/{appt_id}/reminders",
        headers=headers,
        json={"window_hours": 24, "channel": "EMAIL_HTML"},
    )
    assert rem_24.status_code == 200
    assert rem_24.json()["data"]["reminder_24h_sent"] is True

    # Activar Opt-Out del paciente -> debe bloquear el envío de nuevos recordatorios
    consent_res = client.put(
        f"/api/v1/clinical/management/patients/{patient_id}/communication-consent",
        headers=headers,
        json={"comm_opt_out": True, "last_visit_date": "2026-09-10"},
    )
    assert consent_res.status_code == 200
    assert consent_res.json()["data"]["comm_opt_out"] is True

    rem_blocked = client.post(
        f"/api/v1/clinical/management/appointments/{appt_id}/reminders",
        headers=headers,
        json={"window_hours": 24, "channel": "WHATSAPP"},
    )
    assert rem_blocked.status_code == 400

    # D.2: Ejecutar segmentación semanal automática (paciente con última visita 2026-09-10 al 2026-11-18 = 69 días -> EN_RIESGO)
    seg_res = client.post(
        "/api/v1/clinical/management/patients/run-segmentation",
        headers=headers,
        json={"active_max_days": 45, "at_risk_max_days": 90, "reference_date": "2026-11-18"},
    )
    assert seg_res.status_code == 200
    seg_patients = seg_res.json()["data"]["patients"]
    target_pat_seg = next(p for p in seg_patients if p["patient_id"] == patient_id)
    assert target_pat_seg["segment"] == "EN_RIESGO"
    assert target_pat_seg["days_since_last_visit"] == 69

    # Campaña de reactivación debe excluir al paciente con Opt-Out activo
    camp_res = client.post(
        "/api/v1/clinical/management/patients/reactivation-campaign",
        headers=headers,
        json={"target_segments": ["EN_RIESGO", "INACTIVO"], "channel": "WHATSAPP"},
    )
    assert camp_res.status_code == 200
    assert any(p["patient_id"] == patient_id for p in camp_res.json()["data"]["excluded_patients"])

    # D.3: Cierre Sanitario obligatorio (Decreto 6/2009 REAS / cortopunzantes)
    # 1) Si falta confirmar disposición de cortopunzantes REAS -> bloqueado con 400
    san_fail = client.post(
        "/api/v1/clinical/management/sanitary-closure",
        headers=headers,
        json={
            "tutor_id": practitioner_id,
            "sharps_disposal_verified": False,
            "complete_needle_removal_verified": True,
            "box_and_stretcher_sanitized": True,
            "confirmed_by_name": "Dr. Roberto Gómez Valdés",
        },
    )
    assert san_fail.status_code == 400
    assert "REAS" in san_fail.json()["detail"]

    # 2) Con todos los controles obligatorios confirmados -> aprobado y trazado con usuario y timestamp
    san_ok = client.post(
        "/api/v1/clinical/management/sanitary-closure",
        headers=headers,
        json={
            "tutor_id": practitioner_id,
            "sharps_disposal_verified": True,
            "complete_needle_removal_verified": True,
            "box_and_stretcher_sanitized": True,
            "moxa_and_equipment_secured": True,
            "confirmed_by_name": "Dr. Roberto Gómez Valdés",
            "notes": "Contenedor amarillo REAS sellado al 75% y box desinfectado.",
        },
    )
    assert san_ok.status_code == 201
    san_data = san_ok.json()["data"]
    assert san_data["all_mandatory_checks_passed"] is True
    assert san_data["confirmed_by_name"] == "Dr. Roberto Gómez Valdés"
    assert san_data["confirmed_at"] is not None

    # D.4: Control de insumos por tutor y sesión + indicadores por tutor
    sup_res_1 = client.post(
        "/api/v1/clinical/management/tutor-supplies/consume",
        headers=headers,
        json={
            "tutor_id": practitioner_id,
            "session_id": appt_id,
            "patient_id": patient_id,
            "supply_code": "AGU-2530",
            "quantity": 12,
            "consumption_date": "2026-11-18",
        },
    )
    assert sup_res_1.status_code == 201

    kpi_res = client.get(f"/api/v1/clinical/management/tutor-supplies/kpis?tutor_id={practitioner_id}", headers=headers)
    assert kpi_res.status_code == 200
    tutor_kpi = kpi_res.json()["data"]["tutors"][0]
    assert tutor_kpi["patients_attended"] >= 1
    assert tutor_kpi["supplies_consumed"] >= 12
    assert tutor_kpi["average_consumption_per_patient"] > 0

    # D.5: Reporte automático de Cierre Mensual Clínico por modalidad y prestación
    closure_res = client.post(
        "/api/v1/clinical/management/monthly-closure/calculate?period_code=2026-11",
        headers=headers,
    )
    assert closure_res.status_code == 200
    c_data = closure_res.json()["data"]
    assert c_data["period_code"] == "2026-11"
    assert c_data["auto_recalculate_schedule"] == "DAY_1_OF_EACH_MONTH"
    assert c_data["total_attentions"] >= 1
    assert c_data["total_collected_clp"] >= 42000.0
    assert c_data["by_modality"]["PRIMERA_SESION"]["attentions_count"] >= 1
    assert c_data["by_service_type"]["ACUPUNTURA"]["attentions_count"] >= 1

