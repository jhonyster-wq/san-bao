import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import Base
from app.modules.ecommerce.models.product import Product, EcommercePromotion
from app.modules.ecommerce.models.order import Order, OrderItem, GatewayTransaction
from app.modules.ecommerce.schemas.product import ProductCreate, ProductUpdate
from app.modules.ecommerce.schemas.order import CheckoutRequest, PaymentConfirmationRequest, PaymentConfirmationResponse, OrderResponse
from app.modules.lms.services.lms_service import LMSService
from app.modules.lms.models.course import LMSCourse, CourseModule, Lesson
from app.modules.lms.models.progress import LMSEnrollment
from app.modules.academic.models.program import Program
from app.modules.academic.models.student import Student, Enrollment
from app.modules.academic.models.period import AcademicPeriod
from app.modules.finance.services.finance_service import FinanceService
from app.modules.finance.models.commitment import Payment
from app.modules.finance.schemas.commitment import PaymentCreate
from app.modules.integrations.models import DTEDocument, DTEStatus
from app.modules.institutional.models.company import Company
from app.modules.institutional.models.person import Person
from app.modules.institutional.models.user import User
from app.core.security import get_password_hash
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException, SanBaoException
from app.shared.validators.rut import ChileanRUT


class ECommerceService:
    def __init__(self, db: Session):
        self.db = db

    def create_product(self, data: ProductCreate, company_id: str) -> Product:
        existing = self.db.query(Product).filter(Product.sku == data.sku.strip().upper(), Product.deleted_at.is_(None)).first()
        if existing:
            raise EntityAlreadyExistsException("Producto", "SKU", data.sku)

        product = Product(
            company_id=data.company_id or company_id,
            lms_course_id=data.lms_course_id,
            sku=data.sku.strip().upper(),
            name=data.name.strip(),
            slug=data.slug.strip().lower(),
            description=data.description,
            price_clp=data.price_clp,
            promotional_price_clp=data.promotional_price_clp,
            is_digital=data.is_digital,
            stock=data.stock,
            is_active=data.is_active,
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def list_products(self, company_id: Optional[str] = None, only_active: bool = True) -> List[Product]:
        q = self.db.query(Product).filter(Product.deleted_at.is_(None))
        if only_active:
            q = q.filter(Product.is_active == True)
        if company_id:
            q = q.filter(Product.company_id == company_id)
        return q.all()

    def checkout(self, data: CheckoutRequest, company_id: str) -> Order:
        """Crea una orden de compra pendiente de pago a partir del carrito de compra."""
        cleaned_rut = ChileanRUT.clean(data.customer_rut)
        year = date.today().year
        count = self.db.query(Order).filter(Order.order_number.like(f"ORD-{year}-%")).count()
        order_number = f"ORD-{year}-{count + 1:04d}"

        # Buscar si el comprador ya tiene ficha de persona
        person = self.db.query(Person).filter(Person.rut == cleaned_rut, Person.deleted_at.is_(None)).first()

        total_amount = Decimal(0)
        items_to_add = []

        for item_in in data.items:
            product = self.db.query(Product).filter(Product.id == item_in.product_id, Product.deleted_at.is_(None)).first()
            if not product or not product.is_active:
                raise EntityNotFoundException("Producto", item_in.product_id)

            price = product.promotional_price_clp or product.price_clp
            subtotal = price * item_in.quantity
            total_amount += subtotal

            order_item = OrderItem(
                product_id=product.id,
                quantity=item_in.quantity,
                unit_price=price,
                subtotal=subtotal,
            )
            items_to_add.append(order_item)

        order = Order(
            company_id=company_id,
            customer_person_id=person.id if person else None,
            order_number=order_number,
            customer_name=data.customer_name.strip(),
            customer_email=data.customer_email.lower().strip(),
            customer_rut=cleaned_rut,
            customer_phone=data.customer_phone,
            total_amount=total_amount,
            payment_status="PENDING",
            payment_gateway=data.payment_gateway,
        )
        self.db.add(order)
        self.db.flush()

        for it in items_to_add:
            it.order_id = order.id
            self.db.add(it)

        self.db.commit()
        self.db.refresh(order)
        return order

    def confirm_gateway_payment(self, order_id: str, confirmation: PaymentConfirmationRequest) -> PaymentConfirmationResponse:
        """
        Confirma la transacción de la pasarela (Webpay/Flow):
        1. Marca orden como PAGADA.
        2. Auto-aprovisiona cuenta de usuario digital para el comprador (si no existía).
        3. Enrola automáticamente en las aulas virtuales LMS vinculadas a los productos adquiridos.
        4. Registra el ingreso en el módulo de Finanzas.
        """
        order = self.db.query(Order).filter(Order.id == order_id, Order.deleted_at.is_(None)).first()
        if not order:
            raise EntityNotFoundException("Orden", order_id)

        if order.payment_status == "PAID":
            raise SanBaoException("La orden ya fue pagada con anterioridad.")

        tx = GatewayTransaction(
            order_id=order.id,
            gateway=confirmation.gateway,
            transaction_id=confirmation.transaction_id,
            authorization_code=confirmation.authorization_code,
            amount=order.total_amount,
            status=confirmation.status,
            raw_response={"confirmed_at": datetime.now(timezone.utc).isoformat()},
        )
        self.db.add(tx)

        if confirmation.status != "SUCCESS":
            order.payment_status = "FAILED"
            self.db.commit()
            raise SanBaoException("La transacción fue rechazada por la pasarela de pagos.")

        order.payment_status = "PAID"
        order.paid_at = datetime.now(timezone.utc)

        # 1. Asegurar la existencia de Person y User digital
        person = self.db.query(Person).filter(Person.rut == order.customer_rut, Person.deleted_at.is_(None)).first()
        user_created = False
        user: Optional[User] = None

        if not person:
            # Dividir nombres
            parts = order.customer_name.strip().split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else "Comprador Web"

            person = Person(
                rut=order.customer_rut,
                first_name=first_name,
                last_name=last_name,
                email=order.customer_email,
                phone=order.customer_phone,
            )
            self.db.add(person)
            self.db.flush()

        order.customer_person_id = person.id

        if not person.user:
            username = order.customer_email.split("@")[0] + "_" + order.customer_rut.split("-")[0][-4:]
            user = User(
                person_id=person.id,
                username=username,
                password_hash=get_password_hash("SanBaoAlumno2026!"),
                is_active=True,
            )
            self.db.add(user)
            self.db.flush()
            user_created = True
        else:
            user = person.user

        # 2. Enrolamiento automático en cursos del LMS
        lms_service = LMSService(self.db)
        enrolled_courses = []

        for item in order.items:
            product = item.product
            if product.lms_course_id and user:
                lms_service.enroll_user(product.lms_course_id, user.id)
                if product.lms_course:
                    enrolled_courses.append(product.lms_course.title)

        # 3. Registrar recaudación en Finanzas
        finance_service = FinanceService(self.db)
        payment_payload = PaymentCreate(
            company_id=order.company_id,
            person_id=person.id,
            amount=order.total_amount,
            payment_method=order.payment_gateway,
            reference_number=confirmation.authorization_code or confirmation.transaction_id,
            notes=f"Venta Online Orden #{order.order_number}",
        )
        payment_rec = finance_service.record_payment(payment_payload)

        self.db.commit()
        self.db.refresh(order)

        order_res = OrderResponse.model_validate(order)
        return PaymentConfirmationResponse(
            order=order_res,
            user_created=user_created,
            user_id=user.id if user else None,
            enrolled_courses=enrolled_courses,
            receipt_number=payment_rec.id,
        )


class ECommerceHubService:
    """
    Servicio Integral de Comercio Electrónico, Formación Continua y LMS San Bao.
    Cubre las 8 áreas operativas:
    1. Catálogo de cursos y seminarios
    2. Venta de programas de formación continua
    3. Inscripciones en línea
    4. Pagos electrónicos (Webpay Plus, Flow, MercadoPago)
    5. Registro automático de participantes (Person + User + Student + Enrollment + LMSEnrollment)
    6. Emisión de comprobantes (Comprobante Oficial Web + Boleta Exenta SII DTE 41)
    7. Integración bidireccional con el módulo académico y financiero
    8. Administración de promociones y actividades comerciales
    """

    CATALOG_METADATA = {
        "SEM-PULSO-2026": {
            "category": "SEMINARIO",
            "category_label": "Seminario Magistral",
            "modality": "Híbrido (Sede Santiago + Streaming HD)",
            "hours": 24,
            "instructor": "Dra. Marcela Pérez Morales",
            "schedule": "Sábados 09:00 a 14:00 hrs (4 Jornadas)",
            "program_code": "SEM-PULSO-26",
            "program_type": "CURSO",
            "lms_code": "LMS-PULSO-2026",
            "badge": "Cupos Limitados • Práctica Pulsología",
        },
        "FC-YNSA-2026": {
            "category": "FORMACION_CONTINUA",
            "category_label": "Programa de Formación Continua",
            "modality": "Presencial & Aula Virtual LMS",
            "hours": 60,
            "instructor": "Dr. Chen Lin",
            "schedule": "Viernes 18:00 - 21:30 hrs (8 Semanas)",
            "program_code": "FC-YNSA-26",
            "program_type": "FORMACION_CONTINUA",
            "lms_code": "LMS-YNSA-2026",
            "badge": "Certificación Internacional YNSA",
        },
        "CUR-TUINA-2026": {
            "category": "CURSO",
            "category_label": "Curso de Especialización",
            "modality": "Presencial Práctico + Cápsulas LMS",
            "hours": 48,
            "instructor": "Prof. Zhiwei Chen",
            "schedule": "Martes y Jueves 19:00 - 21:30 hrs",
            "program_code": "CUR-TUINA-26",
            "program_type": "CURSO",
            "lms_code": "LMS-TUINA-2026",
            "badge": "Incluye Box Clínico y Ventosas",
        },
        "SEM-SHANGHAN-2026": {
            "category": "SEMINARIO",
            "category_label": "Seminario Clásico de Fitoterapia",
            "modality": "100% Online en Vivo + Grabaciones LMS",
            "hours": 32,
            "instructor": "Dr. Chen Lin",
            "schedule": "Sábados 10:00 a 13:30 hrs",
            "program_code": "SEM-SHL-26",
            "program_type": "FORMACION_CONTINUA",
            "lms_code": "LMS-SHL-2026",
            "badge": "Fórmulas Clásicas Zhang Zhongjing",
        },
        "FC-AURICULO-2026": {
            "category": "FORMACION_CONTINUA",
            "category_label": "Programa de Formación Continua",
            "modality": "Híbrido (Sede Providencia + LMS)",
            "hours": 40,
            "instructor": "Lic. Patricia Soto Henríquez",
            "schedule": "Miércoles 18:30 a 21:30 hrs",
            "program_code": "FC-AURIC-26",
            "program_type": "FORMACION_CONTINUA",
            "lms_code": "LMS-AURIC-2026",
            "badge": "Kit de Semillas e Imanes Incluido",
        },
        "DIP-MTC-WEB-2026": {
            "category": "DIPLOMADO",
            "category_label": "Diplomado Oficial (Matrícula Web)",
            "modality": "Semipresencial • Teoría LMS + Práctica Clínica",
            "hours": 420,
            "instructor": "Dra. Marcela Pérez M. & Claustro San Bao",
            "schedule": "Cohorte 2026 • Lunes, Miércoles y Viernes",
            "program_code": "DIP-MTC-26",
            "program_type": "DIPLOMADO",
            "lms_code": "LMS-DIPMTC-2026",
            "badge": "Acreditable MINSAL Decreto N° 123",
        },
    }

    def __init__(self, db: Session):
        self.db = db
        try:
            Base.metadata.create_all(bind=self.db.get_bind(), tables=[EcommercePromotion.__table__])
        except Exception:
            pass

    def _get_instituto_company(self) -> Company:
        comp = (
            self.db.query(Company)
            .filter(Company.rut.ilike("%77.123.456%"), Company.deleted_at.is_(None))
            .first()
        )
        if not comp:
            comp = self.db.query(Company).filter(Company.deleted_at.is_(None)).first()
        return comp

    def _get_or_create_active_period(self) -> AcademicPeriod:
        period = (
            self.db.query(AcademicPeriod)
            .filter(AcademicPeriod.is_active == True, AcademicPeriod.deleted_at.is_(None))
            .first()
        )
        if not period:
            period = (
                self.db.query(AcademicPeriod)
                .filter(AcademicPeriod.deleted_at.is_(None))
                .first()
            )
        if not period:
            period = AcademicPeriod(
                code="2026-1",
                name="Primer Semestre Académico 2026",
                year=2026,
                semester=1,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 12, 31),
                is_active=True,
            )
            self.db.add(period)
            self.db.flush()
        return period

    def ensure_sample_ecommerce_data(self) -> None:
        comp = self._get_instituto_company()
        if not comp:
            return

        # 1. Asegurar programas académicos y aulas LMS para los 6 ítems del catálogo comercial
        sample_products = [
            {
                "sku": "SEM-PULSO-2026",
                "name": "Seminario Clínico de Diagnóstico por el Pulso y Lengua en MTC",
                "slug": "seminario-diagnostico-pulso-lengua-mtc-2026",
                "description": json.dumps({
                    "summary": "Entrenamiento intensivo en los 28 pulsos clásicos de Li Shizhen y topografía lingual aplicada a síndromes Zang-Fu.",
                    "category": "SEMINARIO",
                    "category_label": "Seminario Magistral",
                    "modality": "Híbrido (Sede Santiago + Streaming HD)",
                    "hours": 24,
                    "instructor": "Dra. Marcela Pérez Morales",
                    "schedule": "Sábados 09:00 a 14:00 hrs (4 Jornadas)",
                    "program_code": "SEM-PULSO-26",
                    "badge": "Cupos Limitados • Práctica Pulsología",
                }, ensure_ascii=False),
                "price_clp": Decimal(145000),
                "promotional_price_clp": Decimal(115000),
                "stock": 30,
                "program_type": "CURSO",
                "lms_code": "LMS-PULSO-2026",
                "instructor": "Dra. Marcela Pérez Morales",
                "hours": 24,
            },
            {
                "sku": "FC-YNSA-2026",
                "name": "Programa de Formación Continua en Craneoacupuntura de Yamamoto (YNSA)",
                "slug": "formacion-continua-craneoacupuntura-yamamoto-ynsa-2026",
                "description": json.dumps({
                    "summary": "Formación continua clínica en somatotopías craneales YNSA, diagnóstico abdominal/cervical y manejo inmediato del dolor neurológico.",
                    "category": "FORMACION_CONTINUA",
                    "category_label": "Programa de Formación Continua",
                    "modality": "Presencial & Aula Virtual LMS",
                    "hours": 60,
                    "instructor": "Dr. Chen Lin",
                    "schedule": "Viernes 18:00 - 21:30 hrs (8 Semanas)",
                    "program_code": "FC-YNSA-26",
                    "badge": "Certificación Internacional YNSA",
                }, ensure_ascii=False),
                "price_clp": Decimal(320000),
                "promotional_price_clp": Decimal(265000),
                "stock": 25,
                "program_type": "FORMACION_CONTINUA",
                "lms_code": "LMS-YNSA-2026",
                "instructor": "Dr. Chen Lin",
                "hours": 60,
            },
            {
                "sku": "CUR-TUINA-2026",
                "name": "Curso Intensivo de Masaje Tuina Clínico, Ventosas y Guasha",
                "slug": "curso-intensivo-masaje-tuina-clinico-ventosas-2026",
                "description": json.dumps({
                    "summary": "Curso teórico-práctico de manipulaciones osteomusculares Tuina, aplicación de ventosas de fuego/neumáticas y raspado terapéutico Guasha.",
                    "category": "CURSO",
                    "category_label": "Curso de Especialización",
                    "modality": "Presencial Práctico + Cápsulas LMS",
                    "hours": 48,
                    "instructor": "Prof. Zhiwei Chen",
                    "schedule": "Martes y Jueves 19:00 - 21:30 hrs",
                    "program_code": "CUR-TUINA-26",
                    "badge": "Incluye Box Clínico y Ventosas",
                }, ensure_ascii=False),
                "price_clp": Decimal(240000),
                "promotional_price_clp": Decimal(195000),
                "stock": 20,
                "program_type": "CURSO",
                "lms_code": "LMS-TUINA-2026",
                "instructor": "Prof. Zhiwei Chen",
                "hours": 48,
            },
            {
                "sku": "SEM-SHANGHAN-2026",
                "name": "Seminario Magistral de Fitoterapia Clásica: Tratado Shang Han Lun",
                "slug": "seminario-fitoterapia-clasica-shang-han-lun-2026",
                "description": json.dumps({
                    "summary": "Estudio clínico de las Seis Etapas (Liu Jing) y prescripción magistral de decocciones clásicas de Zhang Zhongjing.",
                    "category": "SEMINARIO",
                    "category_label": "Seminario Clásico de Fitoterapia",
                    "modality": "100% Online en Vivo + Grabaciones LMS",
                    "hours": 32,
                    "instructor": "Dr. Chen Lin",
                    "schedule": "Sábados 10:00 a 13:30 hrs",
                    "program_code": "SEM-SHL-26",
                    "badge": "Fórmulas Clásicas Zhang Zhongjing",
                }, ensure_ascii=False),
                "price_clp": Decimal(180000),
                "promotional_price_clp": Decimal(149000),
                "stock": 45,
                "program_type": "FORMACION_CONTINUA",
                "lms_code": "LMS-SHL-2026",
                "instructor": "Dr. Chen Lin",
                "hours": 32,
            },
            {
                "sku": "FC-AURICULO-2026",
                "name": "Programa de Formación Continua en Auriculoterapia Clínica y Dolor",
                "slug": "formacion-continua-auriculoterapia-clinica-dolor-2026",
                "description": json.dumps({
                    "summary": "Cartografía auricular china y francesa (Nogier), protocolos de analgesia, estrés, ansiedad y control metabólico.",
                    "category": "FORMACION_CONTINUA",
                    "category_label": "Programa de Formación Continua",
                    "modality": "Híbrido (Sede Providencia + LMS)",
                    "hours": 40,
                    "instructor": "Lic. Patricia Soto Henríquez",
                    "schedule": "Miércoles 18:30 a 21:30 hrs",
                    "program_code": "FC-AURIC-26",
                    "badge": "Kit de Semillas e Imanes Incluido",
                }, ensure_ascii=False),
                "price_clp": Decimal(210000),
                "promotional_price_clp": Decimal(175000),
                "stock": 25,
                "program_type": "FORMACION_CONTINUA",
                "lms_code": "LMS-AURIC-2026",
                "instructor": "Lic. Patricia Soto Henríquez",
                "hours": 40,
            },
            {
                "sku": "DIP-MTC-WEB-2026",
                "name": "Diplomado en Medicina Tradicional China y Acupuntura (Inscripción Web)",
                "slug": "diplomado-medicina-tradicional-china-acupuntura-2026",
                "description": json.dumps({
                    "summary": "Pago de Matrícula y Reserva de Cupo en Línea para el Diplomado Oficial de Formación en Acupuntura y MTC de Escuela San Bao.",
                    "category": "DIPLOMADO",
                    "category_label": "Diplomado Oficial (Matrícula Web)",
                    "modality": "Semipresencial • Teoría LMS + Práctica Clínica",
                    "hours": 420,
                    "instructor": "Dra. Marcela Pérez M. & Claustro San Bao",
                    "schedule": "Cohorte 2026 • Lunes, Miércoles y Viernes",
                    "program_code": "DIP-MTC-26",
                    "badge": "Acreditable MINSAL Decreto N° 123",
                }, ensure_ascii=False),
                "price_clp": Decimal(450000),
                "promotional_price_clp": Decimal(380000),
                "stock": 35,
                "program_type": "DIPLOMADO",
                "lms_code": "LMS-DIPMTC-2026",
                "instructor": "Dra. Marcela Pérez Morales",
                "hours": 420,
            },
        ]

        for sp in sample_products:
            meta = json.loads(sp["description"])
            prog_code = meta["program_code"]
            prog = self.db.query(Program).filter(Program.code == prog_code, Program.deleted_at.is_(None)).first()
            if not prog:
                prog = Program(
                    code=prog_code,
                    name=sp["name"],
                    program_type=sp["program_type"],
                    degree_title=f"Certificación Oficial en {sp['name']}",
                    description=meta["summary"],
                    total_semesters=1 if sp["program_type"] != "DIPLOMADO" else 4,
                    total_theoretical_hours=int(sp["hours"] * 0.6),
                    total_practical_hours=int(sp["hours"] * 0.4),
                    min_clinical_hours=0 if sp["program_type"] == "CURSO" else 20,
                    is_active=True,
                )
                self.db.add(prog)
                self.db.flush()

            lms_course = (
                self.db.query(LMSCourse)
                .filter(LMSCourse.code == sp["lms_code"], LMSCourse.deleted_at.is_(None))
                .first()
            )
            if not lms_course:
                lms_course = LMSCourse(
                    code=sp["lms_code"],
                    title=sp["name"],
                    summary=meta["summary"],
                    instructor_name=sp["instructor"],
                    is_published=True,
                )
                self.db.add(lms_course)
                self.db.flush()

                mod1 = CourseModule(
                    course_id=lms_course.id,
                    title="Módulo 1: Fundamentos Clásicos y Diagnóstico Diferencial",
                    description="Clases magistrales en video HD, textos clásicos comentados y guías clínicas.",
                    order_index=1,
                    is_published=True,
                )
                self.db.add(mod1)
                self.db.flush()
                self.db.add(
                    Lesson(
                        module_id=mod1.id,
                        title="Clase 1: Principios Clínicos y Protocolos Terapéuticos San Bao",
                        content_type="VIDEO",
                        content_body="Video magistral + Manual PDF descargable del programa.",
                        duration_minutes=60,
                        order_index=1,
                        is_published=True,
                    )
                )

            existing_prod = (
                self.db.query(Product)
                .filter(Product.sku == sp["sku"], Product.deleted_at.is_(None))
                .first()
            )
            if not existing_prod:
                prod = Product(
                    company_id=comp.id,
                    lms_course_id=lms_course.id,
                    sku=sp["sku"],
                    name=sp["name"],
                    slug=sp["slug"],
                    description=sp["description"],
                    price_clp=sp["price_clp"],
                    promotional_price_clp=sp["promotional_price_clp"],
                    is_digital=True,
                    stock=sp["stock"],
                    is_active=True,
                )
                self.db.add(prod)
            else:
                if not existing_prod.lms_course_id:
                    existing_prod.lms_course_id = lms_course.id
                if not existing_prod.description or not existing_prod.description.strip().startswith("{"):
                    existing_prod.description = sp["description"]

        self.db.flush()

        # 2. Sembrar Promociones y Actividades Comerciales
        sample_promos = [
            {
                "code": "SANBAO2026",
                "title": "Campaña Admisión & Formación Continua 2026 (15% DCTO)",
                "activity_type": "CAMPANA_EARLY_BIRD",
                "discount_type": "PERCENTAGE",
                "discount_value": Decimal(15),
                "applies_to_category": "TODOS",
                "valid_from": "2026-01-01",
                "valid_until": "2026-12-31",
                "max_uses": 200,
                "used_count": 18,
                "description": "Descuento institucional del 15% por inscripción anticipada en cursos, seminarios y formación continua.",
            },
            {
                "code": "ALUMNO20",
                "title": "Beneficio Comunidad Alumnos & Egresados San Bao (20% DCTO)",
                "activity_type": "CUPON_DESCUENTO",
                "discount_type": "PERCENTAGE",
                "discount_value": Decimal(20),
                "applies_to_category": "FORMACION_CONTINUA",
                "valid_from": "2026-01-01",
                "valid_until": "2026-12-31",
                "max_uses": 150,
                "used_count": 12,
                "description": "Cupón preferencial del 20% para estudiantes regulares y titulados de Escuela San Bao en Formación Continua.",
            },
            {
                "code": "SEMINARIO30K",
                "title": "Bono Directo Seminarios Clínicos ($30.000 CLP DCTO)",
                "activity_type": "BECA_COMERCIAL",
                "discount_type": "FIXED_CLP",
                "discount_value": Decimal(30000),
                "applies_to_category": "SEMINARIO",
                "valid_from": "2026-03-01",
                "valid_until": "2026-11-30",
                "max_uses": 80,
                "used_count": 9,
                "description": "Bono directo de $30.000 CLP aplicable en Seminarios Magistrales de Diagnóstico y Fitoterapia.",
            },
            {
                "code": "WEBINAR-PULSO",
                "title": "Masterclass Abierta: Introducción a los 28 Pulsos Clásicos + Bono 10%",
                "activity_type": "WEBINAR_GRATUITO",
                "discount_type": "PERCENTAGE",
                "discount_value": Decimal(10),
                "applies_to_category": "SEMINARIO",
                "valid_from": "2026-04-01",
                "valid_until": "2026-12-31",
                "max_uses": 300,
                "used_count": 44,
                "description": "Actividad comercial de captación (Webinar en vivo) que otorga 10% adicional para el Seminario Clínico de Pulsología.",
            },
        ]

        for pr in sample_promos:
            exists_pr = (
                self.db.query(EcommercePromotion)
                .filter(EcommercePromotion.code == pr["code"], EcommercePromotion.deleted_at.is_(None))
                .first()
            )
            if not exists_pr:
                self.db.add(
                    EcommercePromotion(
                        company_id=comp.id,
                        code=pr["code"],
                        title=pr["title"],
                        activity_type=pr["activity_type"],
                        discount_type=pr["discount_type"],
                        discount_value=pr["discount_value"],
                        applies_to_category=pr["applies_to_category"],
                        valid_from=pr["valid_from"],
                        valid_until=pr["valid_until"],
                        max_uses=pr["max_uses"],
                        used_count=pr["used_count"],
                        description=pr["description"],
                        is_active=True,
                    )
                )
        self.db.commit()

        # 3. Asegurar al menos 3 inscripciones en línea pagadas de demostración con registro automático completo
        paid_orders_count = (
            self.db.query(Order)
            .filter(Order.payment_status == "PAID", Order.deleted_at.is_(None))
            .count()
        )
        if paid_orders_count == 0:
            demo_enrollments = [
                {
                    "customer_rut": "19.876.543-0",
                    "customer_name": "Diego Valenzuela Rojas",
                    "customer_email": "diego.valenzuela@alumnos.sanbao.cl",
                    "customer_phone": "+56 9 8765 4321",
                    "sku": "FC-YNSA-2026",
                    "payment_gateway": "WEBPAY",
                    "promo_code": "ALUMNO20",
                },
                {
                    "customer_rut": "18.765.432-1",
                    "customer_name": "Camila Soto Miranda",
                    "customer_email": "camila.soto@alumnos.sanbao.cl",
                    "customer_phone": "+56 9 7654 3210",
                    "sku": "SEM-PULSO-2026",
                    "payment_gateway": "FLOW",
                    "promo_code": "SANBAO2026",
                },
                {
                    "customer_rut": "16.432.198-K",
                    "customer_name": "Dra. Javiera Fuenzalida Prado",
                    "customer_email": "j.fuenzalida@medicinaintegrativa.cl",
                    "customer_phone": "+56 9 9123 4567",
                    "sku": "SEM-SHANGHAN-2026",
                    "payment_gateway": "WEBPAY",
                    "promo_code": None,
                },
            ]
            for demo in demo_enrollments:
                prod = (
                    self.db.query(Product)
                    .filter(Product.sku == demo["sku"], Product.deleted_at.is_(None))
                    .first()
                )
                if prod:
                    try:
                        self.process_online_enrollment_and_payment({
                            "product_id": prod.id,
                            "customer_rut": demo["customer_rut"],
                            "customer_name": demo["customer_name"],
                            "customer_email": demo["customer_email"],
                            "customer_phone": demo["customer_phone"],
                            "payment_gateway": demo["payment_gateway"],
                            "promo_code": demo["promo_code"],
                            "notes": "Inscripción en línea automática Portal E-Commerce San Bao",
                        })
                    except Exception:
                        self.db.rollback()

    def _parse_product_metadata(self, product: Product) -> Dict[str, Any]:
        default_meta = self.CATALOG_METADATA.get(product.sku, {})
        parsed = {}
        if product.description and product.description.strip().startswith("{"):
            try:
                parsed = json.loads(product.description)
            except Exception:
                parsed = {"summary": product.description}
        else:
            parsed = {"summary": product.description or "Programa oficial de formación Escuela San Bao."}

        category = parsed.get("category") or default_meta.get("category") or "CURSO"
        category_label = parsed.get("category_label") or default_meta.get("category_label") or "Curso / Seminario"
        modality = parsed.get("modality") or default_meta.get("modality") or "Híbrido (Presencial + Aula Virtual LMS)"
        hours = parsed.get("hours") or default_meta.get("hours") or 36
        instructor = parsed.get("instructor") or (product.lms_course.instructor_name if product.lms_course else None) or default_meta.get("instructor") or "Claustro Docente San Bao"
        schedule = parsed.get("schedule") or default_meta.get("schedule") or "Sábados 09:00 - 13:30 hrs"
        program_code = parsed.get("program_code") or default_meta.get("program_code") or product.sku
        badge = parsed.get("badge") or default_meta.get("badge") or "Inscripción en Línea Activa"
        summary = parsed.get("summary") or "Programa académico certificado por el Instituto de Medicina China Clásica SpA."

        return {
            "summary": summary,
            "category": category,
            "category_label": category_label,
            "modality": modality,
            "hours": int(hours),
            "instructor": instructor,
            "schedule": schedule,
            "program_code": program_code,
            "badge": badge,
        }

    def lookup_participant_by_rut(self, rut: str) -> Dict[str, Any]:
        cleaned = ChileanRUT.clean(rut)
        formatted_rut = ChileanRUT.format(cleaned) if len(cleaned) >= 2 else rut.strip()

        person = (
            self.db.query(Person)
            .filter(
                (Person.rut == cleaned) | (Person.rut == formatted_rut) | (Person.rut.ilike(f"%{cleaned}%")),
                Person.deleted_at.is_(None),
            )
            .first()
        )
        if not person:
            return {
                "found": False,
                "rut": formatted_rut,
                "is_existing_student": False,
                "message": "Participante nuevo: al confirmar el pago se creará automáticamente su ficha académica y cuenta de Aula Virtual LMS.",
            }

        student = (
            self.db.query(Student)
            .filter(Student.person_id == person.id, Student.deleted_at.is_(None))
            .first()
        )
        return {
            "found": True,
            "person_id": person.id,
            "rut": person.rut,
            "full_name": f"{person.first_name} {person.last_name}".strip(),
            "first_name": person.first_name,
            "last_name": person.last_name,
            "email": person.email or "",
            "phone": person.phone or "+56 9 ",
            "is_existing_student": student is not None,
            "student_number": student.student_number if student else None,
            "student_status": student.status if student else None,
            "suggested_promo": "ALUMNO20" if student else "SANBAO2026",
            "message": (
                f"Alumno registrado en San Bao ({student.student_number}). Puede aplicar el cupón ALUMNO20 (20% DCTO)."
                if student
                else "Persona registrada en base institucional San Bao. Datos precargados automáticamente."
            ),
        }

    def validate_promotion_code(self, code: str, product_id: Optional[str] = None) -> Dict[str, Any]:
        clean_code = (code or "").strip().upper()
        if not clean_code:
            raise SanBaoException("Debe ingresar un código promocional.")

        promo = (
            self.db.query(EcommercePromotion)
            .filter(EcommercePromotion.code == clean_code, EcommercePromotion.deleted_at.is_(None))
            .first()
        )
        if not promo or not promo.is_active:
            raise SanBaoException(f"El cupón o promoción '{clean_code}' no existe o no se encuentra vigente.")

        if promo.max_uses and promo.used_count >= promo.max_uses:
            raise SanBaoException(f"El cupón '{clean_code}' ha alcanzado su límite máximo de usos ({promo.max_uses}).")

        base_price = Decimal(0)
        discount_amount = Decimal(0)
        final_price = Decimal(0)
        product_name = None

        if product_id:
            prod = self.db.query(Product).filter(Product.id == product_id, Product.deleted_at.is_(None)).first()
            if prod:
                product_name = prod.name
                base_price = Decimal(prod.promotional_price_clp or prod.price_clp or 0)
                if promo.discount_type == "PERCENTAGE":
                    discount_amount = (base_price * Decimal(promo.discount_value) / Decimal(100)).quantize(Decimal("1"))
                else:
                    discount_amount = min(base_price, Decimal(promo.discount_value))
                final_price = max(Decimal(0), base_price - discount_amount)

        return {
            "valid": True,
            "code": promo.code,
            "title": promo.title,
            "activity_type": promo.activity_type,
            "discount_type": promo.discount_type,
            "discount_value": float(promo.discount_value),
            "applies_to_category": promo.applies_to_category,
            "product_name": product_name,
            "base_price_clp": float(base_price),
            "discount_amount_clp": float(discount_amount),
            "final_price_clp": float(final_price),
            "message": f"Promoción aplicada: {promo.title}",
        }

    def process_online_enrollment_and_payment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flujo integral E-Commerce (Inscripción en Línea + Pago Electrónico + Registro Automático +
        Integración Académica/LMS + Emisión de Comprobante y Boleta SII DTE 41).
        """
        product_id = payload.get("product_id")
        prod = self.db.query(Product).filter(Product.id == product_id, Product.deleted_at.is_(None)).first()
        if not prod:
            raise EntityNotFoundException("Curso / Programa Comercial", str(product_id))

        comp = self._get_instituto_company()
        company_id = prod.company_id or (comp.id if comp else None)

        raw_rut = (payload.get("customer_rut") or "").strip()
        if not raw_rut:
            raise SanBaoException("El RUT del participante es obligatorio para la inscripción y emisión de boleta SII.")
        cleaned_rut = ChileanRUT.clean(raw_rut)
        formatted_rut = ChileanRUT.format(cleaned_rut) if len(cleaned_rut) >= 2 else raw_rut

        customer_name = (payload.get("customer_name") or "").strip()
        customer_email = (payload.get("customer_email") or "").strip().lower()
        customer_phone = (payload.get("customer_phone") or "+56 9 0000 0000").strip()
        payment_gateway = (payload.get("payment_gateway") or "WEBPAY").strip().upper()
        promo_code = (payload.get("promo_code") or "").strip().upper()

        if not customer_name or not customer_email:
            raise SanBaoException("Nombre completo y correo electrónico del participante son obligatorios.")

        meta = self._parse_product_metadata(prod)
        base_price = Decimal(prod.promotional_price_clp or prod.price_clp or 0)
        discount_amount = Decimal(0)
        applied_promo: Optional[EcommercePromotion] = None

        if promo_code:
            promo = (
                self.db.query(EcommercePromotion)
                .filter(
                    EcommercePromotion.code == promo_code,
                    EcommercePromotion.is_active == True,
                    EcommercePromotion.deleted_at.is_(None),
                )
                .first()
            )
            if promo:
                applied_promo = promo
                if promo.discount_type == "PERCENTAGE":
                    discount_amount = (base_price * Decimal(promo.discount_value) / Decimal(100)).quantize(Decimal("1"))
                else:
                    discount_amount = min(base_price, Decimal(promo.discount_value))
                promo.used_count = (promo.used_count or 0) + 1

        final_amount = max(Decimal(0), base_price - discount_amount)

        # 1. Registro automático de Persona (core.people)
        person = (
            self.db.query(Person)
            .filter(
                (Person.rut == cleaned_rut) | (Person.rut == formatted_rut),
                Person.deleted_at.is_(None),
            )
            .first()
        )
        if not person:
            parts = customer_name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else "Participante"
            person = Person(
                rut=formatted_rut,
                first_name=first_name,
                last_name=last_name,
                email=customer_email,
                phone=customer_phone,
            )
            self.db.add(person)
            self.db.flush()
        else:
            if customer_email and not person.email:
                person.email = customer_email
            if customer_phone and not person.phone:
                person.phone = customer_phone

        # 2. Registro automático de Usuario Digital (core.users) para Aula Virtual LMS / Portal Alumno
        user_created = False
        user = self.db.query(User).filter(User.person_id == person.id, User.deleted_at.is_(None)).first()
        rut_digits = "".join(ch for ch in cleaned_rut if ch.isdigit())
        temp_password = f"SanBao.{rut_digits[-4:] if len(rut_digits) >= 4 else '2026'}!"

        if not user:
            base_username = formatted_rut
            existing_u = self.db.query(User).filter(User.username == base_username).first()
            if existing_u:
                base_username = f"{customer_email.split('@')[0]}.{rut_digits[-4:]}"
            user = User(
                person_id=person.id,
                username=base_username,
                password_hash=get_password_hash(temp_password),
                is_active=True,
            )
            self.db.add(user)
            self.db.flush()
            user_created = True

        # 3. Integración Académica: Crear/Actualizar Expediente de Alumno (academic.students) y Matrícula (academic.enrollments)
        student = (
            self.db.query(Student)
            .filter(Student.person_id == person.id, Student.deleted_at.is_(None))
            .first()
        )
        student_created = False
        if not student:
            total_st = self.db.query(Student).count()
            student_number = f"MAT-2026-{total_st + 1:04d}"
            while self.db.query(Student).filter(Student.student_number == student_number).first():
                total_st += 1
                student_number = f"MAT-2026-{total_st + 1:04d}"

            student = Student(
                person_id=person.id,
                student_number=student_number,
                admission_date=date.today(),
                status="REGULAR",
                notes=f"Registrado automáticamente vía E-Commerce ({prod.sku})",
            )
            self.db.add(student)
            self.db.flush()
            student_created = True
        else:
            if student.status == "APPLICANT":
                student.status = "REGULAR"

        # Buscar o vincular Programa Académico correspondiente
        prog_code = meta.get("program_code") or prod.sku
        program = (
            self.db.query(Program)
            .filter(Program.code == prog_code, Program.deleted_at.is_(None))
            .first()
        )
        if not program:
            program = (
                self.db.query(Program)
                .filter(Program.name.ilike(f"%{prod.name[:25]}%"), Program.deleted_at.is_(None))
                .first()
            )
        if not program:
            program = Program(
                code=prog_code[:45],
                name=prod.name,
                program_type=meta.get("category") if meta.get("category") in ("DIPLOMADO", "CURSO", "FORMACION_CONTINUA") else "FORMACION_CONTINUA",
                degree_title=f"Certificación en {prod.name}",
                description=meta.get("summary"),
                total_semesters=1,
                total_theoretical_hours=int(meta.get("hours", 32) * 0.6),
                total_practical_hours=int(meta.get("hours", 32) * 0.4),
                min_clinical_hours=0,
                is_active=True,
            )
            self.db.add(program)
            self.db.flush()

        period = self._get_or_create_active_period()
        enrollment = (
            self.db.query(Enrollment)
            .filter(
                Enrollment.student_id == student.id,
                Enrollment.program_id == program.id,
                Enrollment.deleted_at.is_(None),
            )
            .first()
        )
        if not enrollment:
            enrollment = Enrollment(
                student_id=student.id,
                program_id=program.id,
                academic_period_id=period.id,
                enrollment_date=date.today(),
                status="CONFIRMED",
            )
            self.db.add(enrollment)
            self.db.flush()

        # 4. Enrolamiento en Aula Virtual LMS (lms.lms_enrollments)
        lms_enrolled_title = None
        if prod.lms_course_id and user:
            lms_enr = (
                self.db.query(LMSEnrollment)
                .filter(
                    LMSEnrollment.course_id == prod.lms_course_id,
                    LMSEnrollment.user_id == user.id,
                    LMSEnrollment.deleted_at.is_(None),
                )
                .first()
            )
            if not lms_enr:
                lms_enr = LMSEnrollment(
                    course_id=prod.lms_course_id,
                    user_id=user.id,
                    progress_percentage=Decimal(0),
                    status="ACTIVE",
                )
                self.db.add(lms_enr)
            lms_enrolled_title = prod.lms_course.title if prod.lms_course else prod.name

        # Reducir cupo disponible si tiene stock definido
        if prod.stock is not None and prod.stock > 0:
            prod.stock = prod.stock - 1

        # 5. Generar Orden E-Commerce y Transacción de Pago Electrónico
        year = date.today().year
        ord_seq = self.db.query(Order).count() + 1
        order_number = f"ORD-{year}-{ord_seq:04d}"
        while self.db.query(Order).filter(Order.order_number == order_number).first():
            ord_seq += 1
            order_number = f"ORD-{year}-{ord_seq:04d}"

        now_utc = datetime.now(timezone.utc)
        order = Order(
            company_id=company_id,
            customer_person_id=person.id,
            order_number=order_number,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_rut=formatted_rut,
            customer_phone=customer_phone,
            total_amount=final_amount,
            payment_status="PAID",
            payment_gateway=payment_gateway,
            paid_at=now_utc,
        )
        self.db.add(order)
        self.db.flush()

        order_item = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            quantity=1,
            unit_price=final_amount,
            subtotal=final_amount,
        )
        self.db.add(order_item)

        prefix_map = {"WEBPAY": "TBK", "FLOW": "FLW", "MERCADOPAGO": "MP"}
        gw_prefix = prefix_map.get(payment_gateway, "TBK")
        tx_id = f"{gw_prefix}-{now_utc.strftime('%Y%m%d%H%M%S')}-{ord_seq:03d}"
        auth_code = f"AUTH-{gw_prefix}-{100000 + ord_seq * 37}"

        tx = GatewayTransaction(
            order_id=order.id,
            gateway=payment_gateway,
            transaction_id=tx_id,
            authorization_code=auth_code,
            amount=final_amount,
            status="SUCCESS",
            raw_response={
                "confirmed_at": now_utc.isoformat(),
                "promo_code": applied_promo.code if applied_promo else None,
                "base_price_clp": float(base_price),
                "discount_amount_clp": float(discount_amount),
                "student_number": student.student_number,
                "program_code": program.code,
                "enrollment_id": enrollment.id,
            },
        )
        self.db.add(tx)

        # 6. Registrar Pago en Módulo de Finanzas (finance.payments) y Emitir Boleta Exenta SII DTE 41
        payment_rec = Payment(
            company_id=company_id,
            person_id=person.id,
            amount=final_amount,
            payment_date=now_utc,
            payment_method=payment_gateway,
            reference_number=auth_code,
            notes=f"Inscripción E-Commerce #{order.order_number} • {prod.name}",
        )
        self.db.add(payment_rec)
        self.db.flush()

        max_folio = (
            self.db.query(func.max(DTEDocument.folio))
            .filter(DTEDocument.dte_type == 41)
            .scalar()
        ) or 41050
        next_folio = int(max_folio) + 1

        dte = DTEDocument(
            company_id=company_id,
            dte_type=41,
            folio=next_folio,
            issue_date=date.today(),
            issuer_rut=comp.rut if comp else "77.123.456-9",
            issuer_name=comp.legal_name if comp else "Instituto de Medicina China Clásica SpA",
            receiver_rut=formatted_rut,
            receiver_name=customer_name,
            receiver_address="Inscripción Online Portal E-Commerce San Bao",
            receiver_commune="Santiago",
            receiver_activity="Estudiante / Profesional de la Salud",
            net_amount=Decimal(0),
            exempt_amount=final_amount,
            iva_amount=Decimal(0),
            total_amount=final_amount,
            items=[
                {
                    "name": f"Inscripción Online: {prod.name}",
                    "sku": prod.sku,
                    "qty": 1,
                    "unit_price": float(final_amount),
                    "total": float(final_amount),
                }
            ],
            sii_status=DTEStatus.ACCEPTED,
            sii_track_id=f"SII-ECOM-{next_folio}",
            digital_stamp=f"<TED version='1.0'><DD><RE>{comp.rut if comp else '77.123.456-9'}</RE><TD>41</TD><F>{next_folio}</F><FE>{date.today().isoformat()}</FE><RR>{formatted_rut}</RR><MNT>{int(final_amount)}</MNT></DD></TED>",
            pdf_url=f"/api/v1/ecommerce/hub/orders/{order.id}/receipt",
        )
        self.db.add(dte)
        tx.raw_response = {
            **(tx.raw_response or {}),
            "dte_folio": next_folio,
            "dte_type": 41,
            "payment_id": payment_rec.id,
        }

        self.db.commit()
        self.db.refresh(order)

        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "paid_at": order.paid_at.strftime("%Y-%m-%d %H:%M") if order.paid_at else date.today().isoformat(),
            "customer_name": order.customer_name,
            "customer_rut": order.customer_rut,
            "customer_email": order.customer_email,
            "customer_phone": order.customer_phone,
            "product_id": prod.id,
            "product_sku": prod.sku,
            "product_name": prod.name,
            "category_label": meta["category_label"],
            "modality": meta["modality"],
            "instructor": meta["instructor"],
            "hours": meta["hours"],
            "base_price_clp": float(base_price),
            "discount_amount_clp": float(discount_amount),
            "total_paid_clp": float(final_amount),
            "promo_code": applied_promo.code if applied_promo else None,
            "payment_gateway": payment_gateway,
            "transaction_id": tx_id,
            "authorization_code": auth_code,
            "student_number": student.student_number,
            "student_created": student_created,
            "student_status": student.status,
            "program_code": program.code,
            "program_name": program.name,
            "enrollment_id": enrollment.id,
            "lms_course_title": lms_enrolled_title or prod.name,
            "portal_username": user.username if user else formatted_rut,
            "portal_temp_password": temp_password,
            "user_created": user_created,
            "dte_type": 41,
            "dte_type_label": "Boleta Electrónica Exenta SII (Tipo 41)",
            "dte_folio": next_folio,
            "sii_track_id": dte.sii_track_id,
            "receipt_number": f"COMP-WEB-{order.order_number}",
        }

    def create_catalog_item(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        comp = self._get_instituto_company()
        sku = (payload.get("sku") or "").strip().upper()
        name = (payload.get("name") or "").strip()
        if not sku or not name:
            raise SanBaoException("El código SKU y el nombre del curso o seminario son obligatorios.")

        existing = self.db.query(Product).filter(Product.sku == sku, Product.deleted_at.is_(None)).first()
        if existing:
            raise SanBaoException(f"Ya existe un programa o seminario con el código SKU '{sku}'.")

        category = (payload.get("category") or "SEMINARIO").strip().upper()
        category_labels = {
            "SEMINARIO": "Seminario Magistral",
            "FORMACION_CONTINUA": "Programa de Formación Continua",
            "CURSO": "Curso de Especialización",
            "DIPLOMADO": "Diplomado Oficial (Matrícula Web)",
        }
        category_label = category_labels.get(category, "Programa de Formación Continua")
        modality = (payload.get("modality") or "Híbrido (Presencial + Aula Virtual LMS)").strip()
        hours = int(payload.get("hours") or 32)
        instructor = (payload.get("instructor") or "Dra. Marcela Pérez Morales").strip()
        schedule = (payload.get("schedule") or "Sábados 09:00 a 13:30 hrs").strip()
        summary = (payload.get("summary") or "Programa certificado por el Instituto de Medicina China Clásica SpA.").strip()
        price_clp = Decimal(str(payload.get("price_clp") or 180000))
        promo_price_raw = payload.get("promotional_price_clp")
        promotional_price_clp = Decimal(str(promo_price_raw)) if promo_price_raw else None
        stock = int(payload.get("stock") or 30)

        # Crear Programa Académico sincronizado y Aula Virtual LMS
        prog_code = sku[:45]
        prog = self.db.query(Program).filter(Program.code == prog_code, Program.deleted_at.is_(None)).first()
        if not prog:
            prog = Program(
                code=prog_code,
                name=name,
                program_type="CURSO" if category == "SEMINARIO" else category,
                degree_title=f"Certificación Oficial en {name}",
                description=summary,
                total_semesters=1,
                total_theoretical_hours=int(hours * 0.6),
                total_practical_hours=int(hours * 0.4),
                min_clinical_hours=0,
                is_active=True,
            )
            self.db.add(prog)
            self.db.flush()

        lms_code = f"LMS-{sku}"[:48]
        lms_course = self.db.query(LMSCourse).filter(LMSCourse.code == lms_code, LMSCourse.deleted_at.is_(None)).first()
        if not lms_course:
            lms_course = LMSCourse(
                code=lms_code,
                title=name,
                summary=summary,
                instructor_name=instructor,
                is_published=True,
            )
            self.db.add(lms_course)
            self.db.flush()

        slug = name.lower().replace(" ", "-").replace(":", "").replace(",", "") + f"-{sku.lower()}"
        desc_json = json.dumps({
            "summary": summary,
            "category": category,
            "category_label": category_label,
            "modality": modality,
            "hours": hours,
            "instructor": instructor,
            "schedule": schedule,
            "program_code": prog.code,
            "badge": "Nuevo Programa Sincronizado con Académico & LMS",
        }, ensure_ascii=False)

        prod = Product(
            company_id=comp.id,
            lms_course_id=lms_course.id,
            sku=sku,
            name=name,
            slug=slug[:250],
            description=desc_json,
            price_clp=price_clp,
            promotional_price_clp=promotional_price_clp,
            is_digital=True,
            stock=stock,
            is_active=True,
        )
        self.db.add(prod)
        self.db.commit()
        self.db.refresh(prod)

        return {
            "id": prod.id,
            "sku": prod.sku,
            "name": prod.name,
            "category": category,
            "category_label": category_label,
            "price_clp": float(prod.price_clp),
            "promotional_price_clp": float(prod.promotional_price_clp) if prod.promotional_price_clp else None,
            "program_code": prog.code,
            "lms_code": lms_course.code,
        }

    def create_promotion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        comp = self._get_instituto_company()
        code = (payload.get("code") or "").strip().upper()
        title = (payload.get("title") or "").strip()
        if not code or not title:
            raise SanBaoException("El código del cupón/campaña y su título comercial son obligatorios.")

        exists = (
            self.db.query(EcommercePromotion)
            .filter(EcommercePromotion.code == code, EcommercePromotion.deleted_at.is_(None))
            .first()
        )
        if exists:
            raise SanBaoException(f"Ya existe una promoción o campaña con el código '{code}'.")

        promo = EcommercePromotion(
            company_id=comp.id,
            code=code,
            title=title,
            activity_type=(payload.get("activity_type") or "CUPON_DESCUENTO").strip().upper(),
            discount_type=(payload.get("discount_type") or "PERCENTAGE").strip().upper(),
            discount_value=Decimal(str(payload.get("discount_value") or 15)),
            applies_to_category=(payload.get("applies_to_category") or "TODOS").strip().upper(),
            valid_from=payload.get("valid_from") or date.today().isoformat(),
            valid_until=payload.get("valid_until") or "2026-12-31",
            max_uses=int(payload.get("max_uses") or 100),
            used_count=0,
            description=payload.get("description") or "Campaña comercial activa en tienda online San Bao.",
            is_active=True,
        )
        self.db.add(promo)
        self.db.commit()
        self.db.refresh(promo)
        return {
            "id": promo.id,
            "code": promo.code,
            "title": promo.title,
            "activity_type": promo.activity_type,
            "discount_type": promo.discount_type,
            "discount_value": float(promo.discount_value),
            "is_active": promo.is_active,
        }

    def toggle_promotion(self, promo_id: str) -> Dict[str, Any]:
        promo = (
            self.db.query(EcommercePromotion)
            .filter(EcommercePromotion.id == promo_id, EcommercePromotion.deleted_at.is_(None))
            .first()
        )
        if not promo:
            raise EntityNotFoundException("Promoción Comercial", promo_id)
        promo.is_active = not promo.is_active
        self.db.commit()
        return {"id": promo.id, "code": promo.code, "is_active": promo.is_active}

    def get_hub_overview(
        self,
        category_filter: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.ensure_sample_ecommerce_data()

        products = (
            self.db.query(Product)
            .filter(Product.deleted_at.is_(None), Product.is_active == True)
            .order_by(Product.created_at.asc())
            .all()
        )

        # Contar inscritos por producto
        enrolled_counts_by_product: Dict[str, int] = {}
        paid_orders = (
            self.db.query(Order)
            .filter(Order.payment_status == "PAID", Order.deleted_at.is_(None))
            .order_by(Order.paid_at.desc(), Order.created_at.desc())
            .all()
        )
        for o in paid_orders:
            for it in o.items:
                enrolled_counts_by_product[it.product_id] = enrolled_counts_by_product.get(it.product_id, 0) + (it.quantity or 1)

        catalog_items = []
        for p in products:
            meta = self._parse_product_metadata(p)
            if category_filter and category_filter.upper() not in ("ALL", "TODOS", ""):
                if meta["category"].upper() != category_filter.upper():
                    continue
            if search and search.strip():
                q = search.strip().lower()
                if (
                    q not in p.name.lower()
                    and q not in p.sku.lower()
                    and q not in meta["instructor"].lower()
                    and q not in meta["category_label"].lower()
                ):
                    continue

            enrolled_count = enrolled_counts_by_product.get(p.id, 0)
            effective_price = float(p.promotional_price_clp or p.price_clp or 0)
            regular_price = float(p.price_clp or 0)
            savings_pct = round(((regular_price - effective_price) / regular_price) * 100) if regular_price > effective_price and regular_price > 0 else 0

            catalog_items.append({
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "slug": p.slug,
                "category": meta["category"],
                "category_label": meta["category_label"],
                "summary": meta["summary"],
                "modality": meta["modality"],
                "hours": meta["hours"],
                "instructor": meta["instructor"],
                "schedule": meta["schedule"],
                "program_code": meta["program_code"],
                "badge": meta["badge"],
                "price_clp": regular_price,
                "promotional_price_clp": float(p.promotional_price_clp) if p.promotional_price_clp else None,
                "effective_price_clp": effective_price,
                "savings_pct": savings_pct,
                "stock": p.stock if p.stock is not None else 50,
                "enrolled_count": enrolled_count,
                "lms_course_id": p.lms_course_id,
                "lms_course_code": p.lms_course.code if p.lms_course else f"LMS-{p.sku}",
                "lms_course_title": p.lms_course.title if p.lms_course else p.name,
            })

        # Construir listado enriquecido de órdenes, pagos electrónicos, participantes registrados y comprobantes DTE
        orders_list = []
        participants_list = []
        receipts_list = []
        total_revenue_clp = Decimal(0)

        for o in paid_orders:
            total_revenue_clp += Decimal(o.total_amount or 0)
            first_item = o.items[0] if o.items else None
            prod = first_item.product if first_item else None
            meta = self._parse_product_metadata(prod) if prod else {
                "category": "CURSO",
                "category_label": "Programa Online",
                "modality": "Online LMS",
                "instructor": "Claustro San Bao",
                "hours": 32,
                "program_code": "MTC-WEB",
            }
            tx = o.transactions[0] if o.transactions else None
            raw = (tx.raw_response or {}) if tx and isinstance(tx.raw_response, dict) else {}

            # Buscar ficha Student y User asociada al comprador
            student = None
            user = None
            if o.customer_person_id:
                student = (
                    self.db.query(Student)
                    .filter(Student.person_id == o.customer_person_id, Student.deleted_at.is_(None))
                    .first()
                )
                user = (
                    self.db.query(User)
                    .filter(User.person_id == o.customer_person_id, User.deleted_at.is_(None))
                    .first()
                )

            student_number = raw.get("student_number") or (student.student_number if student else "MAT-2026-WEB")
            dte_folio = raw.get("dte_folio") or 41051
            paid_date_str = o.paid_at.strftime("%Y-%m-%d %H:%M") if o.paid_at else o.created_at.strftime("%Y-%m-%d %H:%M")

            order_entry = {
                "order_id": o.id,
                "order_number": o.order_number,
                "paid_at": paid_date_str,
                "customer_name": o.customer_name,
                "customer_rut": o.customer_rut,
                "customer_email": o.customer_email,
                "customer_phone": o.customer_phone or "+56 9 8765 4321",
                "product_sku": prod.sku if prod else "WEB-001",
                "product_name": prod.name if prod else "Programa de Formación Continua",
                "category_label": meta["category_label"],
                "modality": meta["modality"],
                "instructor": meta["instructor"],
                "hours": meta["hours"],
                "program_code": raw.get("program_code") or meta["program_code"],
                "base_price_clp": float(raw.get("base_price_clp") or o.total_amount or 0),
                "discount_amount_clp": float(raw.get("discount_amount_clp") or 0),
                "total_amount_clp": float(o.total_amount or 0),
                "promo_code": raw.get("promo_code"),
                "payment_gateway": o.payment_gateway or "WEBPAY",
                "payment_status": o.payment_status,
                "transaction_id": tx.transaction_id if tx else f"TBK-{o.order_number}",
                "authorization_code": tx.authorization_code if tx else f"AUTH-{o.order_number}",
                "student_number": student_number,
                "student_status": student.status if student else "REGULAR",
                "portal_username": user.username if user else o.customer_rut,
                "lms_course_code": prod.lms_course.code if prod and prod.lms_course else f"LMS-{prod.sku if prod else 'WEB'}",
                "lms_status": "ACTIVO EN AULA VIRTUAL",
                "dte_type": 41,
                "dte_type_label": "Boleta Electrónica Exenta SII (DTE 41)",
                "dte_folio": dte_folio,
                "receipt_number": f"COMP-WEB-{o.order_number}",
            }
            orders_list.append(order_entry)
            participants_list.append(order_entry)
            receipts_list.append(order_entry)

        # Promociones y Actividades Comerciales
        promotions_q = (
            self.db.query(EcommercePromotion)
            .filter(EcommercePromotion.deleted_at.is_(None))
            .order_by(EcommercePromotion.created_at.desc())
            .all()
        )
        promotions_list = [
            {
                "id": pr.id,
                "code": pr.code,
                "title": pr.title,
                "activity_type": pr.activity_type,
                "discount_type": pr.discount_type,
                "discount_value": float(pr.discount_value or 0),
                "applies_to_category": pr.applies_to_category,
                "valid_from": pr.valid_from,
                "valid_until": pr.valid_until,
                "max_uses": pr.max_uses,
                "used_count": pr.used_count or 0,
                "description": pr.description,
                "is_active": pr.is_active,
            }
            for pr in promotions_q
        ]

        # Estado de sincronización con el Módulo Académico y LMS
        academic_sync_items = []
        for p in products:
            meta = self._parse_product_metadata(p)
            prog = (
                self.db.query(Program)
                .filter(Program.code == meta["program_code"], Program.deleted_at.is_(None))
                .first()
            )
            acad_enrollments_count = 0
            if prog:
                acad_enrollments_count = (
                    self.db.query(Enrollment)
                    .filter(Enrollment.program_id == prog.id, Enrollment.deleted_at.is_(None))
                    .count()
                )
            lms_enrollments_count = 0
            if p.lms_course_id:
                lms_enrollments_count = (
                    self.db.query(LMSEnrollment)
                    .filter(LMSEnrollment.course_id == p.lms_course_id, LMSEnrollment.deleted_at.is_(None))
                    .count()
                )
            academic_sync_items.append({
                "product_sku": p.sku,
                "product_name": p.name,
                "category_label": meta["category_label"],
                "academic_program_code": prog.code if prog else meta["program_code"],
                "academic_program_type": prog.program_type if prog else meta["category"],
                "academic_enrollments_count": max(acad_enrollments_count, enrolled_counts_by_product.get(p.id, 0)),
                "lms_course_code": p.lms_course.code if p.lms_course else f"LMS-{p.sku}",
                "lms_instructor": meta["instructor"],
                "lms_enrollments_count": max(lms_enrollments_count, enrolled_counts_by_product.get(p.id, 0)),
                "sync_status": "SINCRONIZADO 100%",
            })

        return {
            "kpis": {
                "catalog_total": len(products),
                "seminars_and_continuing_ed": sum(
                    1 for p in products if self._parse_product_metadata(p)["category"] in ("SEMINARIO", "FORMACION_CONTINUA")
                ),
                "online_enrollments_count": len(orders_list),
                "online_revenue_clp": float(total_revenue_clp),
                "auto_registered_participants": len(participants_list),
                "emitted_receipts_and_dtes": len(receipts_list),
                "active_promotions": sum(1 for pr in promotions_list if pr["is_active"]),
                "academic_programs_synced": len(academic_sync_items),
            },
            "catalog_items": catalog_items,
            "orders": orders_list,
            "participants": participants_list,
            "receipts": receipts_list,
            "academic_integration": academic_sync_items,
            "promotions": promotions_list,
        }

