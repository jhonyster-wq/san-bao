import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.modules.academic.models.student import Student
from app.modules.academic.models.program import Program


def get_auth_token_and_instituto(client: TestClient):
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    companies = login_res.json()["data"]["available_companies"]
    instituto = next(c for c in companies if "Instituto" in c["legal_name"] or "77123456" in c["rut"])
    clinica = next(c for c in companies if "Clínica" in c["legal_name"] or "76987654" in c["rut"])
    return token, instituto["id"], clinica["id"]


def test_coordinator_list_enrollments(client: TestClient, db_session: Session):
    token, instituto_id, _ = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    res = client.get("/api/v1/academic/coordinator/enrollments", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) >= 3

    # Verificar presencia de Diego Valenzuela
    diego = next((s for s in data if "Diego" in s["full_name"]), None)
    assert diego is not None
    assert "MAT-2026-" in diego["student_number"]
    assert diego["academic_status"] == "REGULAR"
    assert diego["clinical_practice_approved"] is True


def test_coordinator_freeze_and_unfreeze_student(client: TestClient, db_session: Session):
    token, instituto_id, _ = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Obtener lista
    res = client.get("/api/v1/academic/coordinator/enrollments", headers=headers)
    diego = next(s for s in res.json()["data"] if "Diego" in s["full_name"])
    student_id = diego["student_id"]

    # 2. Congelar alumno
    freeze_payload = {
        "reason": "Motivos laborales y de salud temporal",
        "effective_date": "2026-11-01",
        "notes": "Solicitud formal presentada en Coordinación Académica.",
    }
    freeze_res = client.post(
        f"/api/v1/academic/coordinator/students/{student_id}/freeze",
        headers=headers,
        json=freeze_payload,
    )
    assert freeze_res.status_code == 200
    assert freeze_res.json()["data"]["status"] == "CONGELADO"
    assert freeze_res.json()["data"]["freeze_reason"] == freeze_payload["reason"]

    # 3. Reactivar alumno
    unfreeze_payload = {
        "effective_date": "2026-11-15",
        "notes": "Reincorporación formal y regularización académica.",
    }
    unfreeze_res = client.post(
        f"/api/v1/academic/coordinator/students/{student_id}/unfreeze",
        headers=headers,
        json=unfreeze_payload,
    )
    assert unfreeze_res.status_code == 200
    assert unfreeze_res.json()["data"]["status"] == "REGULAR"


def test_coordinator_transfer_student_course(client: TestClient, db_session: Session):
    token, instituto_id, _ = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # Obtener alumno y programas
    res = client.get("/api/v1/academic/coordinator/enrollments", headers=headers)
    camila = next(s for s in res.json()["data"] if "Camila" in s["full_name"])
    student_id = camila["student_id"]

    # Buscar programa destino (CUR-TUI-01)
    programs_res = client.get("/api/v1/academic/programs", headers=headers)
    target_program = next(p for p in programs_res.json()["data"] if "TUI" in p["code"])
    dest_program_id = target_program["id"]

    transfer_payload = {
        "to_program_id": dest_program_id,
        "reason": "Cambio de especialización hacia Masaje Tuina y Ventosas",
        "effective_date": "2026-11-02",
        "notes": "Convalidación de asignaturas teóricas aprobadas.",
    }
    trans_res = client.post(
        f"/api/v1/academic/coordinator/students/{student_id}/change-course",
        headers=headers,
        json=transfer_payload,
    )
    assert trans_res.status_code == 200
    assert trans_res.json()["data"]["to_program_name"] == target_program["name"]

    # Verificar historial de transferencias
    hist_res = client.get("/api/v1/academic/coordinator/transfers", headers=headers)
    assert hist_res.status_code == 200
    assert len(hist_res.json()["data"]) >= 1


def test_coordinator_approve_clinical_and_assign_in_clinical_management(client: TestClient, db_session: Session):
    token, instituto_id, clinica_id = get_auth_token_and_instituto(client)
    headers_inst = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}
    headers_clin = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # 1. Aprobar a Camila para prácticas clínicas
    enr_res = client.get("/api/v1/academic/coordinator/enrollments", headers=headers_inst)
    camila = next(s for s in enr_res.json()["data"] if "Camila" in s["full_name"])
    student_id = camila["student_id"]

    approve_payload = {
        "approved": True,
        "approval_date": "2026-11-01",
        "notes": "Habilitada por Coordinación Académica tras certificar asistencia teórica completa.",
    }
    appr_res = client.post(
        f"/api/v1/academic/coordinator/students/{student_id}/approve-clinical",
        headers=headers_inst,
        json=approve_payload,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["data"]["clinical_practice_approved"] is True

    # 2. Verificar que Dirección Clínica visualiza a Camila en la lista de practicantes habilitados
    interns_res = client.get("/api/v1/clinical/management/interns", headers=headers_clin)
    assert interns_res.status_code == 200
    interns = interns_res.json()["data"]
    camila_intern = next((i for i in interns if i["student_id"] == student_id), None)
    assert camila_intern is not None
    assert "Camila" in camila_intern["full_name"]

    # 3. Asignar a Camila a un turno en Dirección Clínica
    shifts_res = client.get("/api/v1/clinical/management/shifts", headers=headers_clin)
    assert shifts_res.status_code == 200
    shifts = shifts_res.json()["data"]
    assert len(shifts) > 0
    target_shift = shifts[0]
    shift_id = target_shift["id"]

    assign_res = client.put(
        f"/api/v1/clinical/management/shifts/{shift_id}/assign-intern",
        headers=headers_clin,
        json={"student_id": student_id, "notes": "Asignada a box Tai Yang con tutor docente."},
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["data"]["intern_student_id"] == student_id
    assert "Camila" in assign_res.json()["data"]["intern_student_name"]

    # 4. Desvincular del turno
    unassign_res = client.delete(
        f"/api/v1/clinical/management/shifts/{shift_id}/unassign-intern",
        headers=headers_clin,
    )
    assert unassign_res.status_code == 200
    assert unassign_res.json()["data"]["intern_student_id"] is None


def test_coordinator_grading_and_evaluation_entry(client: TestClient, db_session: Session):
    token, instituto_id, _ = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Listar cohortes para entrega de notas
    cohorts_res = client.get("/api/v1/academic/coordinator/grading/cohorts", headers=headers)
    assert cohorts_res.status_code == 200
    cohorts = cohorts_res.json()["data"]
    assert len(cohorts) > 0
    target_cohort = cohorts[0]
    cohort_id = target_cohort["cohort_id"]

    # 2. Consultar notas de la cohorte
    grades_res = client.get(f"/api/v1/academic/coordinator/grading/cohorts/{cohort_id}", headers=headers)
    assert grades_res.status_code == 200
    grade_data = grades_res.json()["data"]
    assert len(grade_data["students"]) > 0
    student = grade_data["students"][0]
    student_id = student["student_id"]

    # 3. Ingresar nueva nota de evaluación
    entry_payload = {
        "cohort_id": cohort_id,
        "student_id": student_id,
        "evaluation_name": "Control Clínico MTC #2",
        "score": 6.7,
        "weight_percentage": 25.0,
        "feedback": "Correcta palpación de pulsos de Riñón y Bazo.",
    }
    entry_res = client.post(
        "/api/v1/academic/coordinator/grading/entry",
        headers=headers,
        json=entry_payload,
    )
    assert entry_res.status_code == 200
    assert entry_res.json()["data"]["score"] == 6.7


def test_coordinator_official_documents_issuance(client: TestClient, db_session: Session):
    token, instituto_id, _ = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    enr_res = client.get("/api/v1/academic/coordinator/enrollments", headers=headers)
    students = enr_res.json()["data"]
    diego = next(s for s in students if "Diego" in s["full_name"])
    andrea = next(s for s in students if "Andrea" in s["full_name"])

    # 1. Emitir Certificado de Alumno Regular
    ar_res = client.post(
        "/api/v1/academic/coordinator/documents/issue",
        headers=headers,
        json={
            "student_id": diego["student_id"],
            "document_type": "ALUMNO_REGULAR",
            "notes": "Para trámites de previsión y acreditación de cargas.",
        },
    )
    assert ar_res.status_code == 201
    assert "CERT-AR" in ar_res.json()["data"]["document_number"]

    # 2. Emitir Diploma de Egreso para alumna egresada (Andrea Bustamante)
    dip_res = client.post(
        "/api/v1/academic/coordinator/documents/issue",
        headers=headers,
        json={
            "student_id": andrea["student_id"],
            "document_type": "DIPLOMA_EGRESO",
            "notes": "Graduación de honor por cumplimiento íntegro del plan de estudios.",
        },
    )
    assert dip_res.status_code == 201
    assert "DIP-EGR" in dip_res.json()["data"]["document_number"]
    assert dip_res.json()["data"]["is_compliant"] is True

    # 3. Listar documentos
    docs_res = client.get("/api/v1/academic/coordinator/documents", headers=headers)
    assert docs_res.status_code == 200
    docs = docs_res.json()["data"]
    assert len(docs) >= 2
    types = [d["document_type"] for d in docs]
    assert "ALUMNO_REGULAR" in types
    assert "DIPLOMA_EGRESO" in types


def test_coordinator_matriculas_panel_filters_and_summary(client: TestClient, db_session: Session):
    """
    Verifica el nuevo panel de Matrículas en Gestión Académica & Control Curricular:
    - Listado de matriculados con filtro de sede, estado financiero, diplomados o cursos.
    - Resumen dinámico según filtros aplicados.
    - Presencia de los componentes en el frontend (#coord-subtab-matriculas).
    """
    token, instituto_id, _ = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Reporte general sin filtros
    rep_all = client.get("/api/v1/academic/coordinator/matriculas/report", headers=headers)
    assert rep_all.status_code == 200
    data_all = rep_all.json()["data"]
    summary_all = data_all["summary"]
    items_all = data_all["items"]
    assert summary_all["total_enrolled"] == len(items_all)
    assert summary_all["total_enrolled"] >= 4
    assert summary_all["diplomados_count"] + summary_all["cursos_count"] == summary_all["total_enrolled"]
    assert summary_all["santiago_count"] + summary_all["vina_count"] == summary_all["total_enrolled"]
    assert summary_all["total_contract_clp"] > 0

    # 2. Filtro por Sede (VINA_DEL_MAR)
    rep_vina = client.get(
        "/api/v1/academic/coordinator/matriculas/report?campus=VINA_DEL_MAR",
        headers=headers,
    )
    assert rep_vina.status_code == 200
    data_vina = rep_vina.json()["data"]
    assert data_vina["summary"]["total_enrolled"] >= 1
    assert data_vina["summary"]["santiago_count"] == 0
    assert all(i["campus_code"] == "VINA_DEL_MAR" for i in data_vina["items"])

    # 3. Filtro por Estado Financiero (MOROSO)
    rep_moroso = client.get(
        "/api/v1/academic/coordinator/matriculas/report?financial_status=MOROSO",
        headers=headers,
    )
    assert rep_moroso.status_code == 200
    data_moroso = rep_moroso.json()["data"]
    assert data_moroso["summary"]["moroso_count"] == data_moroso["summary"]["total_enrolled"]
    assert all(i["financial_status"] == "MOROSO" for i in data_moroso["items"])

    # 4. Filtro por Tipo de Programa (DIPLOMADO vs CURSO)
    rep_dip = client.get(
        "/api/v1/academic/coordinator/matriculas/report?program_category=DIPLOMADO",
        headers=headers,
    )
    assert rep_dip.status_code == 200
    data_dip = rep_dip.json()["data"]
    assert data_dip["summary"]["cursos_count"] == 0
    assert all(i["program_type_group"] == "DIPLOMADO" for i in data_dip["items"])

    rep_cur = client.get(
        "/api/v1/academic/coordinator/matriculas/report?program_category=CURSO",
        headers=headers,
    )
    assert rep_cur.status_code == 200
    data_cur = rep_cur.json()["data"]
    assert data_cur["summary"]["diplomados_count"] == 0
    assert all(i["program_type_group"] == "CURSO" for i in data_cur["items"])

    # 5. Verificar que el nuevo panel #coord-subtab-matriculas esté en el DOM como hijo directo de #tab-academic-coordinator
    res_html = client.get("/")
    assert res_html.status_code == 200
    html_text = res_html.text
    assert 'id="coord-subtab-btn-matriculas"' in html_text
    assert 'id="coord-subtab-matriculas"' in html_text
    assert 'id="mat-filter-campus"' in html_text
    assert 'id="mat-filter-financial"' in html_text
    assert 'id="mat-filter-category"' in html_text
    assert 'id="mat-filter-program"' in html_text
    assert 'id="mat-summary-cards-container"' in html_text
    assert 'id="coord-matriculas-table-body"' in html_text
    assert "filterCoordinatorMatriculas" in html_text
    assert "renderCoordinatorMatriculasSummaryAndTable" in html_text

    # 6. Verificar que los 7 paneles de Gestión Académica sean hijos directos de #tab-academic-coordinator y la barra #coord-subtabs-nav tenga flex-wrap
    from html.parser import HTMLParser

    class CoordDomChecker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.parents_by_id = {}
            self.nav_classes = ""

        def handle_starttag(self, tag, attrs):
            if tag in ("img", "input", "br", "hr", "meta", "link"):
                return
            d = dict(attrs)
            cid = d.get("id", "")
            cls = d.get("class", "")
            if cid == "coord-subtabs-nav":
                self.nav_classes = cls
            if "coord-subtab-pane" in cls:
                self.parents_by_id[cid] = [x[1] for x in self.stack if x[1]]
            self.stack.append((tag, cid))

        def handle_endtag(self, tag):
            if tag in ("img", "input", "br", "hr", "meta", "link"):
                return
            if self.stack:
                self.stack.pop()

    checker = CoordDomChecker()
    checker.feed(html_text)
    assert "flex-wrap" in checker.nav_classes
    for pane_id in (
        "coord-subtab-enrollments",
        "coord-subtab-grades",
        "coord-subtab-freeze",
        "coord-subtab-transfers",
        "coord-subtab-clinical",
        "coord-subtab-documents",
        "coord-subtab-matriculas",
        "coord-subtab-admissions",
        "coord-subtab-interviews",
    ):
        assert pane_id in checker.parents_by_id
        assert checker.parents_by_id[pane_id][-1] == "tab-academic-coordinator"

    # 7. Verificar que el Portal del Alumno (#tab-student) esté organizado en 3 paneles independientes sin despliegues largos
    assert 'id="student-subtabs-nav"' in html_text
    assert 'id="student-subtab-courses"' in html_text
    assert 'id="student-subtab-finance"' in html_text
    assert 'id="student-subtab-qr-minsal"' in html_text
    assert "switchStudentPortalSubtab" in html_text
    assert ".student-subtab-pane.hidden" in html_text

    # 8. Verificar que el Portal de Tutores (#tab-tutor-portal) no tenga separación financiera en el encabezado,
    # esté organizado en 3 paneles independientes, muestre los turnos por mes con botón para desplegar y aprobar alumnos por turno,
    # e incorpore filtros de Turno y Fecha en el listado de alumnos asignados por Dirección Clínica
    assert "Separación Financiera &amp; RRHH — Docentes de Aula" not in html_text
    assert 'id="tutor-subtabs-nav"' in html_text
    assert "<span>1. Mis Turnos Asignados</span>" in html_text
    assert "1. Mis Turnos Asignados (Vista Mensual)" not in html_text
    assert 'id="tutor-subtab-shifts"' in html_text
    assert 'id="tutor-shifts-filter-type"' in html_text
    assert 'id="tutor-session-identity-card"' in html_text
    assert "setTutorShiftsTypeFilter" in html_text
    assert "✓ Aprobar Asistencia en Turno" not in html_text
    assert 'id="tutor-calendar-days-grid"' in html_text
    assert 'id="tutor-calendar-shift-students-drawer"' in html_text
    assert "renderTutorMonthlyCalendar" in html_text
    assert 'id="tutor-subtab-students"' in html_text
    assert 'id="tutor-subtab-qr-logs"' in html_text
    assert ".tutor-subtab-pane.hidden" in html_text
    assert 'id="tutor-shifts-month-picker"' in html_text
    assert "toggleTutorShiftStudentsRow" in html_text
    assert "approveTutorShiftStudentAttendance" in html_text
    assert 'id="tutor-students-filter-shift"' in html_text
    assert 'id="tutor-students-filter-date"' in html_text

    res_tutor = client.get("/api/v1/academic/coordinator/tutor-portal/overview?tutor_id=12.876.543-1")
    assert res_tutor.status_code == 200
    tutor_data = res_tutor.json()["data"]
    assert 1 <= len(tutor_data["assigned_shifts"]) <= 3
    shift_periods = [s["shift_period"] for s in tutor_data["assigned_shifts"]]
    assert len(shift_periods) == len(set(shift_periods))
    assert set(shift_periods).issubset({"AM", "PM", "VESPERTINO"})
    first_shift = tutor_data["assigned_shifts"][0]
    assert "(" not in first_shift["shift_name"]
    assert "shift_period_label" in first_shift
    assert "shift_month" in first_shift
    assert "assigned_students_list" in first_shift
    assert len(first_shift["assigned_students_list"]) >= 1
    assert len(tutor_data["assigned_students"]) >= 1
    assert "shift_date" in tutor_data["assigned_students"][0]
    assert "assigned_shift_code" in tutor_data["assigned_students"][0]

    # 9. Verificar "Registro de Horas de Práctica Clínica":
    # - Cambio de nombre en Portal de Alumnos
    # - Habilitado solo si tiene asignación de turno
    # - Obligatoriedad de marcar Entrada y Salida en el mismo día (resta Salida - Entrada) y aviso si falta una marca
    assert "3. Registro de Horas de Práctica Clínica" in html_text
    assert 'id="st-shift-assignment-banner"' in html_text
    assert 'id="btn-st-qr-checkin"' in html_text
    assert 'id="btn-st-qr-checkout"' in html_text

    # Alumno con turno asignado (Diego Valenzuela 19.876.543-0) vs alumno congelado sin turno (Ignacio Morales 17.654.321-9)
    res_st_active = client.get("/api/v1/academic/coordinator/student-portal/profile?student_id_or_rut=19.876.543-0")
    assert res_st_active.status_code == 200
    assert res_st_active.json()["data"]["has_assigned_shift"] is True

    res_st_no_shift = client.get("/api/v1/academic/coordinator/student-portal/profile?student_id_or_rut=17.654.321-9")
    assert res_st_no_shift.status_code == 200
    assert res_st_no_shift.json()["data"]["has_assigned_shift"] is False

    # Intento de marcaje sin turno asignado debe rechazarse
    res_blocked = client.post(
        "/api/v1/academic/coordinator/clinical-qr-attendance",
        json={"student_id_or_rut": "17.654.321-9", "action": "ENTRADA", "activity_date": "2026-11-15"},
    )
    assert res_blocked.status_code == 400

    # Marcaje solo de ENTRADA en el día deja registro incompleto (0 hrs) y aviso de falta de SALIDA
    res_in_only = client.post(
        "/api/v1/academic/coordinator/clinical-qr-attendance",
        json={
            "student_id_or_rut": "19.876.543-0",
            "action": "ENTRADA",
            "activity_date": "2026-11-18",
            "check_in_time": "09:00:00",
        },
    )
    assert res_in_only.status_code == 200
    d_in = res_in_only.json()["data"]
    assert d_in["is_complete"] is False
    assert d_in["missing_mark"] == "SALIDA"
    assert d_in["hours_completed"] == 0
    assert d_in["warning_notice"] is not None

    # Al marcar SALIDA en el mismo día (14:00:00), calcula la resta exacta (14:00 - 09:00 = 5 hrs) y completa el registro
    res_out_same_day = client.post(
        "/api/v1/academic/coordinator/clinical-qr-attendance",
        json={
            "student_id_or_rut": "19.876.543-0",
            "action": "SALIDA",
            "activity_date": "2026-11-18",
            "check_out_time": "14:00:00",
        },
    )
    assert res_out_same_day.status_code == 200
    d_out = res_out_same_day.json()["data"]
    assert d_out["is_complete"] is True
    assert d_out["missing_mark"] is None
    assert d_out["hours_completed"] == 5
    assert "14:00 − 09:00 = 5 hrs" in d_out["hours_formula"]

    # 10. Verificar paneles "8. Fichas de Admisión" (#coord-subtab-admissions) y "9. Listado de Entrevistas" (#coord-subtab-interviews):
    # - Endpoint interno del portal del sitio (POST /api/v1/academic/coordinator/admissions/intake) con Correo, Nombre, Apellidos, Teléfono, Formato (Presencial/Semipresencial) y Sede (Santiago/Viña del Mar)
    # - Cambio de nombre "+ Agregar Ficha de Admisión" y "📅 Programar Entrevista"
    # - Sin botones de Aceptar ni Matricular en Fichas de Admisión
    # - Al confirmar la fecha en Programar Entrevista: envía correo con la cita, sale del listado de Fichas de Admisión y se agrega al Listado de Entrevistas
    assert 'id="coord-subtab-btn-admissions"' in html_text
    assert 'id="coord-subtab-btn-interviews"' in html_text
    assert 'id="coord-subtab-admissions"' in html_text
    assert 'id="coord-subtab-interviews"' in html_text
    assert 'id="coord-manual-ficha-panel"' in html_text
    assert "+ Agregar Ficha de Admisión" in html_text
    assert "Agregar Ficha Técnica Manual (Presencial Clínica)" not in html_text
    assert "📅 Programar Entrevista" in html_text
    assert "Reprogramar Entrevista" not in html_text
    assert 'id="coord-sched-email-preview"' in html_text
    assert "submitManualAdmissionFicha" in html_text
    assert "simulatePortalWebAdmissionIntake" in html_text
    assert "openScheduleAdmissionInterviewBox" in html_text
    assert "evaluateAdmissionInterviewDecision" in html_text
    assert "initiateEnrollmentFromAdmission" in html_text

    # Recepción desde endpoint interno del portal web (alias en español)
    res_portal_intake = client.post(
        "/api/v1/academic/coordinator/admissions/intake",
        json={
            "correo": "francisca.portal@sanbao.cl",
            "nombre": "Francisca",
            "apellidos": "Araya Soto",
            "telefono": "+56 9 8111 2233",
            "formato_estudio": "Semipresencial",
            "sede": "Viña del Mar",
        },
    )
    assert res_portal_intake.status_code in (200, 201)
    ficha_portal = res_portal_intake.json()["data"]
    assert ficha_portal["email"] == "francisca.portal@sanbao.cl"
    assert ficha_portal["first_name"] == "Francisca"
    assert ficha_portal["last_name"] == "Araya Soto"
    assert ficha_portal["study_format"] == "SEMIPRESENCIAL"
    assert ficha_portal["study_format_label"] == "Semipresencial"
    assert ficha_portal["campus"] == "VINA_DEL_MAR"
    assert ficha_portal["campus_label"] == "Viña del Mar"
    assert ficha_portal["source"] == "PORTAL_WEB"
    assert "https://wa.me/56981112233" in ficha_portal["whatsapp_url"]

    # Antes de programar entrevista, la ficha aparece en el listado de Fichas de Admisión
    ficha_id = ficha_portal["id"]
    res_adm_before = client.get("/api/v1/academic/coordinator/admissions")
    assert res_adm_before.status_code == 200
    assert any(item["id"] == ficha_id for item in res_adm_before.json()["data"]["items"])

    # Ingreso de Ficha de Admisión Manual (caso presencial en clínica)
    res_manual_ficha = client.post(
        "/api/v1/academic/coordinator/admissions",
        json={
            "email": "gonzalo.clinica@sanbao.cl",
            "first_name": "Gonzalo",
            "last_name": "Vargas Pinto",
            "phone": "+56 9 7444 5566",
            "study_format": "Presencial",
            "campus": "Santiago",
            "source": "PRESENCIAL_CLINICA",
            "rut": "16.543.210-8",
            "interviewer_notes": "Atendido presencialmente en recepción clínica Providencia. Interés en cohorte marzo.",
        },
    )
    assert res_manual_ficha.status_code in (200, 201)
    ficha_manual = res_manual_ficha.json()["data"]
    assert ficha_manual["source"] == "PRESENCIAL_CLINICA"
    assert ficha_manual["campus"] == "SANTIAGO"
    assert ficha_manual["study_format"] == "PRESENCIAL"

    # Programar entrevista para la ficha recibida del portal:
    # Debe enviar correo con la cita, salir del listado de Fichas de Admisión y agregarse al Listado de Entrevistas
    res_sched = client.put(
        f"/api/v1/academic/coordinator/admissions/{ficha_id}/schedule-interview",
        json={
            "interview_date": "2026-11-20",
            "interview_time": "11:30",
            "interviewer_name": "Dra. Claudia Morales (Dir. Académica)",
            "interview_modality": "ONLINE_ZOOM",
            "interviewer_notes": "Coordinada vía WhatsApp para revisión de requisitos.",
        },
    )
    assert res_sched.status_code == 200
    sched_data = res_sched.json()["data"]
    assert sched_data["status"] == "ENTREVISTA_AGENDADA"
    assert sched_data["interview_date"] == "2026-11-20"
    assert sched_data["interview_time"] == "11:30"
    assert sched_data["email_sent"] is True
    assert sched_data["moved_to_interviews_list"] is True
    assert sched_data["email_notification"]["recipient"] == "francisca.portal@sanbao.cl"
    assert "2026-11-20" in sched_data["email_notification"]["subject"]

    # Verificar que ya salió del listado de Fichas de Admisión
    res_adm_after = client.get("/api/v1/academic/coordinator/admissions")
    assert res_adm_after.status_code == 200
    assert not any(item["id"] == ficha_id for item in res_adm_after.json()["data"]["items"])

    # Verificar que se agregó al Listado de Entrevistas filtrando por fecha de trabajo diario
    # y que ANTES de aceptar la entrevista, la matrícula aún no está habilitada (can_enroll == False)
    res_int_list = client.get("/api/v1/academic/coordinator/interviews?interview_date=2026-11-20")
    assert res_int_list.status_code == 200
    int_payload = res_int_list.json()["data"]
    scheduled_interview_item = next((item for item in int_payload["interviews"] if item["id"] == ficha_id), None)
    assert scheduled_interview_item is not None
    assert scheduled_interview_item["can_enroll"] is False

    # Evaluar entrevista en el Listado de Entrevistas:
    # Aceptar la entrevista y agregar una descripción opcional para su Hoja de Vida -> habilita la matrícula
    life_record_desc = "Postulante con formación previa en enfermería y alta motivación clínica para Acupuntura."
    res_eval = client.put(
        f"/api/v1/academic/coordinator/admissions/{ficha_id}/evaluate-interview",
        json={
            "decision": "ACEPTADO",
            "life_record_notes": life_record_desc,
        },
    )
    assert res_eval.status_code == 200
    eval_data = res_eval.json()["data"]
    assert eval_data["status"] == "ACEPTADO"
    assert eval_data["evaluation_decision"] == "ACEPTADO"
    assert eval_data["can_enroll"] is True
    assert eval_data["life_record_notes"] == life_record_desc

    # Iniciar matrícula y enviar correo de matrícula:
    # Debe desaparecer del Listado de Entrevistas, agregarse a la Nómina de Matriculados y guardar la descripción en su Hoja de Vida
    cat_res = client.get("/api/v1/academic/programs", headers=headers)
    assert cat_res.status_code == 200
    first_prog_id = cat_res.json()["data"][0]["id"]

    res_init_mat = client.post(
        "/api/v1/academic/coordinator/onboarding/initiate",
        headers=headers,
        json={
            "rut": "19.876.543-2",
            "first_name": "Francisca",
            "last_name": "Araya Soto",
            "email": "francisca.portal@sanbao.cl",
            "phone": "+56 9 8111 2233",
            "program_id": first_prog_id,
            "campus": "VINA_DEL_MAR",
            "enrollment_fee": 150000,
            "tuition_amount": 2600000,
            "installments_count": 10,
            "first_due_date": "2026-04-05",
            "admission_application_id": ficha_id,
            "life_record_notes": life_record_desc,
        },
    )
    assert res_init_mat.status_code in (200, 201)
    mat_data = res_init_mat.json()["data"]
    assert mat_data["status"] in ("CONTRACT_SENT", "CONTRATO_ENVIADO_CORREO")
    assert mat_data["removed_from_interviews_list"] is True
    assert mat_data["life_record_notes"] == life_record_desc
    enrolled_student_id = mat_data["student_id"]

    # Verificar que al enviar el correo de matrícula desapareció del Listado de Entrevistas
    res_int_after_mat = client.get("/api/v1/academic/coordinator/interviews", headers=headers)
    assert res_int_after_mat.status_code == 200
    assert not any(item["id"] == ficha_id for item in res_int_after_mat.json()["data"]["interviews"])

    # Verificar que fue agregada al panel de Nómina de Matriculados (enrollments y matriculas/report)
    res_enrollments = client.get("/api/v1/academic/coordinator/enrollments", headers=headers)
    assert res_enrollments.status_code == 200
    enrolled_row = next((s for s in res_enrollments.json()["data"] if s["student_id"] == enrolled_student_id), None)
    assert enrolled_row is not None
    assert enrolled_row["email"] == "francisca.portal@sanbao.cl"
    assert life_record_desc in (enrolled_row["life_record_summary"]["latest_observation"] or "")

    res_matriculas_nomina = client.get("/api/v1/academic/coordinator/matriculas/report", headers=headers)
    assert res_matriculas_nomina.status_code == 200
    assert any(s["student_id"] == enrolled_student_id for s in res_matriculas_nomina.json()["data"]["items"])

    # Verificar que la descripción quedó registrada en la Hoja de Vida del alumno
    res_life_record = client.get(f"/api/v1/academic/coordinator/students/{enrolled_student_id}/life-record", headers=headers)
    assert res_life_record.status_code == 200
    lr_entries = res_life_record.json()["data"]["life_record_entries"]
    assert any(life_record_desc in entry["description"] for entry in lr_entries)








