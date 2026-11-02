from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.modules.academic.models.program import Program, Course
from app.modules.institutional.models.person import Person


def get_auth_token_and_instituto(client: TestClient):
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "director_academico", "password": "DirectorAcademico2026!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]
    companies = login_res.json()["data"]["available_companies"]
    instituto = next(c for c in companies if "Instituto" in c["legal_name"] or "77123456" in c["rut"])
    return token, instituto["id"]


def test_academic_director_login_and_list_programs(client: TestClient, db_session: Session):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    res = client.get("/api/v1/academic/programs", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) >= 4

    # Verificar que los diplomados y cursos oficiales existen
    codes = [p["code"] for p in data]
    assert "DIP-MTC-01" in codes
    assert "CUR-TUI-01" in codes
    assert "DIP-FITO-02" in codes


def test_academic_programs_create_and_toggle_active_status(client: TestClient, db_session: Session):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Crear nuevo Diplomado / Curso
    payload = {
        "code": "DIP-ACU-CLIN-01",
        "name": "Diplomado en Acupuntura Clínica y Urgencias MTC",
        "program_type": "DIPLOMADO",
        "degree_title": "Diplomado en Acupuntura Hospitalaria y Urgencias",
        "description": "Protocolos rápidos de analgesia y atención clínica en box de agudos.",
        "total_semesters": 2,
        "total_theoretical_hours": 180,
        "total_practical_hours": 90,
        "min_clinical_hours": 50,
        "is_active": True,
    }
    create_res = client.post("/api/v1/academic/programs", headers=headers, json=payload)
    assert create_res.status_code == 201
    created_data = create_res.json()["data"]
    assert created_data["code"] == "DIP-ACU-CLIN-01"
    assert created_data["is_active"] is True
    program_id = created_data["id"]

    # 2. Desactivar el curso (toggle status)
    toggle_res1 = client.patch(f"/api/v1/academic/programs/{program_id}/toggle-status", headers=headers)
    assert toggle_res1.status_code == 200
    assert toggle_res1.json()["data"]["is_active"] is False

    # 3. Reactivar el curso (toggle status)
    toggle_res2 = client.patch(f"/api/v1/academic/programs/{program_id}/toggle-status", headers=headers)
    assert toggle_res2.status_code == 200
    assert toggle_res2.json()["data"]["is_active"] is True


def test_academic_course_creation_modification_and_teacher_assignment(client: TestClient, db_session: Session):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Obtener lista de docentes disponibles
    teachers_res = client.get("/api/v1/academic/programs/teachers", headers=headers)
    assert teachers_res.status_code == 200
    teachers = teachers_res.json()["data"]
    assert len(teachers) >= 3
    sample_teacher = teachers[0]
    sample_teacher_id = sample_teacher["id"]

    # 2. Obtener un programa (ej: Diplomado en Tuina o MTC)
    programs_res = client.get("/api/v1/academic/programs", headers=headers)
    target_program = next(p for p in programs_res.json()["data"] if "DIP-MTC" in p["code"])
    prog_id = target_program["id"]

    # 3. Crear una nueva asignatura asignada al programa con docente
    course_payload = {
        "code": "MTC-BIO-104",
        "name": "Bioseguridad y Manejo de Desechos en Box Acupuntural",
        "description": "Normativas REAS, esterilización y punción segura según Minsal.",
        "theoretical_hours": 20,
        "practical_hours": 20,
        "clinical_hours": 10,
        "credits": 3,
        "is_clinical_practice": False,
        "teacher_id": sample_teacher_id,
        "is_active": True,
    }
    course_res = client.post(f"/api/v1/academic/programs/{prog_id}/courses", headers=headers, json=course_payload)
    assert course_res.status_code == 201
    course_data = course_res.json()["data"]
    assert course_data["code"] == "MTC-BIO-104"
    assert course_data["teacher_id"] == sample_teacher_id
    assert course_data["teacher_name"] is not None
    course_id = course_data["id"]

    # 4. Modificar la asignatura (cambiar nombre y créditos)
    update_payload = {
        "name": "Bioseguridad Avanzada y Manejo de Desechos Cortopunzantes",
        "credits": 4,
        "practical_hours": 25,
    }
    update_res = client.put(f"/api/v1/academic/programs/courses/{course_id}", headers=headers, json=update_payload)
    assert update_res.status_code == 200
    updated_data = update_res.json()["data"]
    assert updated_data["name"] == "Bioseguridad Avanzada y Manejo de Desechos Cortopunzantes"
    assert updated_data["credits"] == 4
    assert updated_data["practical_hours"] == 25

    # 5. Reasignar a otro docente
    other_teacher = teachers[1]
    assign_res = client.put(
        f"/api/v1/academic/programs/courses/{course_id}/teacher",
        headers=headers,
        json={"teacher_id": other_teacher["id"]},
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["data"]["teacher_id"] == other_teacher["id"]

    # 6. Consultar asignaturas del programa y verificar que aparece con su docente
    prog_courses_res = client.get(f"/api/v1/academic/programs/{prog_id}/courses", headers=headers)
    assert prog_courses_res.status_code == 200
    courses_in_prog = prog_courses_res.json()["data"]
    course_found = next(c for c in courses_in_prog if c["id"] == course_id)
    assert course_found["name"] == "Bioseguridad Avanzada y Manejo de Desechos Cortopunzantes"
    assert course_found["teacher_id"] == other_teacher["id"]
