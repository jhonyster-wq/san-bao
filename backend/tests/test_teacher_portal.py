import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db
from app.modules.academic.services.teacher_portal_service import TeacherPortalService


@pytest.fixture
def client():
    return TestClient(app)


def test_teacher_assigned_courses(client: TestClient, db_session: Session):
    """Prueba 1: El docente visualiza sus cursos asignados con métricas de matrícula, asistencia y notas."""
    service = TeacherPortalService(db_session)
    teacher_person = service.ensure_sample_teacher_data()

    response = client.get(
        "/api/v1/academic/teacher/courses",
        params={"teacher_id": teacher_person.id},
        headers={"X-Company-ID": "instituto"},
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    courses = json_data["data"]
    assert len(courses) >= 1

    # Verificar que el curso principal MTC-101 tiene datos válidos
    course = next((c for c in courses if c["code"] == "MTC-101"), courses[0])
    assert "name" in course
    assert course["enrolled_students_count"] >= 1
    assert course["theoretical_hours"] > 0
    assert course["credits"] >= 1


def test_teacher_grade_entry_and_evaluations(client: TestClient, db_session: Session):
    """Prueba 2: El docente registra notas por alumno en escala oficial chilena 1.0 a 7.0 y crea evaluaciones."""
    service = TeacherPortalService(db_session)
    teacher_person = service.ensure_sample_teacher_data()
    courses = service.list_teacher_assigned_courses(teacher_person.id)
    course = next((c for c in courses if c["code"] == "MTC-101"), courses[0])
    course_id = course["id"]

    # 1. Obtener planilla actual
    res_grades = client.get(f"/api/v1/academic/teacher/courses/{course_id}/grades")
    assert res_grades.status_code == 200
    data_grades = res_grades.json()["data"]
    assert len(data_grades["evaluations"]) >= 1
    assert len(data_grades["students"]) >= 1

    eval_id = data_grades["evaluations"][0]["id"]
    student_id = data_grades["students"][0]["student_id"]

    # 2. Registrar nota de 6.7 con retroalimentación
    payload = {
        "evaluation_id": eval_id,
        "student_id": student_id,
        "score": 6.7,
        "feedback": "Excelente fundamentación teórica de los principios Daoístas y Wu Xing.",
    }
    res_entry = client.post(f"/api/v1/academic/teacher/courses/{course_id}/grades", json=payload)
    assert res_entry.status_code == 200
    entry_data = res_entry.json()["data"]
    assert entry_data["score"] == 6.7
    assert entry_data["is_approved"] is True

    # 3. Crear una nueva evaluación de cátedra
    new_eval_payload = {
        "name": "Control Práctico: Puntos Shu Antiguos",
        "weight_percentage": 20.0,
        "evaluation_date": date(2026, 6, 10).isoformat(),
        "description": "Evaluación en taller presencial de localización de puntos Shu.",
    }
    res_create_eval = client.post(f"/api/v1/academic/teacher/courses/{course_id}/evaluations", json=new_eval_payload)
    assert res_create_eval.status_code == 200
    assert res_create_eval.json()["data"]["name"] == "Control Práctico: Puntos Shu Antiguos"


def test_teacher_attendance_recording(client: TestClient, db_session: Session):
    """Prueba 3: El docente registra la asistencia por alumno por clase (Presente, Ausente, Justificado, Atraso)."""
    service = TeacherPortalService(db_session)
    teacher_person = service.ensure_sample_teacher_data()
    courses = service.list_teacher_assigned_courses(teacher_person.id)
    course = next((c for c in courses if c["code"] == "MTC-101"), courses[0])
    course_id = course["id"]

    # 1. Consultar asistencia actual
    res_att = client.get(f"/api/v1/academic/teacher/courses/{course_id}/attendance")
    assert res_att.status_code == 200
    att_data = res_att.json()["data"]
    assert len(att_data["students"]) >= 1
    students = att_data["students"]

    # 2. Guardar asistencia de nueva clase
    class_date = date(2026, 4, 7).isoformat()
    batch_payload = {
        "class_date": class_date,
        "class_number": 5,
        "session_topic": "Clase 5: Fisiología de las Entrañas Fu y Canales Extraordinarios",
        "records": [
            {"student_id": students[0]["student_id"], "status": "PRESENTE", "notes": "Participación activa"},
            {"student_id": students[1]["student_id"], "status": "PRESENTE", "notes": "Asistencia puntual"},
            {"student_id": students[2]["student_id"], "status": "JUSTIFICADO", "notes": "Presentó certificado de salud"},
            {"student_id": students[3]["student_id"], "status": "ATRASO", "notes": "Ingresó 15 min tarde"},
        ],
    }
    res_save = client.post(f"/api/v1/academic/teacher/courses/{course_id}/attendance", json=batch_payload)
    assert res_save.status_code == 200
    save_result = res_save.json()["data"]
    assert save_result["records_saved"] == 4
    assert save_result["summary"]["PRESENTE"] == 2
    assert save_result["summary"]["JUSTIFICADO"] == 1
    assert save_result["summary"]["ATRASO"] == 1

    # 3. Consultar asistencia en la fecha guardada
    res_check = client.get(f"/api/v1/academic/teacher/courses/{course_id}/attendance", params={"class_date": class_date})
    assert res_check.status_code == 200
    check_students = res_check.json()["data"]["students"]
    assert next(s for s in check_students if s["student_id"] == students[0]["student_id"])["status"] == "PRESENTE"
    assert next(s for s in check_students if s["student_id"] == students[2]["student_id"])["status"] == "JUSTIFICADO"


def test_teacher_course_content_upload_and_delete(client: TestClient, db_session: Session):
    """Prueba 4: El docente sube y administra contenidos didácticos por curso y clase."""
    service = TeacherPortalService(db_session)
    teacher_person = service.ensure_sample_teacher_data()
    courses = service.list_teacher_assigned_courses(teacher_person.id)
    course = next((c for c in courses if c["code"] == "MTC-101"), courses[0])
    course_id = course["id"]

    # 1. Subir nuevo contenido para la Clase 5
    upload_payload = {
        "class_number": 5,
        "class_title": "Clase 5: Canales Extraordinarios y Puntos Confluentes",
        "resource_title": "Guía Práctica N° 3: Vasos Extraordinarios (Ba Mai)",
        "resource_type": "DOCUMENTO_PDF",
        "attachment_url": "/static/academic/materials/guia_ba_mai.pdf",
        "description": "Esquemas y trayectos de los canales Ren Mai, Du Mai y Chong Mai.",
        "file_size_text": "PDF 3.8 MB",
        "is_published": True,
    }
    res_upload = client.post(f"/api/v1/academic/teacher/courses/{course_id}/contents", json=upload_payload)
    assert res_upload.status_code == 201
    content_data = res_upload.json()["data"]
    content_id = content_data["id"]
    assert content_data["resource_title"] == "Guía Práctica N° 3: Vasos Extraordinarios (Ba Mai)"

    # 2. Listar contenidos del curso
    res_list = client.get(f"/api/v1/academic/teacher/courses/{course_id}/contents")
    assert res_list.status_code == 200
    list_data = res_list.json()["data"]
    assert list_data["total_contents"] >= 1
    # Debe estar presente en la lista de clases
    clase5 = next((c for c in list_data["classes"] if c["class_number"] == 5), None)
    assert clase5 is not None
    assert any(item["id"] == content_id for item in clase5["items"])

    # 3. Eliminar contenido
    res_delete = client.delete(f"/api/v1/academic/teacher/contents/{content_id}")
    assert res_delete.status_code == 200

    # 4. Verificar que se eliminó
    res_list_after = client.get(f"/api/v1/academic/teacher/courses/{course_id}/contents")
    all_items = [item for cl in res_list_after.json()["data"]["classes"] for item in cl["items"]]
    assert not any(item["id"] == content_id for item in all_items)
