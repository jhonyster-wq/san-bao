import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def get_auth_token_and_clinica(client):
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    token = login_res.json()["data"]["access_token"]
    companies = login_res.json()["data"]["available_companies"]
    clinica = next(c for c in companies if "Clínicos" in c["legal_name"] or "76987654" in c["rut"])
    return token, clinica["id"]


def test_clinical_tutors_management_and_block(client: TestClient, db_session: Session):
    """Verifica que Dirección Clínica pueda listar, crear y bloquear/desbloquear tutores clínicos."""
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Listar tutores
    res_list = client.get("/api/v1/clinical/management/tutors", headers=headers)
    assert res_list.status_code == 200
    tutors = res_list.json()["data"]
    assert len(tutors) >= 4

    # 2. Crear nuevo tutor clínico
    new_tutor_payload = {
        "first_name": "Esteban",
        "last_name": "Navarro",
        "rut": "17.654.321-8",
        "specialty": "Acupuntura Bioenergética y Moxibustión",
        "license_number": "SIS-28900",
        "email": "esteban.navarro@sanbao.cl",
    }
    res_create = client.post("/api/v1/clinical/management/tutors", json=new_tutor_payload, headers=headers)
    assert res_create.status_code == 201
    created_id = res_create.json()["data"]["id"]

    # 3. Bloquear tutor
    res_block = client.put(f"/api/v1/clinical/management/tutors/{created_id}/toggle-block", headers=headers)
    assert res_block.status_code == 200
    assert res_block.json()["data"]["is_active"] is False

    # 4. Desbloquear tutor
    res_unblock = client.put(f"/api/v1/clinical/management/tutors/{created_id}/toggle-block", headers=headers)
    assert res_unblock.status_code == 200
    assert res_unblock.json()["data"]["is_active"] is True


def test_clinical_session_prices_management(client: TestClient, db_session: Session):
    """Verifica la administración de valores de sesiones clínicas por Dirección Clínica."""
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Listar aranceles
    res_prices = client.get("/api/v1/clinical/management/session-prices", headers=headers)
    assert res_prices.status_code == 200
    prices = res_prices.json()["data"]
    assert len(prices) >= 5

    # 2. Modificar valor de una sesión
    target_price = prices[0]
    update_payload = {
        "price_clp": 38000,
        "duration_minutes": 60,
    }
    res_update = client.put(f"/api/v1/clinical/management/session-prices/{target_price['id']}", json=update_payload, headers=headers)
    assert res_update.status_code == 200
    assert res_update.json()["data"]["price_clp"] == 38000.0


def test_clinical_shifts_and_practitioner_assignment(client: TestClient, db_session: Session):
    """Verifica el turnero, asignación de terapeutas y cierre oficial de turnos."""
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Listar turnos
    res_shifts = client.get("/api/v1/clinical/management/shifts", headers=headers)
    assert res_shifts.status_code == 200
    shifts = res_shifts.json()["data"]
    assert len(shifts) >= 3

    # 2. Obtener lista de tutores activos para asignar
    res_tutors = client.get("/api/v1/clinical/management/tutors", headers=headers)
    active_tutors = [t for t in res_tutors.json()["data"] if t["is_active"]]
    assert len(active_tutors) >= 2

    # 3. Asignar / reasignar terapeuta a turno
    shift_id = shifts[0]["id"]
    new_practitioner_id = active_tutors[1]["id"]
    res_assign = client.put(
        f"/api/v1/clinical/management/shifts/{shift_id}/assign",
        json={"practitioner_id": new_practitioner_id, "notes": "Reemplazo por docencia"},
        headers=headers,
    )
    assert res_assign.status_code == 200
    assert res_assign.json()["data"]["practitioner_id"] == new_practitioner_id

    # 4. Cierre de turno oficial (cerramos turno de prácticas)
    shift_to_close = shifts[-1]["id"]
    res_close = client.put(f"/api/v1/clinical/management/shifts/{shift_to_close}/close", headers=headers)
    assert res_close.status_code == 200


def test_supplies_stock_and_tutor_metrics(client: TestClient, db_session: Session):
    """Verifica la consulta de stock consolidado de insumos y métricas de consumo por tutor."""
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Stock de insumos (27 ítems)
    res_stock = client.get("/api/v1/clinical/management/supplies/stock", headers=headers)
    assert res_stock.status_code == 200
    stock_items = res_stock.json()["data"]
    assert len(stock_items) == 27
    assert all("current_stock" in item and "status" in item for item in stock_items)

    # 2. Métricas de consumo de insumos por atención por tutor
    res_metrics = client.get("/api/v1/clinical/management/metrics/tutors", headers=headers)
    assert res_metrics.status_code == 200
    metrics_data = res_metrics.json()["data"]
    assert "summary" in metrics_data
    assert "tutors_metrics" in metrics_data
    assert len(metrics_data["tutors_metrics"]) >= 3
    assert metrics_data["summary"]["average_needles_per_attention"] > 0


def test_appointment_booking_governed_by_clinical_management_shifts(client: TestClient, db_session: Session):
    """Verifica que la agenda médica esté estrictamente regida por los turnos y terapeutas de Dirección Clínica."""
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Obtener horas disponibles según turnos de Dirección Clínica para Santiago
    res_slots = client.get("/api/v1/clinical/appointments/available-slots?campus_id=santiago", headers=headers)
    assert res_slots.status_code == 200
    slots_data = res_slots.json()["data"]
    assert len(slots_data) >= 1
    shift_info = slots_data[0]
    assert "TUR-" in shift_info["shift_code"]
    assert "slots" in shift_info
    assert len(shift_info["slots"]) >= 1

    practitioner_id = shift_info["practitioner_id"]
    room_id = shift_info["room_id"]
    campus_id = shift_info["campus_id"]

    # Obtener o crear paciente para agendamiento
    from app.modules.clinical.models.patient import Patient
    from app.modules.institutional.models.person import Person
    p = db_session.query(Person).first()
    patient = db_session.query(Patient).first()
    if not patient:
        patient = Patient(
            person_id=p.id,
            record_number="FICH-STGO-2026-9999",
            is_active=True,
        )
        db_session.add(patient)
        db_session.commit()
    patient_id = patient.id

    today_str = str(date.today())

    # 2. Agendar dentro del turno autorizado (ej: 09:00 a 10:00 o 10:00 a 11:00)
    valid_payload = {
        "company_id": clinica_id,
        "patient_id": patient_id,
        "practitioner_id": practitioner_id,
        "campus_id": campus_id,
        "room_id": room_id,
        "appointment_date": today_str,
        "start_time": "10:00",
        "end_time": "11:00",
        "reason": "Consulta dentro del turno oficial de Dirección Clínica",
    }
    res_valid = client.post("/api/v1/clinical/appointments", json=valid_payload, headers=headers)
    if res_valid.status_code != 201:
        raise RuntimeError(f"Error booking appointment: {res_valid.status_code} - {res_valid.json()}")
    assert res_valid.status_code == 201

    # 3. Intentar agendar fuera de los turnos asignados por Dirección Clínica (ej: 07:00 a 08:00 antes de AM)
    invalid_time_payload = {
        "company_id": clinica_id,
        "patient_id": patient_id,
        "practitioner_id": practitioner_id,
        "campus_id": campus_id,
        "room_id": room_id,
        "appointment_date": today_str,
        "start_time": "07:00",
        "end_time": "08:00",
        "reason": "Intento de agendamiento fuera de turno",
    }
    res_invalid_time = client.post("/api/v1/clinical/appointments", json=invalid_time_payload, headers=headers)
    assert res_invalid_time.status_code == 400
    assert "Dirección Clínica" in res_invalid_time.json()["detail"]

    # 4. Bloquear al terapeuta desde Dirección Clínica e intentar agendar
    # Si tiene turnos activos asignados, debe exigir tutor de reemplazo obligatorio
    res_block_fail = client.put(f"/api/v1/clinical/management/tutors/{practitioner_id}/toggle-block", headers=headers)
    assert res_block_fail.status_code == 400
    assert "obligatorio seleccionar un tutor" in res_block_fail.json()["detail"]

    # Obtener tutor activo de reemplazo desde el listado
    res_tutors = client.get("/api/v1/clinical/management/tutors", headers=headers)
    active_tutors = [t for t in res_tutors.json()["data"] if t["id"] != practitioner_id and t["is_active"]]
    assert len(active_tutors) >= 1
    replacement_tutor_id = active_tutors[0]["id"]

    # Bloquear proveyendo el tutor de reemplazo
    res_block = client.put(
        f"/api/v1/clinical/management/tutors/{practitioner_id}/toggle-block",
        json={"replacement_practitioner_id": replacement_tutor_id, "reason": "Licencia y reemplazo"},
        headers=headers,
    )
    assert res_block.status_code == 200
    assert res_block.json()["data"]["is_active"] is False
    assert res_block.json()["data"]["reassigned_shifts_count"] >= 1

    res_blocked_appt = client.post("/api/v1/clinical/appointments", json=valid_payload, headers=headers)
    assert res_blocked_appt.status_code == 400
    assert "bloqueado o inactivo" in res_blocked_appt.json()["detail"]

    # Desbloquearlo para dejar el estado limpio
    client.put(f"/api/v1/clinical/management/tutors/{practitioner_id}/toggle-block", headers=headers)


def test_clinical_secretary_campus_assignment_and_restriction(client: TestClient, db_session: Session):
    """
    Verifica que la Dirección Clínica pueda asignar secretarias a sedes clínicas específicas,
    y que la sede autorizada se restrinja y refleje en el perfil de la secretaria.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Listar secretarias clínicas y sus sedes
    res_list = client.get("/api/v1/clinical/management/secretaries", headers=headers)
    assert res_list.status_code == 200
    secretaries = res_list.json()["data"]
    assert len(secretaries) >= 2

    sec_valentina = next(s for s in secretaries if s["username"] == "secretaria")
    assert sec_valentina["full_name"] == "Valentina Morales"
    assert "SEDE-CENTRAL" in sec_valentina["campus_code"]

    # 2. Dirección Clínica reasigna a Valentina a Sede Viña del Mar
    val_user_id = sec_valentina["user_id"]
    reassign_payload = {
        "campus_code": "SEDE-VINA",
        "notes": "Reasignación formal por Dirección Clínica a Viña del Mar para cubrir turnos",
    }
    res_assign = client.put(
        f"/api/v1/clinical/management/secretaries/{val_user_id}/campus",
        json=reassign_payload,
        headers=headers,
    )
    assert res_assign.status_code == 200
    data_reassigned = res_assign.json()["data"]
    assert data_reassigned["campus_code"] == "SEDE-VINA"
    assert data_reassigned["campus_key"] == "vina"
    assert "Viña del Mar" in data_reassigned["campus_name"]

    # 3. Consultar /my-campus con usuario secretaria para verificar restricción a Viña del Mar
    res_my_campus = client.get(
        f"/api/v1/clinical/management/secretaries/my-campus?user_id={val_user_id}",
        headers=headers,
    )
    assert res_my_campus.status_code == 200
    my_campus_data = res_my_campus.json()["data"]
    assert my_campus_data["campus_code"] == "SEDE-VINA"
    assert my_campus_data["campus_key"] == "vina"
    assert my_campus_data["is_restricted"] is True

    # 4. Probar login directo con las credenciales de la secretaria
    login_sec = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "secretaria", "password": "SecretariaSanBao2026!"},
    )
    assert login_sec.status_code == 200
    sec_token = login_sec.json()["data"]["access_token"]
    sec_headers = {"Authorization": f"Bearer {sec_token}", "X-Company-ID": clinica_id}

    res_sec_view = client.get("/api/v1/clinical/management/secretaries/my-campus", headers=sec_headers)
    assert res_sec_view.status_code == 200
    assert res_sec_view.json()["data"]["campus_code"] == "SEDE-VINA"
    assert res_sec_view.json()["data"]["campus_key"] == "vina"

    # 5. Dirección Clínica reasigna de regreso a Santiago Providencia
    res_restore = client.put(
        f"/api/v1/clinical/management/secretaries/{val_user_id}/campus",
        json={"campus_code": "SEDE-CENTRAL", "notes": "Retorno a Sede Central Providencia"},
        headers=headers,
    )
    assert res_restore.status_code == 200
    assert res_restore.json()["data"]["campus_code"] == "SEDE-CENTRAL"
    assert res_restore.json()["data"]["campus_key"] == "santiago"


def test_clinical_shifts_acupuntura_and_tuina_schedules(client: TestClient, db_session: Session):
    """
    Verifica que el turnero de Dirección Clínica contemple turnos oficiales diferenciados de Acupuntura y Tui na,
    con sus franjas horarias exactas:
    - AM: 10:00 a 14:00 (Lunes a Sábado)
    - PM: 15:00 a 19:00 (Lunes a Sábado)
    - Vespertino: 18:00 a 22:00 (Lunes a Viernes)
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Listar todos los turnos
    res_all = client.get("/api/v1/clinical/management/shifts", headers=headers)
    assert res_all.status_code == 200
    shifts = res_all.json()["data"]
    assert len(shifts) >= 12

    # 2. Filtrar turnos de Acupuntura
    res_acu = client.get("/api/v1/clinical/management/shifts?service_type=ACUPUNTURA", headers=headers)
    assert res_acu.status_code == 200
    acu_shifts = res_acu.json()["data"]
    assert len(acu_shifts) >= 6
    assert all(s["service_type"] == "ACUPUNTURA" for s in acu_shifts)

    # Verificar horarios Acupuntura
    acu_am = next(s for s in acu_shifts if s["shift_period"] == "AM")
    assert acu_am["start_time"] == "10:00" and acu_am["end_time"] == "14:00"
    assert acu_am["day_schedule"] == "LUNES_A_SABADO"

    acu_pm = next(s for s in acu_shifts if s["shift_period"] == "PM")
    assert acu_pm["start_time"] == "15:00" and acu_pm["end_time"] == "19:00"
    assert acu_pm["day_schedule"] == "LUNES_A_SABADO"

    acu_vesp = next(s for s in acu_shifts if s["shift_period"] == "VESPERTINO")
    assert acu_vesp["start_time"] == "18:00" and acu_vesp["end_time"] == "22:00"
    assert acu_vesp["day_schedule"] == "LUNES_A_VIERNES"

    # 3. Filtrar turnos de Tui na
    res_tui = client.get("/api/v1/clinical/management/shifts?service_type=TUI_NA", headers=headers)
    assert res_tui.status_code == 200
    tui_shifts = res_tui.json()["data"]
    assert len(tui_shifts) >= 6
    assert all(s["service_type"] == "TUI_NA" for s in tui_shifts)

    # Verificar horarios Tui na
    tui_am = next(s for s in tui_shifts if s["shift_period"] == "AM")
    assert tui_am["start_time"] == "10:00" and tui_am["end_time"] == "14:00"
    assert tui_am["day_schedule"] == "LUNES_A_SABADO"

    tui_pm = next(s for s in tui_shifts if s["shift_period"] == "PM")
    assert tui_pm["start_time"] == "15:00" and tui_pm["end_time"] == "19:00"
    assert tui_pm["day_schedule"] == "LUNES_A_SABADO"

    tui_vesp = next(s for s in tui_shifts if s["shift_period"] == "VESPERTINO")
    assert tui_vesp["start_time"] == "18:00" and tui_vesp["end_time"] == "22:00"
    assert tui_vesp["day_schedule"] == "LUNES_A_VIERNES"

    # 4. Crear nuevo turno de Tui na Vespertino vía endpoint POST
    new_shift_payload = {
        "campus_id": acu_am["campus_id"],
        "service_type": "TUI_NA",
        "shift_period": "VESPERTINO",
        "shift_date": acu_am["shift_date"],
        "notes": "Turno adicional de Tui na vespertino creado por Dirección",
    }
    res_create = client.post("/api/v1/clinical/management/shifts", json=new_shift_payload, headers=headers)
    assert res_create.status_code == 201
    assert "TUR-TUI-" in res_create.json()["data"]["shift_code"]


def test_clinical_shift_closure_with_dates_and_reopen(client: TestClient, db_session: Session):
    """
    Verifica que la Dirección Clínica puede cerrar turnos especificando la o las fechas en que
    se suspenderá (fecha única o rango de fechas) y el motivo, y luego reabrirlo formalmente.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Obtener lista de turnos
    res = client.get("/api/v1/clinical/management/shifts", headers=headers)
    assert res.status_code == 200
    shifts = res.json()["data"]
    target_shift = shifts[0]
    shift_id = target_shift["id"]

    # 2. Cierre de turno con Fecha Única (ej. feriado o día específico)
    close_single_payload = {
        "closure_type": "SINGLE_DATE",
        "closure_start_date": "2026-11-03",
        "closure_end_date": "2026-11-03",
        "closure_dates_text": "03/11/2026",
        "closure_reason": "Feriado Nacional / Festivo Oficial",
        "notes": "Suspensión de box por festivo",
    }
    res_close1 = client.put(f"/api/v1/clinical/management/shifts/{shift_id}/close", json=close_single_payload, headers=headers)
    assert res_close1.status_code == 200
    data_close1 = res_close1.json()["data"]
    assert data_close1["status"] == "CLOSED"
    assert data_close1["closure_type"] == "SINGLE_DATE"
    assert data_close1["closure_start_date"] == "2026-11-03"
    assert data_close1["closure_end_date"] == "2026-11-03"
    assert data_close1["closure_dates_text"] == "03/11/2026"
    assert data_close1["closure_reason"] == "Feriado Nacional / Festivo Oficial"

    # 3. Cierre de turno con Rango de Fechas (ej. receso de una semana)
    close_range_payload = {
        "closure_type": "DATE_RANGE",
        "closure_start_date": "2026-11-10",
        "closure_end_date": "2026-11-15",
        "closure_dates_text": "Del 10/11/2026 al 15/11/2026",
        "closure_reason": "Receso Sanitario y Sanitización de Boxes",
        "notes": "Obras y desinfección preventiva",
    }
    res_close2 = client.put(f"/api/v1/clinical/management/shifts/{shift_id}/close", json=close_range_payload, headers=headers)
    assert res_close2.status_code == 200
    data_close2 = res_close2.json()["data"]
    assert data_close2["status"] == "CLOSED"
    assert data_close2["closure_type"] == "DATE_RANGE"
    assert data_close2["closure_start_date"] == "2026-11-10"
    assert data_close2["closure_end_date"] == "2026-11-15"
    assert data_close2["closure_dates_text"] == "Del 10/11/2026 al 15/11/2026"
    assert "Sanitización" in data_close2["closure_reason"]

    # Verificar que el listado de turnos devuelve los campos de fechas de cierre
    res_list = client.get("/api/v1/clinical/management/shifts", headers=headers)
    updated_shift = next(s for s in res_list.json()["data"] if s["id"] == shift_id)
    assert updated_shift["status"] == "CLOSED"
    assert updated_shift["closure_dates_text"] == "Del 10/11/2026 al 15/11/2026"
    assert updated_shift["closure_reason"] == "Receso Sanitario y Sanitización de Boxes"

    # 4. Reabrir turno
    res_reopen = client.put(f"/api/v1/clinical/management/shifts/{shift_id}/reopen", headers=headers)
    assert res_reopen.status_code == 200
    assert res_reopen.json()["data"]["status"] == "OPEN"

    # Confirmar reapertura en listado
    res_list_after = client.get("/api/v1/clinical/management/shifts", headers=headers)
    reopened_shift = next(s for s in res_list_after.json()["data"] if s["id"] == shift_id)
    assert reopened_shift["status"] == "OPEN"
    assert reopened_shift["closure_dates_text"] is None


def test_monthly_calendar_shifts_and_daily_assignment(client: TestClient, db_session: Session):
    """
    Verifica que la asignación de turnos clínicos opera por mes calendario,
    permitiendo consultar la grilla completa del mes y asignar terapeutas por día y turno específico.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Consultar calendario mensual de Noviembre 2026 para Sede Santiago y Acupuntura
    res_cal = client.get(
        "/api/v1/clinical/management/shifts/calendar?year=2026&month=11&campus_id=santiago&service_type=ACUPUNTURA",
        headers=headers,
    )
    assert res_cal.status_code == 200
    cal_data = res_cal.json()["data"]
    assert cal_data["year"] == 2026
    assert cal_data["month"] == 11
    assert cal_data["month_name"] == "Noviembre"
    assert cal_data["num_days"] == 30
    assert len(cal_data["days"]) == 30

    # Días hábiles tienen turnos programados (Lunes a Sábado)
    operating_days = [d for d in cal_data["days"] if d["is_operating_day"]]
    assert len(operating_days) >= 25
    assert all(len(d["shifts"]) >= 2 for d in operating_days)

    # 2. Obtener un terapeuta acreditado para asignación diaria
    res_tutors = client.get("/api/v1/clinical/management/tutors", headers=headers)
    tutors = res_tutors.json()["data"]
    tutor_dr_chen = next(t for t in tutors if "Chen" in t["full_name"])
    tutor_dra_marcela = next(t for t in tutors if "Marcela" in t["full_name"])

    # 3. Asignar terapeuta a un día y turno específico (Día 05 de Noviembre 2026, Turno AM Acupuntura)
    assign_day_payload = {
        "campus_id": "santiago",
        "service_type": "ACUPUNTURA",
        "shift_period": "AM",
        "shift_date": "2026-11-05",
        "practitioner_id": tutor_dr_chen["id"],
        "scope": "SINGLE_DAY",
        "status": "OPEN",
        "notes": "Reemplazo puntual por conferencia de Dra. Marcela Pérez",
    }
    res_assign_day = client.post(
        "/api/v1/clinical/management/shifts/calendar/assign-day",
        json=assign_day_payload,
        headers=headers,
    )
    assert res_assign_day.status_code == 200
    assign_data = res_assign_day.json()["data"]
    assert assign_data["practitioner_id"] == tutor_dr_chen["id"]
    assert assign_data["scope"] == "SINGLE_DAY"
    assert "2026-11-05" in assign_data["target_dates"]

    # 4. Verificar en el calendario que el día 05 de Noviembre tiene asignado al Dr. Chen Lin
    res_cal_updated = client.get(
        "/api/v1/clinical/management/shifts/calendar?year=2026&month=11&campus_id=santiago&service_type=ACUPUNTURA",
        headers=headers,
    )
    day_5 = next(d for d in res_cal_updated.json()["data"]["days"] if d["date"] == "2026-11-05")
    shift_am_day5 = next(s for s in day_5["shifts"] if s["shift_period"] == "AM")
    assert shift_am_day5["practitioner_id"] == tutor_dr_chen["id"]
    assert "Chen" in shift_am_day5["practitioner_name"]

    # 5. Asignación recurrente por día de la semana (todos los Martes del mes para Dra. Marcela en Tui na PM)
    assign_rec_payload = {
        "campus_id": "santiago",
        "service_type": "TUI_NA",
        "shift_period": "PM",
        "shift_date": "2026-11-03",  # Martes 3 Nov 2026
        "practitioner_id": tutor_dra_marcela["id"],
        "scope": "RECURRING_WEEKDAY",
        "status": "OPEN",
        "notes": "Titular de todos los martes del mes",
    }
    res_rec = client.post(
        "/api/v1/clinical/management/shifts/calendar/assign-day",
        json=assign_rec_payload,
        headers=headers,
    )
    assert res_rec.status_code == 200
    rec_data = res_rec.json()["data"]
    assert rec_data["scope"] == "RECURRING_WEEKDAY"
    assert len(rec_data["target_dates"]) >= 4  # 4 martes en Nov 2026


def test_shift_substitute_tutor_optional_and_mandatory_when_active(client: TestClient, db_session: Session):
    """
    Verifica que en la creación de turnos:
    1. El tutor suplente sea opcional por defecto (substitute_active=False).
    2. Sea obligatorio si se activa la opción de suplencia (substitute_active=True).
    3. Impida que el tutor suplente sea el mismo tutor titular.
    4. Se registre y despliegue adecuadamente en los datos del turno.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    res_tutors = client.get("/api/v1/clinical/management/tutors", headers=headers)
    tutors = [t for t in res_tutors.json()["data"] if t["is_active"]]
    assert len(tutors) >= 2
    tutor_titular = tutors[0]
    tutor_suplente = tutors[1]

    # 1. Crear turno sin suplente (opcional por defecto -> substitute_active=False)
    shift_no_sub = {
        "campus_id": "santiago",
        "practitioner_id": tutor_titular["id"],
        "service_type": "ACUPUNTURA",
        "shift_period": "AM",
        "shift_date": "2026-11-16",
        "substitute_active": False,
        "notes": "Turno con suplente inactivo",
    }
    res_no_sub = client.post("/api/v1/clinical/management/shifts", json=shift_no_sub, headers=headers)
    assert res_no_sub.status_code == 201
    assert res_no_sub.json()["data"]["substitute_active"] is False

    # 2. Intentar activar tutor suplente sin especificar id -> debe fallar con 400 (obligatorio si se activa)
    shift_sub_missing = {
        "campus_id": "santiago",
        "practitioner_id": tutor_titular["id"],
        "service_type": "ACUPUNTURA",
        "shift_period": "PM",
        "shift_date": "2026-11-16",
        "substitute_active": True,
        "substitute_practitioner_id": None,
    }
    res_sub_missing = client.post("/api/v1/clinical/management/shifts", json=shift_sub_missing, headers=headers)
    assert res_sub_missing.status_code == 400
    assert "obligatorio seleccionar un tutor suplente" in res_sub_missing.json()["detail"]

    # 3. Intentar asignar al mismo tutor titular como su propio suplente -> debe fallar con 400
    shift_same_sub = {
        "campus_id": "santiago",
        "practitioner_id": tutor_titular["id"],
        "service_type": "ACUPUNTURA",
        "shift_period": "PM",
        "shift_date": "2026-11-16",
        "substitute_active": True,
        "substitute_practitioner_id": tutor_titular["id"],
    }
    res_same = client.post("/api/v1/clinical/management/shifts", json=shift_same_sub, headers=headers)
    assert res_same.status_code == 400
    assert "no puede ser el mismo" in res_same.json()["detail"]

    # 4. Crear turno activando tutor suplente válido -> debe ser exitoso (201)
    shift_valid_sub = {
        "campus_id": "santiago",
        "practitioner_id": tutor_titular["id"],
        "service_type": "ACUPUNTURA",
        "shift_period": "PM",
        "shift_date": "2026-11-16",
        "substitute_active": True,
        "substitute_practitioner_id": tutor_suplente["id"],
        "notes": "Turno con suplencia médica activa",
    }
    res_valid_sub = client.post("/api/v1/clinical/management/shifts", json=shift_valid_sub, headers=headers)
    assert res_valid_sub.status_code == 201
    assert res_valid_sub.json()["data"]["substitute_active"] is True
    assert res_valid_sub.json()["data"]["substitute_practitioner_id"] == tutor_suplente["id"]

    # 5. Asignar suplente por día en calendario (/assign-day)
    day_assign_payload = {
        "campus_id": "santiago",
        "service_type": "TUI_NA",
        "shift_period": "AM",
        "shift_date": "2026-11-17",
        "practitioner_id": tutor_titular["id"],
        "substitute_active": True,
        "substitute_practitioner_id": tutor_suplente["id"],
        "scope": "SINGLE_DAY",
    }
    res_day_sub = client.post("/api/v1/clinical/management/shifts/calendar/assign-day", json=day_assign_payload, headers=headers)
    assert res_day_sub.status_code == 200
    assert res_day_sub.json()["data"]["substitute_active"] is True
    assert res_day_sub.json()["data"]["substitute_practitioner_id"] == tutor_suplente["id"]

    # 6. Consultar en el calendario y verificar que se refleje la suplencia activa
    res_cal = client.get("/api/v1/clinical/management/shifts/calendar?year=2026&month=11&campus_id=santiago", headers=headers)
    day_17 = next(d for d in res_cal.json()["data"]["days"] if d["date"] == "2026-11-17")
    shift_17 = next(s for s in day_17["shifts"] if s["shift_period"] == "AM" and "TUI" in s["service_type"])
    assert shift_17["substitute_active"] is True
    assert shift_17["substitute_practitioner_id"] == tutor_suplente["id"]
    assert shift_17["substitute_practitioner_name"] is not None


def test_tutor_block_requires_active_replacement_when_has_active_shifts(client: TestClient, db_session: Session):
    """
    Verifica que en el listado de tutores clínicos:
    1. Si un tutor no tiene turnos activos, se pueda bloquear directamente.
    2. Si un tutor tiene turnos activos, consultar /active-shifts retorne los turnos.
    3. Si se intenta bloquear sin reemplazo, retorne error 400 exigiendo reemplazo.
    4. Al especificar un tutor activo de reemplazo, reasigne todos sus turnos activos
       al tutor de reemplazo y bloquee exitosamente al tutor original.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Crear nuevo tutor sin turnos
    new_tutor = client.post("/api/v1/clinical/management/tutors", json={
        "first_name": "Claudio",
        "last_name": "Rojas",
        "rut": "16.123.456-7",
        "specialty": "Fitoterapia MTC",
        "license_number": "SIS-29911",
    }, headers=headers).json()["data"]

    # Bloquearlo directamente (no tiene turnos) -> debe permitir sin reemplazo
    res_block_free = client.put(f"/api/v1/clinical/management/tutors/{new_tutor['id']}/toggle-block", headers=headers)
    assert res_block_free.status_code == 200
    assert res_block_free.json()["data"]["is_active"] is False

    # Desbloquearlo
    client.put(f"/api/v1/clinical/management/tutors/{new_tutor['id']}/toggle-block", headers=headers)

    # 2. Asignarle un turno activo para hoy o futuro
    today_str = str(date.today())
    shift_payload = {
        "campus_id": "santiago",
        "practitioner_id": new_tutor["id"],
        "service_type": "ACUPUNTURA",
        "shift_period": "AM",
        "shift_date": today_str,
        "notes": "Turno activo para prueba de bloqueo y reemplazo",
    }
    res_shift = client.post("/api/v1/clinical/management/shifts", json=shift_payload, headers=headers)
    assert res_shift.status_code == 201

    # 3. Consultar endpoint /active-shifts
    res_active = client.get(f"/api/v1/clinical/management/tutors/{new_tutor['id']}/active-shifts", headers=headers)
    assert res_active.status_code == 200
    active_data = res_active.json()["data"]
    assert active_data["has_active_shifts"] is True
    assert active_data["active_shifts_count"] >= 1

    # 4. Intentar bloquear sin proveer tutor de reemplazo -> DEBE RETORNAR 400
    res_block_fail = client.put(f"/api/v1/clinical/management/tutors/{new_tutor['id']}/toggle-block", headers=headers)
    assert res_block_fail.status_code == 400
    assert "obligatorio seleccionar un tutor" in res_block_fail.json()["detail"]

    # 5. Obtener otro tutor activo del listado
    res_tutors = client.get("/api/v1/clinical/management/tutors", headers=headers)
    active_tutors = [t for t in res_tutors.json()["data"] if t["id"] != new_tutor["id"] and t["is_active"]]
    assert len(active_tutors) >= 1
    replacement_tutor = active_tutors[0]

    # 6. Intentar usar un tutor inactivo como reemplazo -> DEBE RETORNAR 400
    # Creamos un tutor inactivo
    blocked_tutor = client.post("/api/v1/clinical/management/tutors", json={
        "first_name": "Inactivo",
        "last_name": "Tutor",
        "rut": "19.987.654-3",
        "specialty": "MTC",
        "license_number": "SIS-99999",
    }, headers=headers).json()["data"]
    client.put(f"/api/v1/clinical/management/tutors/{blocked_tutor['id']}/toggle-block", headers=headers)

    res_block_invalid_rep = client.put(
        f"/api/v1/clinical/management/tutors/{new_tutor['id']}/toggle-block",
        json={"replacement_practitioner_id": blocked_tutor["id"]},
        headers=headers,
    )
    assert res_block_invalid_rep.status_code == 400
    assert "bloqueado o inactivo" in res_block_invalid_rep.json()["detail"]

    # 7. Bloquear proveyendo un tutor activo de reemplazo válido -> ÉXITO (200)
    res_block_ok = client.put(
        f"/api/v1/clinical/management/tutors/{new_tutor['id']}/toggle-block",
        json={"replacement_practitioner_id": replacement_tutor["id"], "reason": "Licencia médica de tutor"},
        headers=headers,
    )
    assert res_block_ok.status_code == 200
    assert res_block_ok.json()["data"]["is_active"] is False
    assert res_block_ok.json()["data"]["reassigned_shifts_count"] >= 1

    # 8. Verificar que los turnos fueron reasignados al tutor de reemplazo
    res_active_after = client.get(f"/api/v1/clinical/management/tutors/{new_tutor['id']}/active-shifts", headers=headers)
    assert res_active_after.json()["data"]["has_active_shifts"] is False
    assert res_active_after.json()["data"]["active_shifts_count"] == 0


def test_tutor_effective_shifts_metrics_report_and_filters(client: TestClient, db_session: Session):
    """
    Verifica el reporte oficial de turnos efectivos por tutor para Dirección Clínica:
    - Validación de cálculo: turnos tomados como titular vs suplente.
    - Despliegue por mes en curso por defecto.
    - Filtro por mes específico y total anual.
    - Filtro por sede (Santiago / Viña del Mar) y especialidad (Acupuntura / Tui na).
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Reporte por defecto (mes en curso)
    res_default = client.get("/api/v1/clinical/management/metrics/effective-shifts", headers=headers)
    assert res_default.status_code == 200
    data_default = res_default.json()["data"]

    assert data_default["filter_applied"]["is_current_month"] is True
    assert data_default["filter_applied"]["is_annual"] is False
    assert "summary" in data_default
    assert data_default["summary"]["total_effective_shifts"] > 0
    assert data_default["summary"]["total_primary_shifts"] > 0
    assert data_default["summary"]["total_substitute_shifts"] >= 0
    assert data_default["summary"]["total_unattended_primary_shifts"] == data_default["summary"]["total_substitute_shifts"]
    assert data_default["summary"]["total_effective_hours"] == data_default["summary"]["total_effective_shifts"] * 4
    # Principio de Unicidad: Cada turno es solo uno y se contabiliza para el tutor principal O para el suplente
    assert data_default["summary"]["total_effective_shifts"] == data_default["summary"]["total_primary_shifts"] + data_default["summary"]["total_substitute_shifts"]

    # Verificar que los tutores tengan métricas separadas de titular y suplente,
    # y que los turnos no asistidos por el titular (donde estuvo el suplente) NO se sumen a su conteo
    tutors = data_default["tutors_metrics"]
    assert len(tutors) >= 3
    for t in tutors:
        # Los turnos efectivos SOLO incluyen los efectivamente asistidos (titular + suplente)
        assert t["total_effective_shifts"] == t["effective_as_primary"] + t["effective_as_substitute"]
        # Los turnos no asistidos cubiertos por suplente NO están en total_effective_shifts
        assert t["scheduled_shifts_as_primary"] == t["effective_as_primary"] + t["unattended_substituted_shifts"]
        assert t["effective_hours"] == t["total_effective_shifts"] * 4
        assert 0.0 <= t["percentage_of_total"] <= 100.0

    # 2. Filtro Total Anual
    res_annual = client.get("/api/v1/clinical/management/metrics/effective-shifts?is_annual=true", headers=headers)
    assert res_annual.status_code == 200
    data_annual = res_annual.json()["data"]
    assert data_annual["filter_applied"]["is_annual"] is True
    assert "monthly_summary" in data_annual
    assert len(data_annual["monthly_summary"]) == 12

    # 3. Filtro por Especialidad: Acupuntura
    res_acu = client.get("/api/v1/clinical/management/metrics/effective-shifts?service_type=ACUPUNTURA", headers=headers)
    assert res_acu.status_code == 200
    data_acu = res_acu.json()["data"]
    assert data_acu["filter_applied"]["service_type"] == "ACUPUNTURA"
    for t in data_acu["tutors_metrics"]:
        assert t["tuina_shifts"] == 0  # En filtro Acupuntura, no hay turnos de Tui na

    # 4. Filtro por Especialidad: Tui na
    res_tui = client.get("/api/v1/clinical/management/metrics/effective-shifts?service_type=TUI_NA", headers=headers)
    assert res_tui.status_code == 200
    data_tui = res_tui.json()["data"]
    assert data_tui["filter_applied"]["service_type"] == "TUI_NA"
    for t in data_tui["tutors_metrics"]:
        assert t["acupuntura_shifts"] == 0

    # 5. Filtro por Sede (Viña del Mar)
    res_vina = client.get("/api/v1/clinical/management/metrics/effective-shifts?campus_id=SEDE-VINA", headers=headers)
    assert res_vina.status_code == 200
    data_vina = res_vina.json()["data"]
    assert "Viña" in data_vina["filter_applied"]["campus_name"] or "VINA" in (data_vina["filter_applied"]["campus_id"] or "")
    for t in data_vina["tutors_metrics"]:
        assert t["santiago_shifts"] == 0


def test_clinical_session_packs_creation_tracking_and_last_session_renewal(client: TestClient, db_session: Session):
    """
    Verifica la creación de packs de 1 a X sesiones en Dirección Clínica,
    el seguimiento y descuento de saldo por paciente, y la alerta de última sesión con renovación.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Crear nuevo pack de 6 sesiones de Acupuntura y Moxibustión en Dirección Clínica
    create_pack_payload = {
        "name": "Pack 6 Sesiones Acupuntura & Moxibustión",
        "code": "PACK-ACU-MOX-06",
        "category": "PACK",
        "service_type": "ACUPUNTURA",
        "session_count": 6,
        "duration_minutes": 60,
        "price_clp": 170000,
        "description": "Pack de 6 sesiones integradas de Acupuntura y Moxibustión para síndromes crónicos.",
        "is_active": True,
    }
    res_create_pack = client.post("/api/v1/clinical/management/session-prices", json=create_pack_payload, headers=headers)
    assert res_create_pack.status_code == 200
    created_pack = res_create_pack.json()["data"]
    assert created_pack["code"] == "PACK-ACU-MOX-06"
    assert created_pack["session_count"] == 6
    assert created_pack["is_pack"] is True
    assert created_pack["price_clp"] == 170000.0

    # 2. Consultar listado de aranceles y verificar presencia de sesiones individuales y packs
    res_prices = client.get("/api/v1/clinical/management/session-prices", headers=headers)
    assert res_prices.status_code == 200
    all_prices = res_prices.json()["data"]
    assert any(p["code"] == "PACK-ACU-MOX-06" for p in all_prices)
    assert any(p["is_pack"] for p in all_prices)
    assert any(not p["is_pack"] for p in all_prices)

    # 3. Consultar saldo de sesiones del paciente (Rodrigo Silva 17.123.456-5)
    res_patient_packs = client.get("/api/v1/clinical/management/patients/17.123.456-5/packs", headers=headers)
    assert res_patient_packs.status_code == 200
    patient_data = res_patient_packs.json()["data"]
    assert patient_data["patient_found"] is True
    assert patient_data["has_active_pack"] is True

    active_pack = patient_data["active_pack"]
    assert active_pack is not None
    assert active_pack["total_sessions"] >= 1
    # Inicialmente tiene 1 sesión restante (demostración de última sesión)
    assert active_pack["remaining_sessions"] == 1
    assert active_pack["is_last_session"] is True
    # El catálogo incluye opciones para renovar
    assert len(patient_data["catalog_prices"]) >= 3

    # 4. Descontar la última sesión del pack (simulando atención del paciente)
    discount_payload = {
        "sessions_to_discount": 1,
        "notes": "Atención de sesión final realizada con Dra. Marcela Pérez",
    }
    res_discount = client.post(
        f"/api/v1/clinical/management/patients/17.123.456-5/packs/{active_pack['id']}/discount",
        json=discount_payload,
        headers=headers,
    )
    assert res_discount.status_code == 200
    disc_data = res_discount.json()["data"]
    assert disc_data["remaining_sessions"] == 0
    assert disc_data["status"] == "EXHAUSTED"
    assert disc_data["is_exhausted"] is True

    # 5. Ofrecer y renovar un nuevo pack para el paciente (seleccionando el nuevo pack de 6 sesiones)
    renew_payload = {
        "session_price_id": created_pack["id"],
        "notes": "Renovación acordada con el paciente para continuar ciclo de tratamiento.",
    }
    res_renew = client.post(
        f"/api/v1/clinical/management/patients/17.123.456-5/packs/{active_pack['id']}/renew",
        json=renew_payload,
        headers=headers,
    )
    assert res_renew.status_code == 200
    renew_data = res_renew.json()["data"]
    assert renew_data["total_sessions"] == 6
    assert renew_data["remaining_sessions"] == 6
    assert renew_data["status"] == "ACTIVE"

    # 6. Verificar el saldo renovado del paciente
    res_updated_packs = client.get("/api/v1/clinical/management/patients/17.123.456-5/packs", headers=headers)
    assert res_updated_packs.status_code == 200
    updated_data = res_updated_packs.json()["data"]
    assert updated_data["has_active_pack"] is True
    assert updated_data["active_pack"]["remaining_sessions"] == 6
    assert updated_data["active_pack"]["is_last_session"] is False
    # El pack previo agotado se encuentra en el historial
    assert len(updated_data["history_packs"]) >= 1
    assert updated_data["history_packs"][0]["status"] == "EXHAUSTED"


def test_supplies_restock_with_quantity_and_date_and_low_stock_filter(client: TestClient, db_session: Session):
    """
    Verifica:
    1. Consulta de stock con umbrales específicos de bajo stock (agujas <= 2000, sabanillas <= 5,
       moxa <= 10, guantes <= 100, semillas <= 100, imanes <= 100, lancetas <= 50, chinchetas <= 100).
    2. Filtro de bajo stock (low_stock_only=True).
    3. Reposición de stock de insumos ingresando cantidad y fecha de ingreso obligatorias.
    4. Auditoría histórica de reposición en bodega.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Obtener listado completo de stock de insumos
    res_all = client.get("/api/v1/clinical/management/supplies/stock", headers=headers)
    assert res_all.status_code == 200
    all_supplies = res_all.json()["data"]
    assert len(all_supplies) == 27

    # Verificar que los umbrales específicos solicitados por el usuario se asignen correctamente
    supplies_by_name = {s["name"]: s for s in all_supplies}

    # aujas menor o igual a 2000
    assert supplies_by_name["Agujas 25 x 25"]["low_stock_threshold"] == 2000
    assert supplies_by_name["Agujas 25 x 40"]["low_stock_threshold"] == 2000
    assert supplies_by_name["Agujas hipodérmicas"]["low_stock_threshold"] == 2000

    # sabanillas menor o igual a 5 unidades
    assert supplies_by_name["Sabanilla"]["low_stock_threshold"] == 5

    # moxa menor o igual a 10 unidades
    assert supplies_by_name["Moxa c/humo"]["low_stock_threshold"] == 10
    assert supplies_by_name["Moxa s/humo"]["low_stock_threshold"] == 10

    # guantes menor o igual a 100 unidades
    assert supplies_by_name["Guantes"]["low_stock_threshold"] == 100

    # semillas menor o igual a 100 unidades
    assert supplies_by_name["Semillas"]["low_stock_threshold"] == 100

    # imanes menor o igual a 100 unidades
    assert supplies_by_name["Imanes"]["low_stock_threshold"] == 100

    # Lancetas menor o igual a 50 unidades
    assert supplies_by_name["Lancetas"]["low_stock_threshold"] == 50

    # chinchetas menor o igual a 100 unidades
    assert supplies_by_name["Chinchetas"]["low_stock_threshold"] == 100

    # 2. Filtrar exclusivamente insumos con bajo stock
    res_low = client.get("/api/v1/clinical/management/supplies/stock?low_stock_only=true", headers=headers)
    assert res_low.status_code == 200
    low_supplies = res_low.json()["data"]
    assert len(low_supplies) > 0
    # Todos los retornados deben tener is_low_stock == True
    for item in low_supplies:
        assert item["is_low_stock"] is True
        assert item["current_stock"] <= item["low_stock_threshold"]

    # 3. Registrar reposición de stock con cantidad y fecha de ingreso
    # Tomamos Agujas 25 x 25 que tiene stock bajo (<= 2000)
    target_supply = supplies_by_name["Agujas 25 x 25"]
    prev_stock = target_supply["current_stock"]
    supply_id = target_supply["id"]

    restock_payload = {
        "quantity": 1000,
        "restock_date": "2026-10-31",
        "invoice_or_batch_number": "FAC-SANBAO-2026-0089",
        "notes": "Ingreso regular de agujas corporales de acupuntura para abastecimiento mensual",
    }
    res_restock = client.post(
        f"/api/v1/clinical/management/supplies/{supply_id}/restock",
        json=restock_payload,
        headers=headers,
    )
    assert res_restock.status_code == 200
    restock_res_data = res_restock.json()["data"]
    assert restock_res_data["quantity_added"] == 1000
    assert restock_res_data["current_stock"] == prev_stock + 1000
    assert restock_res_data["last_restock_date"] == "2026-10-31"
    assert restock_res_data["last_restock_quantity"] == 1000

    # 4. Consultar historial de reposición del insumo
    res_history = client.get(f"/api/v1/clinical/management/supplies/{supply_id}/restocks", headers=headers)
    assert res_history.status_code == 200
    history_data = res_history.json()["data"]
    assert history_data["restocks_count"] >= 1
    latest_record = history_data["history"][0]
    assert latest_record["quantity"] == 1000
    assert latest_record["restock_date"] == "2026-10-31"
    assert latest_record["invoice_or_batch_number"] == "FAC-SANBAO-2026-0089"


def test_supplies_stock_add_and_withdraw_movements_and_insufficient_stock_error(client: TestClient, db_session: Session):
    """
    Verifica los movimientos de stock dentro de Dirección Clínica:
    1. Sacar insumos del stock (- unidades por merma, retiro o uso asistencial).
    2. Validar rechazo 400 cuando se intenta sacar más unidades que el stock disponible.
    3. Agregar insumos al stock (+ unidades por ingreso o ajuste).
    4. Comprobar actualización en tiempo real de stock y alertas.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Obtener insumo objetivo (Agujas 25 x 40)
    res_stock = client.get("/api/v1/clinical/management/supplies/stock", headers=headers)
    assert res_stock.status_code == 200
    supplies = {s["name"]: s for s in res_stock.json()["data"]}
    target = supplies["Agujas 25 x 40"]
    initial_stock = target["current_stock"]
    supply_id = target["id"]

    # 2. Sacar 500 unidades por concepto de merma o retiro asistencial
    withdraw_payload = {
        "movement_type": "SACAR",
        "quantity": 500,
        "movement_date": "2026-10-31",
        "reason": "MERMA",
        "notes": "Retiro por control de calidad de lote y acondicionamiento",
    }
    res_withdraw = client.post(
        f"/api/v1/clinical/management/supplies/{supply_id}/movement",
        json=withdraw_payload,
        headers=headers,
    )
    assert res_withdraw.status_code == 200
    withdraw_data = res_withdraw.json()["data"]
    assert withdraw_data["movement_type"] == "EGRESO"
    assert withdraw_data["previous_stock"] == initial_stock
    assert withdraw_data["current_stock"] == initial_stock - 500

    # 3. Validar error 400 si se intenta sacar más unidades del stock disponible
    excessive_withdraw = {
        "movement_type": "SACAR",
        "quantity": withdraw_data["current_stock"] + 1000,
        "movement_date": "2026-10-31",
        "reason": "MERMA",
    }
    res_excess = client.post(
        f"/api/v1/clinical/management/supplies/{supply_id}/movement",
        json=excessive_withdraw,
        headers=headers,
    )
    assert res_excess.status_code == 400
    assert "Stock insuficiente" in res_excess.json()["detail"]

    # 4. Agregar 300 unidades de insumos (+ stock)
    add_payload = {
        "movement_type": "AGREGAR",
        "quantity": 300,
        "movement_date": "2026-10-31",
        "reason": "AJUSTE_POSITIVO",
        "notes": "Ingreso por ajuste físico de inventario",
    }
    res_add = client.post(
        f"/api/v1/clinical/management/supplies/{supply_id}/movement",
        json=add_payload,
        headers=headers,
    )
    assert res_add.status_code == 200
    add_data = res_add.json()["data"]
    assert add_data["movement_type"] == "INGRESO"
    assert add_data["current_stock"] == initial_stock - 500 + 300


def test_supplies_catalog_create_and_delete(client: TestClient, db_session: Session):
    """
    Verifica la incorporación y eliminación de insumos en el catálogo institucional:
    1. Agregar un nuevo insumo clínico (ej: Agujas 40 x 50 Acero Quirúrgico).
    2. Comprobar que aparece en el listado consolidado.
    3. Sacar / dar de baja el insumo con DELETE.
    4. Comprobar que ya no aparece activo en el listado.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Agregar nuevo insumo clínico al catálogo
    create_payload = {
        "name": "Agujas 40 x 50 Acero Quirúrgico",
        "category": "AGUJAS",
        "unit": "UNIDAD",
        "initial_stock": 2500,
        "notes": "Nuevo calibre para punción profunda en traumatología",
    }
    res_create = client.post("/api/v1/clinical/management/supplies", json=create_payload, headers=headers)
    assert res_create.status_code == 200
    created_item = res_create.json()["data"]
    assert created_item["name"] == "Agujas 40 x 50 Acero Quirúrgico"
    assert created_item["category"] == "AGUJAS"
    assert created_item["current_stock"] == 2500
    # Umbral automático de agujas <= 2000
    assert created_item["low_stock_threshold"] == 2000
    assert created_item["is_low_stock"] is False
    new_id = created_item["id"]

    # 2. Verificar que aparezca en el listado de stock
    res_list = client.get("/api/v1/clinical/management/supplies/stock", headers=headers)
    assert res_list.status_code == 200
    names = [s["name"] for s in res_list.json()["data"]]
    assert "Agujas 40 x 50 Acero Quirúrgico" in names

    # 3. Sacar / eliminar el insumo del catálogo
    res_delete = client.delete(f"/api/v1/clinical/management/supplies/{new_id}", headers=headers)
    assert res_delete.status_code == 200
    assert res_delete.json()["data"]["deleted"] is True

    # 4. Verificar que ya no aparezca en el listado de stock activo
    res_list_after = client.get("/api/v1/clinical/management/supplies/stock", headers=headers)
    assert res_list_after.status_code == 200
    names_after = [s["name"] for s in res_list_after.json()["data"]]
    assert "Agujas 40 x 50 Acero Quirúrgico" not in names_after


def test_weekly_booking_shift_hours_and_overbooking_approval_flow(client: TestClient, db_session: Session):
    """
    Verifica:
    1. Horarios exactos por turno para Acupuntura (AM, PM, Vespertino) y Tui na (AM, PM).
    2. Solicitud de sobrecupo manual en Acupuntura y Tui na y su autorización en Dirección Clínica.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Consultar sobrecupos y catálogo oficial de horas por turno
    res_ovb = client.get("/api/v1/clinical/management/overbookings", headers=headers)
    assert res_ovb.status_code == 200
    payload = res_ovb.json()["data"]
    shift_hours = payload["official_shift_hours"]

    assert shift_hours["ACUPUNTURA"]["AM"] == [
        "10:00", "10:15", "10:30", "10:45", "11:00", "11:15", "11:30", "11:45", "12:00", "12:20", "12:40", "13:00"
    ]
    assert shift_hours["ACUPUNTURA"]["PM"] == [
        "15:00", "15:15", "15:30", "15:45", "16:00", "16:15", "16:30", "16:45", "17:00", "17:20", "17:40"
    ]
    assert shift_hours["ACUPUNTURA"]["VESPERTINO"] == [
        "18:00", "18:15", "18:30", "18:45", "19:00", "19:15", "19:30", "19:45", "20:00", "20:20", "20:40"
    ]
    assert shift_hours["TUI_NA"]["AM"] == ["10:15", "10:45", "11:15", "11:45", "12:15", "12:45"]
    assert shift_hours["TUI_NA"]["PM"] == ["15:15", "15:45", "16:15", "16:45", "17:15", "17:45"]

    # 2. Crear sobrecupo manual para Tui na Turno PM
    create_ovb = {
        "campus_id": "santiago",
        "service_type": "TUI_NA",
        "shift_period": "PM",
        "shift_code": "TUR-TUI-STGO-PM",
        "tutor_name": "Dra. Marcela Pérez Morales",
        "box_name": "Sala Tui na & Masajes (Box Prácticas)",
        "patient_rut": "16.543.210-8",
        "patient_name": "Marcela Rivas P.",
        "patient_phone": "+56 9 9123 4567",
        "appointment_date": "2026-11-05",
        "requested_time": "16:15",
        "reason": "Contractura cervical aguda — solicita sobrecupo manual en turno PM de Tui na",
        "requested_by": "Secretaría Clínica",
    }
    res_post = client.post("/api/v1/clinical/management/overbookings", json=create_ovb, headers=headers)
    assert res_post.status_code == 201
    created = res_post.json()["data"]
    assert created["status"] == "PENDING"
    assert created["service_type"] == "TUI_NA"
    assert created["requested_time"] == "16:15"
    ovb_id = created["id"]

    # 3. Autorizar el sobrecupo desde Dirección Clínica
    res_decide = client.post(
        f"/api/v1/clinical/management/overbookings/{ovb_id}/decide",
        json={
            "decision": "APPROVE",
            "authorized_by": "Dr. Roberto Valenzuela (Director Clínico)",
            "decision_notes": "Autorizado en box de Tui na.",
        },
        headers=headers,
    )
    assert res_decide.status_code == 200
    decided = res_decide.json()["data"]
    assert decided["status"] == "APPROVED"
    assert "Roberto Valenzuela" in decided["authorized_by"]


def test_shift_closure_by_scope_and_affected_patients_reschedule_flow(client: TestClient, db_session: Session):
    """
    Verifica:
    1. Cierre de turnos por jornada en Dirección Clínica: por día (DAY), por semana (WEEK),
       por mes (MONTH) o indefinidamente (INDEFINITE).
    2. Cuando el turno cerrado tiene horas agendadas, genera y envía la nómina de pacientes afectados
       con propuesta de nueva hora al panel de Gestión Clínica.
    3. Desde el listado de Gestión Clínica se puede enviar la propuesta por WhatsApp directo
       (SEND_WHATSAPP), gestionar vía llamada telefónica (LOG_PHONE_CALL) y confirmar el reagendamiento (CONFIRM_RESCHEDULE).
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Cerrar un turno por Semana (WEEK) y verificar que envía la nómina de pacientes afectados a Gestión Clínica
    res_shifts = client.get("/api/v1/clinical/management/shifts", headers=headers)
    assert res_shifts.status_code == 200
    target_shift = res_shifts.json()["data"][0]

    close_week_payload = {
        "closure_type": "WEEK",
        "closure_scope": "WEEK",
        "closure_start_date": "2026-11-02",
        "closure_end_date": "2026-11-07",
        "closure_reason": "Jornada Académica / Capacitación Docente MTC",
        "notes": "Cierre semanal con envío de nómina a Gestión Clínica",
    }
    res_close = client.put(
        f"/api/v1/clinical/management/shifts/{target_shift['id']}/close",
        json=close_week_payload,
        headers=headers,
    )
    assert res_close.status_code == 200
    close_data = res_close.json()["data"]
    assert close_data["status"] == "CLOSED"
    assert close_data["closure_scope"] == "WEEK"
    assert close_data["affected_patients_count"] >= 2
    created_patient = close_data["affected_patients"][0]
    assert created_patient["proposed_date"] == "2026-11-09"  # Lunes siguiente (evita domingo)
    assert "wa.me/" in created_patient["whatsapp_url"]
    assert "tel:+" in created_patient["tel_url"]

    # 2. Probar también cierre por Mes (MONTH) e Indefinido (INDEFINITE)
    res_close_month = client.put(
        f"/api/v1/clinical/management/shifts/{target_shift['id']}/close",
        json={"closure_scope": "MONTH", "closure_start_date": "2026-11-01", "closure_reason": "Mantención Mensual"},
        headers=headers,
    )
    assert res_close_month.status_code == 200
    assert res_close_month.json()["data"]["closure_scope"] == "MONTH"

    res_close_indef = client.put(
        f"/api/v1/clinical/management/shifts/{target_shift['id']}/close",
        json={"closure_scope": "INDEFINITE", "closure_start_date": "2026-11-03", "closure_reason": "Licencia Médica"},
        headers=headers,
    )
    assert res_close_indef.status_code == 200
    assert res_close_indef.json()["data"]["closure_scope"] == "INDEFINITE"

    # 3. Consultar el listado en el panel de Gestión Clínica
    res_list = client.get("/api/v1/clinical/management/shift-closures/affected-patients", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()["data"]
    assert list_data["kpis"]["total_count"] >= 3
    item_id = created_patient["id"]

    # 4. Gestionar envío por WhatsApp directo desde el sitio
    res_wa = client.post(
        f"/api/v1/clinical/management/shift-closures/affected-patients/{item_id}/manage",
        json={
            "action": "SEND_WHATSAPP",
            "proposed_date": "2026-11-10",
            "proposed_time": "10:30",
        },
        headers=headers,
    )
    assert res_wa.status_code == 200
    wa_data = res_wa.json()["data"]
    assert wa_data["status"] == "PROPOSAL_SENT_WHATSAPP"
    assert wa_data["contact_channel"] == "WHATSAPP"
    assert wa_data["proposed_date"] == "2026-11-10"
    assert wa_data["proposed_time"] == "10:30"
    assert "10/11/2026" in wa_data["whatsapp_message"]

    # 5. Gestionar llamada telefónica desde el mismo listado
    second_item_id = close_data["affected_patients"][1]["id"]
    res_call = client.post(
        f"/api/v1/clinical/management/shift-closures/affected-patients/{second_item_id}/manage",
        json={
            "action": "LOG_PHONE_CALL",
            "proposed_date": "2026-11-10",
            "proposed_time": "11:00",
        },
        headers=headers,
    )
    assert res_call.status_code == 200
    assert res_call.json()["data"]["status"] == "CONTACTED_PHONE"
    assert res_call.json()["data"]["contact_channel"] == "PHONE_CALL"

    # 6. Confirmar reagendamiento definitivo
    res_confirm = client.post(
        f"/api/v1/clinical/management/shift-closures/affected-patients/{item_id}/manage",
        json={
            "action": "CONFIRM_RESCHEDULE",
            "proposed_date": "2026-11-10",
            "proposed_time": "10:30",
        },
        headers=headers,
    )
    assert res_confirm.status_code == 200
    assert res_confirm.json()["data"]["status"] == "RESCHEDULED"

    # 7. Verificar que el visualizador semanal de franjas de turnos para cierre en días específicos esté en el frontend
    res_html = client.get("/")
    assert res_html.status_code == 200
    html_text = res_html.text
    assert 'id="cm-shifts-weekly-strips-view"' in html_text
    assert 'id="cm-weekly-strips-grid"' in html_text
    assert 'id="cm-ws-service-filter"' in html_text
    assert 'id="cm-ws-period-filter"' in html_text
    assert 'id="close-shift-month-subscope"' in html_text
    assert 'id="close-shift-indef-subscope"' in html_text
    for strip_code in ("TUR-ACU-AM", "TUR-ACU-PM", "TUR-ACU-VESPERTINO", "TUR-TUI-AM", "TUR-TUI-PM"):
        assert strip_code in html_text
    assert 'onclick="closeClinicalShift(' not in html_text
    assert "renderCmWeeklyShiftStrips" in html_text
    assert "openCloseShiftFromWeeklyStrip" in html_text

    # 8. Verificar que los subpaneles 8 (Solicitud de Pago) y 9 (Solicitudes de Sobrecupo) sean hijos directos de #tab-clinical-management
    from html.parser import HTMLParser

    class SubtabDomChecker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.parents_by_id = {}

        def handle_starttag(self, tag, attrs):
            if tag in ("img", "input", "br", "hr", "meta", "link"):
                return
            d = dict(attrs)
            cid = d.get("id", "")
            cls = d.get("class", "")
            if "cm-subtab-pane" in cls or "clin-mod-subtab-pane" in cls:
                self.parents_by_id[cid] = [x[1] for x in self.stack if x[1]]
            self.stack.append((tag, cid))

        def handle_endtag(self, tag):
            if tag in ("img", "input", "br", "hr", "meta", "link"):
                return
            if self.stack:
                self.stack.pop()

    checker = SubtabDomChecker()
    checker.feed(html_text)
    assert "cm-subtab-secretaries" not in checker.parents_by_id["cm-subtab-payment-requests"]
    assert "cm-subtab-secretaries" not in checker.parents_by_id["cm-subtab-overbookings"]
    assert checker.parents_by_id["cm-subtab-payment-requests"][-1] == "tab-clinical-management"
    assert checker.parents_by_id["cm-subtab-overbookings"][-1] == "tab-clinical-management"

    # 9. Verificar que Gestión Clínica (#tab-clinical) esté organizada en 5 subpaneles independientes y cuente con apertura directa de Agenda al presionar tag "Hoy"
    assert 'id="clinical-module-subtabs-nav"' in html_text
    assert 'id="btn-header-clinical-today-tag"' in html_text
    assert 'id="btn-weekly-booking-today"' in html_text
    assert 'id="today-agenda-quick-slots-grid"' in html_text
    assert "switchClinicalModuleSubtab" in html_text
    assert "openClinicalTodayAgenda" in html_text
    assert "renderTodayAgendaQuickSlots" in html_text
    for clin_pane_id in (
        "clin-subtab-weekly-booking",
        "clin-subtab-today-agenda",
        "clin-subtab-affected-patients",
        "clin-subtab-supply-dispatch",
        "clin-subtab-clinical-record",
    ):
        assert clin_pane_id in checker.parents_by_id
        assert checker.parents_by_id[clin_pane_id][-1] == "tab-clinical"














