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
    ):
        assert pane_id in checker.parents_by_id
        assert checker.parents_by_id[pane_id][-1] == "tab-academic-coordinator"



