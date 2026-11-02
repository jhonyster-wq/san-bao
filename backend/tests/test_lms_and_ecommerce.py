from datetime import date
from decimal import Decimal
import pytest
from app.modules.lms.models.course import LMSCourse, CourseModule, Lesson
from app.modules.lms.models.progress import LMSEnrollment, LessonProgress, Assignment, Submission
from app.modules.ecommerce.models.product import Product
from app.modules.ecommerce.models.order import Order


def get_auth_token_and_instituto(client):
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    token = login_res.json()["data"]["access_token"]
    companies = login_res.json()["data"]["available_companies"]
    instituto = next(c for c in companies if "Instituto" in c["legal_name"] or "77123456" in c["rut"])
    return token, instituto["id"]


def test_lms_course_structure_and_lesson_progress(client):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Crear Curso en el LMS
    course_res = client.post(
        "/api/v1/lms/courses",
        headers=headers,
        json={
            "code": "LMS-PUNTOS-SHU",
            "title": "Masterclass de Puntos Shu Antiguos y Cinco Elementos",
            "summary": "Estudio profundo de los puntos de comando de los 12 canales principales",
            "instructor_name": "Profesor Chen San Bao",
        },
    )
    assert course_res.status_code == 201
    course_id = course_res.json()["data"]["id"]

    # 2. Agregar Módulo Didáctico
    module_res = client.post(
        "/api/v1/lms/courses/modules",
        headers=headers,
        json={
            "course_id": course_id,
            "title": "Unidad 1: Puntos Jing-Pozo y Ying-Manantial",
            "order_index": 1,
        },
    )
    assert module_res.status_code == 201
    module_id = module_res.json()["data"]["id"]

    # 3. Agregar 2 Lecciones (Video y Documento)
    lesson1_res = client.post(
        "/api/v1/lms/courses/lessons",
        headers=headers,
        json={
            "module_id": module_id,
            "title": "Clase 1: Localización y función de los Puntos Pozo",
            "content_type": "VIDEO",
            "video_url": "https://vimeo.com/sanbao/shu-antiguos-1",
            "duration_minutes": 45,
            "order_index": 1,
        },
    )
    assert lesson1_res.status_code == 201
    lesson1_id = lesson1_res.json()["data"]["id"]

    lesson2_res = client.post(
        "/api/v1/lms/courses/lessons",
        headers=headers,
        json={
            "module_id": module_id,
            "title": "Clase 2: Tabla comparativa de los Puntos Manantial",
            "content_type": "DOCUMENT",
            "attachment_url": "https://cdn.sanbao.cl/docs/tabla-ying.pdf",
            "duration_minutes": 30,
            "order_index": 2,
        },
    )
    assert lesson2_res.status_code == 201
    lesson2_id = lesson2_res.json()["data"]["id"]

    # 4. Enrolar al usuario administrador en el curso
    enroll_res = client.post(
        f"/api/v1/lms/courses/{course_id}/enroll",
        headers=headers,
    )
    assert enroll_res.status_code == 201
    assert Decimal(str(enroll_res.json()["data"]["progress_percentage"])) == Decimal("0.0")

    # 5. Marcar Lección 1 como completada -> progreso debe subir a 50%
    prog1_res = client.post(
        "/api/v1/lms/lessons/progress",
        headers=headers,
        json={"lesson_id": lesson1_id, "is_completed": True},
    )
    assert prog1_res.status_code == 200

    # 6. Marcar Lección 2 como completada -> progreso debe subir a 100%
    prog2_res = client.post(
        "/api/v1/lms/lessons/progress",
        headers=headers,
        json={"lesson_id": lesson2_id, "is_completed": True},
    )
    assert prog2_res.status_code == 200

    # Verificar Mis Cursos
    my_courses_res = client.get("/api/v1/lms/my-courses", headers=headers)
    assert my_courses_res.status_code == 200
    my_enrollments = my_courses_res.json()["data"]
    target_enrollment = next(e for e in my_enrollments if e["course_id"] == course_id)
    assert Decimal(str(target_enrollment["progress_percentage"])) == Decimal("100.0")
    assert target_enrollment["status"] == "COMPLETED"


def test_lms_assignment_submission_and_grading(client):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # Obtener el curso y sus lecciones
    courses = client.get("/api/v1/lms/courses", headers=headers).json()["data"]
    course = courses[0]
    lesson = course["modules"][0]["lessons"][0]

    # 1. Crear Tarea en la Lección
    assign_res = client.post(
        "/api/v1/lms/assignments",
        headers=headers,
        json={
            "lesson_id": lesson["id"],
            "title": "Ensayo sobre aplicación clínica del punto E45 (Lidui)",
            "instructions": "Describir indicaciones y método de sangría según el Ling Shu.",
            "max_score": "7.0",
        },
    )
    assert assign_res.status_code == 201
    assignment_id = assign_res.json()["data"]["id"]

    # 2. Entregar Tarea por parte del estudiante
    sub_res = client.post(
        "/api/v1/lms/submissions",
        headers=headers,
        json={
            "assignment_id": assignment_id,
            "content_text": "El punto E45 se ubica en el ángulo ungueal lateral del segundo dedo del pie...",
            "attachment_url": "https://cdn.sanbao.cl/tareas/entrega-e45.pdf",
        },
    )
    assert sub_res.status_code == 201
    submission_id = sub_res.json()["data"]["id"]
    assert sub_res.json()["data"]["status"] == "SUBMITTED"

    # 3. Docente califica la entrega (escala 1.0 a 7.0)
    grade_res = client.post(
        f"/api/v1/lms/submissions/{submission_id}/grade",
        headers=headers,
        json={"score": "6.7", "feedback": "Excelente fundamentación teórica de acuerdo al texto clásico."},
    )
    assert grade_res.status_code == 200
    graded_data = grade_res.json()["data"]
    assert graded_data["status"] == "GRADED"
    assert Decimal(str(graded_data["score"])) == Decimal("6.7")


def test_ecommerce_checkout_to_lms_auto_enrollment(client):
    token, instituto_id = get_auth_token_and_instituto(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": instituto_id}

    # 1. Crear un Curso en el LMS para venta online
    course_res = client.post(
        "/api/v1/lms/courses",
        headers=headers,
        json={
            "code": "WEB-FITOTERAPIA",
            "title": "Seminario Online: Fórmulas Clásicas de Fitoterapia China",
            "summary": "Aplicación de fórmulas magistrales en medicina integrativa",
        },
    )
    lms_course_id = course_res.json()["data"]["id"]

    # 2. Publicar Producto en la Tienda E-Commerce vinculado a este curso LMS
    prod_res = client.post(
        "/api/v1/ecommerce/products",
        headers=headers,
        json={
            "sku": "CURSO-FITO-ONLINE",
            "name": "Seminario Online de Fitoterapia China",
            "slug": "seminario-online-fitoterapia-china",
            "price_clp": "120000",
            "promotional_price_clp": "99000",
            "is_digital": True,
            "lms_course_id": lms_course_id,
        },
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["data"]["id"]

    # 3. Checkout Público: Visitante web compra el curso (sin estar logueado previamente)
    # RUT chileno válido Módulo 11: 17.123.456-5
    checkout_payload = {
        "customer_name": "Marcela Soto Carrasco",
        "customer_email": "marcela.soto@gmail.com",
        "customer_rut": "17.123.456-5",
        "customer_phone": "+56 9 6677 8899",
        "payment_gateway": "WEBPAY_PLUS",
        "items": [{"product_id": product_id, "quantity": 1}],
    }
    checkout_res = client.post(
        f"/api/v1/ecommerce/orders/checkout?company_id={instituto_id}",
        json=checkout_payload,
    )
    assert checkout_res.status_code == 201
    order_data = checkout_res.json()["data"]
    order_id = order_data["id"]
    assert order_data["payment_status"] == "PENDING"
    # Debe cobrar el precio promocional ($99.000)
    assert Decimal(str(order_data["total_amount"])) == Decimal("99000")

    # 4. Confirmación de Pago Webpay (Webhook / Retorno exitoso de pasarela)
    confirm_payload = {
        "gateway": "WEBPAY_PLUS",
        "transaction_id": "TBK-TX-99887766",
        "authorization_code": "AUTH-778899",
        "status": "SUCCESS",
    }
    confirm_res = client.post(
        f"/api/v1/ecommerce/orders/{order_id}/confirm-payment",
        json=confirm_payload,
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()["data"]
    assert confirm_data["order"]["payment_status"] == "PAID"
    assert confirm_data["user_created"] is True
    assert "Seminario Online" in confirm_data["enrolled_courses"][0]

    # 5. Iniciar sesión con la cuenta auto-aprovisionada de la compradora
    # Usuario generado a partir del email + últimos 4 dígitos del RUT
    username = confirm_data["order"]["customer_email"].split("@")[0] + "_3456"
    buyer_login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "17.123.456-5", "password": "SanBaoAlumno2026!"},
    )
    assert buyer_login_res.status_code == 200
    buyer_token = buyer_login_res.json()["data"]["access_token"]

    # 6. La compradora consulta sus cursos en el LMS: debe tener acceso inmediato
    buyer_headers = {"Authorization": f"Bearer {buyer_token}"}
    buyer_courses_res = client.get("/api/v1/lms/my-courses", headers=buyer_headers)
    assert buyer_courses_res.status_code == 200
    buyer_courses = buyer_courses_res.json()["data"]
    assert len(buyer_courses) == 1
    assert buyer_courses[0]["course_id"] == lms_course_id
    assert buyer_courses[0]["status"] == "ACTIVE"
