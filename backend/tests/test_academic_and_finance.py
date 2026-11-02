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
            "code": "MTC-101",
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

    # 3. Obtener el estudiante y su matrícula
    student = client.get("/api/v1/academic/students", headers=headers).json()["data"][0]
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
    student_id = students[0]["id"]

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

    # Consultar resumen acumulado: debe sumar 7 horas
    summary_res = client.get(
        f"/api/v1/academic/students/{student_id}/clinical-hours/summary",
        headers=headers,
    )
    assert summary_res.status_code == 200
    assert summary_res.json()["data"]["total_approved_hours"] == 7
