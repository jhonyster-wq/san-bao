import logging
from sqlalchemy.orm import Session
from app.core.database import Base, engine, SessionLocal
from app.core.security import get_password_hash
from app.modules.institutional.models.company import Company
from app.modules.institutional.models.campus import Campus, Room
from app.modules.institutional.models.person import Person
from app.modules.institutional.models.user import User
from app.modules.institutional.services.rbac_service import RBACService
from app.shared.validators.rut import ChileanRUT
import app.modules.academic.models
import app.modules.clinical.models
import app.modules.finance.models
import app.modules.lms.models
import app.modules.ecommerce.models
import app.modules.hr.models
import app.modules.integrations.models

logger = logging.getLogger(__name__)


def _migrate_sqlite_columns(target_engine) -> None:
    """Asegura que tablas existentes en SQLite cuenten con columnas añadidas dinámicamente."""
    if not target_engine.url.drivername.startswith("sqlite"):
        return
    with target_engine.begin() as conn:
        try:
            # Inspeccionar columnas actuales de clinical_shift_schedules
            result = conn.exec_driver_sql("PRAGMA table_info(clinical_shift_schedules)").fetchall()
            existing_cols = {row[1] for row in result}
            columns_to_add = [
                ("service_type", "VARCHAR(50) DEFAULT 'ACUPUNTURA'"),
                ("shift_period", "VARCHAR(30) DEFAULT 'AM'"),
                ("day_schedule", "VARCHAR(50) DEFAULT 'LUNES_A_SABADO'"),
                ("closure_type", "VARCHAR(50) DEFAULT 'SINGLE_DATE'"),
                ("closure_start_date", "DATE"),
                ("closure_end_date", "DATE"),
                ("closure_dates_text", "VARCHAR(255)"),
                ("closure_reason", "VARCHAR(255)"),
                ("substitute_practitioner_id", "VARCHAR(36)"),
                ("substitute_active", "BOOLEAN DEFAULT 0"),
            ]
            for col_name, col_def in columns_to_add:
                if col_name not in existing_cols:
                    conn.exec_driver_sql(f"ALTER TABLE clinical_shift_schedules ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Columna {col_name} agregada a clinical_shift_schedules.")

            # Inspeccionar columnas de clinical_session_prices (soporte de packs y tipos de servicio)
            res_prices = conn.exec_driver_sql("PRAGMA table_info(clinical_session_prices)").fetchall()
            existing_price_cols = {row[1] for row in res_prices}
            price_cols = [
                ("session_count", "INTEGER DEFAULT 1"),
                ("service_type", "VARCHAR(50) DEFAULT 'ACUPUNTURA'"),
            ]
            for col_name, col_def in price_cols:
                if col_name not in existing_price_cols:
                    conn.exec_driver_sql(f"ALTER TABLE clinical_session_prices ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Columna {col_name} agregada a clinical_session_prices.")
            # Inspeccionar columnas de clinical_supplies (soporte de reposición y seguimiento de stock)
            res_supplies = conn.exec_driver_sql("PRAGMA table_info(clinical_supplies)").fetchall()
            existing_supply_cols = {row[1] for row in res_supplies}
            supply_cols = [
                ("current_stock", "INTEGER DEFAULT 100"),
                ("last_restock_date", "DATE"),
                ("last_restock_quantity", "INTEGER"),
            ]
            for col_name, col_def in supply_cols:
                if col_name not in existing_supply_cols:
                    conn.exec_driver_sql(f"ALTER TABLE clinical_supplies ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Columna {col_name} agregada a clinical_supplies.")
            # Inspeccionar columnas de supply_restock_records (soporte para egreso/sacar insumos y motivo)
            res_restocks = conn.exec_driver_sql("PRAGMA table_info(supply_restock_records)").fetchall()
            existing_restock_cols = {row[1] for row in res_restocks}
            restock_cols = [
                ("movement_type", "VARCHAR(30) DEFAULT 'INGRESO'"),
                ("reason", "VARCHAR(100)"),
            ]
            for col_name, col_def in restock_cols:
                if col_name not in existing_restock_cols:
                    conn.exec_driver_sql(f"ALTER TABLE supply_restock_records ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Columna {col_name} agregada a supply_restock_records.")

            # Inspeccionar columnas de programs (soporte para diplomados, cursos y formación continua)
            res_programs = conn.exec_driver_sql("PRAGMA table_info(programs)").fetchall()
            existing_prog_cols = {row[1] for row in res_programs}
            if "program_type" not in existing_prog_cols:
                conn.exec_driver_sql("ALTER TABLE programs ADD COLUMN program_type VARCHAR(50) DEFAULT 'DIPLOMADO'")
                logger.info("Columna program_type agregada a programs.")

            # Inspeccionar columnas de courses (soporte de asignación a programa y docente titular)
            res_courses = conn.exec_driver_sql("PRAGMA table_info(courses)").fetchall()
            existing_course_cols = {row[1] for row in res_courses}
            course_cols = [
                ("program_id", "VARCHAR(36)"),
                ("teacher_id", "VARCHAR(36)"),
            ]
            for col_name, col_def in course_cols:
                if col_name not in existing_course_cols:
                    conn.exec_driver_sql(f"ALTER TABLE courses ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Columna {col_name} agregada a courses.")

            # Inspeccionar columnas de students (soporte para congelamiento, activación y práctica clínica)
            res_students = conn.exec_driver_sql("PRAGMA table_info(students)").fetchall()
            existing_student_cols = {row[1] for row in res_students}
            student_cols = [
                ("freeze_reason", "VARCHAR(255)"),
                ("freeze_date", "DATE"),
                ("clinical_practice_approved", "BOOLEAN DEFAULT 0"),
                ("clinical_practice_approval_date", "DATE"),
                ("clinical_practice_notes", "TEXT"),
            ]
            for col_name, col_def in student_cols:
                if col_name not in existing_student_cols:
                    conn.exec_driver_sql(f"ALTER TABLE students ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Columna {col_name} agregada a students.")

            # Inspeccionar columnas de clinical_shift_schedules (soporte de alumno en práctica clínica asignado al turno)
            res_shifts = conn.exec_driver_sql("PRAGMA table_info(clinical_shift_schedules)").fetchall()
            existing_shift_cols = {row[1] for row in res_shifts}
            shift_cols = [
                ("intern_student_id", "VARCHAR(36)"),
                ("intern_student_name", "VARCHAR(200)"),
            ]
            for col_name, col_def in shift_cols:
                if col_name not in existing_shift_cols:
                    conn.exec_driver_sql(f"ALTER TABLE clinical_shift_schedules ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Columna {col_name} agregada a clinical_shift_schedules.")

            # Inspeccionar columnas de attendances (soporte para registro de asistencia por curso cátedra)
            res_att = conn.exec_driver_sql("PRAGMA table_info(attendances)").fetchall()
            existing_att_cols = {row[1] for row in res_att}
            att_cols = [
                ("course_id", "VARCHAR(36)"),
                ("class_number", "INTEGER"),
                ("session_topic", "VARCHAR(255)"),
                ("status", "VARCHAR(20) DEFAULT 'PRESENTE'"),
            ]
            for col_name, col_def in att_cols:
                if col_name not in existing_att_cols:
                    conn.exec_driver_sql(f"ALTER TABLE attendances ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Columna {col_name} agregada a attendances.")

            # Inspeccionar columnas de evaluations (soporte para asociar a curso cátedra)
            res_evals = conn.exec_driver_sql("PRAGMA table_info(evaluations)").fetchall()
            existing_eval_cols = {row[1] for row in res_evals}
            if "course_id" not in existing_eval_cols:
                conn.exec_driver_sql("ALTER TABLE evaluations ADD COLUMN course_id VARCHAR(36)")
                logger.info("Columna course_id agregada a evaluations.")
        except Exception as e:
            logger.debug(f"Aviso en migración SQLite: {e}")


def _ensure_postgres_schemas(target_engine) -> None:
    """Crea automáticamente los 10 esquemas relacionales si el motor es PostgreSQL."""
    if not target_engine.url.drivername.startswith("postgresql"):
        return
    schemas = [
        "core",
        "academic",
        "clinical",
        "finance",
        "hr",
        "ecommerce",
        "lms",
        "integrations",
        "bi",
        "audit",
    ]
    with target_engine.begin() as conn:
        for schema_name in schemas:
            try:
                conn.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            except Exception as e:
                logger.debug(f"Esquema {schema_name} omitido: {e}")


def _ensure_performance_indexes(target_engine) -> None:
    """Crea índices compuestos B-Tree normalizados (3NF/BCNF) en tablas existentes para optimizar consultas."""
    drv = target_engine.url.drivername
    is_sqlite = drv.startswith("sqlite") or drv.startswith("mysql") or drv.startswith("mariadb")
    idx_statements = [
        ("ix_curriculum_courses_curr_sem", "curriculum_courses" if is_sqlite else "academic.curriculum_courses", "(curriculum_id, semester)"),
        ("ix_enrollments_student_status", "enrollments" if is_sqlite else "academic.enrollments", "(student_id, status)"),
        ("ix_cohort_enrollments_cohort_status", "cohort_enrollments" if is_sqlite else "academic.cohort_enrollments", "(cohort_id, status)"),
        ("ix_grades_student_eval", "grades" if is_sqlite else "academic.grades", "(student_id, evaluation_id)"),
        ("ix_attendances_student_course_date", "attendances" if is_sqlite else "academic.attendances", "(student_id, course_id, class_date)"),
        ("ix_clinical_practice_student_status", "clinical_practice_hours" if is_sqlite else "academic.clinical_practice_hours", "(student_id, status)"),
        ("ix_clinical_practice_tutor_date", "clinical_practice_hours" if is_sqlite else "academic.clinical_practice_hours", "(tutor_id, activity_date)"),
        ("ix_appointments_campus_date_status", "appointments" if is_sqlite else "clinical.appointments", "(campus_id, appointment_date, status)"),
        ("ix_appointments_practitioner_date", "appointments" if is_sqlite else "clinical.appointments", "(practitioner_id, appointment_date)"),
        ("ix_shifts_practitioner_date", "clinical_shift_schedules" if is_sqlite else "clinical.clinical_shift_schedules", "(practitioner_id, shift_date)"),
        ("ix_shifts_campus_date_period", "clinical_shift_schedules" if is_sqlite else "clinical.clinical_shift_schedules", "(campus_id, shift_date, shift_period)"),
        ("ix_installments_status_duedate", "installments" if is_sqlite else "finance.installments", "(status, due_date)"),
        ("ix_hr_employees_comp_type_active", "hr_employees" if is_sqlite else "hr.hr_employees", "(company_id, employee_type, is_active)"),
        ("ix_hr_payrolls_comp_period", "hr_payrolls" if is_sqlite else "hr.hr_payrolls", "(company_id, period_year, period_month)"),
        ("ix_dte_company_date", "dte_documents" if is_sqlite else "integrations.dte_documents", "(company_id, issue_date)"),
    ]
    with target_engine.begin() as conn:
        for idx_name, tbl_name, cols_expr in idx_statements:
            try:
                conn.exec_driver_sql(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl_name} {cols_expr}")
            except Exception as e:
                logger.debug(f"Índice {idx_name} omitido: {e}")


def init_db(db: Session) -> None:
    """Inicializa la base de datos con tablas, esquemas, roles y datos institucionales maestros iniciales."""
    _ensure_postgres_schemas(engine)
    # Crear todas las tablas declaradas
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_columns(engine)
    _ensure_performance_indexes(engine)

    rbac_service = RBACService(db)
    rbac_service.seed_default_roles_and_permissions()

    # 1. Crear Sociedades SpA San Bao si no existen
    instituto_rut = "77123456-9"
    clinica_rut = "76987654-5"

    instituto = db.query(Company).filter(Company.rut == instituto_rut).first()
    if not instituto:
        instituto = Company(
            rut=instituto_rut,
            legal_name="Instituto de Medicina China Clásica SpA",
            trade_name="Escuela San Bao",
            tax_activity="Enseñanza superior y capacitación en medicina complementaria y tradicional",
            address="Av. Providencia 1234, Providencia, Santiago",
            email="contacto@medicinachinaclasica.cl",
            phone="+56 2 2345 6789",
            website="https://www.medicinachinaclasica.cl",
            is_active=True,
        )
        db.add(instituto)
        db.commit()
        db.refresh(instituto)
        logger.info("Creada sociedad: Instituto de Medicina China Clásica SpA")

    clinica = db.query(Company).filter(Company.rut == clinica_rut).first()
    if not clinica:
        clinica = Company(
            rut=clinica_rut,
            legal_name="Servicios Clínicos San Bao SpA",
            trade_name="Clínica San Bao",
            tax_activity="Servicios de atención médica, acupuntura y terapias integrativas",
            address="Av. Providencia 1238, Providencia, Santiago",
            email="contacto@clinicasanbao.cl",
            phone="+56 2 2345 6790",
            website="https://www.clinicasanbao.cl",
            is_active=True,
        )
        db.add(clinica)
        db.commit()
        db.refresh(clinica)
        logger.info("Creada sociedad: Servicios Clínicos San Bao SpA")

    # 2. Crear Sede Central y Boxes/Salas
    campus = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
    if not campus:
        campus = Campus(
            code="SEDE-CENTRAL",
            name="Sede Central Providencia",
            address="Av. Providencia 1234-1238",
            city="Santiago",
            is_active=True,
        )
        db.add(campus)
        db.commit()
        db.refresh(campus)

        # Crear salas y boxes clínicos de muestra
        rooms = [
            Room(campus_id=campus.id, code="SALA-101", name="Aula Magna Lao Tsé", room_type="CLASSROOM", capacity=40),
            Room(campus_id=campus.id, code="SALA-102", name="Sala Teórica Huang Di", room_type="CLASSROOM", capacity=25),
            Room(campus_id=campus.id, code="BOX-01", name="Box de Acupuntura Tai Yang", room_type="CLINICAL_BOX", capacity=2),
            Room(campus_id=campus.id, code="BOX-02", name="Box de Acupuntura Shao Yin", room_type="CLINICAL_BOX", capacity=2),
            Room(campus_id=campus.id, code="BOX-PRACTICA", name="Box Prácticas Supervisadas", room_type="CLINICAL_BOX", capacity=6),
        ]
        db.add_all(rooms)
        db.commit()
        logger.info("Creada Sede Central Providencia con salas teóricas y boxes clínicos")

    # 2.1 Crear Sede Viña del Mar si no existe
    campus_vina = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
    if not campus_vina:
        campus_vina = Campus(
            code="SEDE-VINA",
            name="Clínica San Bao - Sede Viña del Mar",
            address="Av. Libertad 456",
            city="Viña del Mar",
            is_active=True,
        )
        db.add(campus_vina)
        db.commit()
        db.refresh(campus_vina)

        vina_rooms = [
            Room(campus_id=campus_vina.id, code="BOX-VINA-01", name="Box Acupuntura Shen", room_type="CLINICAL_BOX", capacity=2),
            Room(campus_id=campus_vina.id, code="BOX-VINA-02", name="Box Medicina Tradicional Jing", room_type="CLINICAL_BOX", capacity=2),
            Room(campus_id=campus_vina.id, code="BOX-VINA-03", name="Box Prácticas Supervisadas Qi", room_type="CLINICAL_BOX", capacity=6),
        ]
        db.add_all(vina_rooms)
        db.commit()
        logger.info("Creada Sede Viña del Mar con boxes clínicos especializados")

    # 2.2 Poblar Tablas Maestras Normalizadas (3NF) de Centros de Costo y Unidades de Negocio
    from app.modules.finance.models.commitment import CostCenter, BusinessUnit
    if db.query(CostCenter).count() == 0:
        default_cost_centers = [
            CostCenter(company_id=instituto.id, code="CC-DOCENCIA-ESCUELA", name="CC-DOCENCIA-ESCUELA Docencia Teórica y Mallas", area_type="ACADEMICO"),
            CostCenter(company_id=instituto.id, code="CC-102-FORMACION-CONTINUA", name="CC-102 Formación Continua y Seminarios", area_type="ACADEMICO"),
            CostCenter(company_id=clinica.id, code="CC-TUTORIA-CLINICA", name="CC-TUTORIA-CLINICA Supervisión de Práctica Clínica", area_type="CLINICO"),
            CostCenter(company_id=clinica.id, code="CC-201-BOXES-PROVIDENCIA", name="CC-201 Atención Boxes Acupuntura Providencia", area_type="CLINICO"),
            CostCenter(company_id=clinica.id, code="CC-202-BOXES-VINA", name="CC-202 Atención Boxes Sede Viña del Mar", area_type="CLINICO"),
            CostCenter(company_id=instituto.id, code="CC-301-ADMIN-HOLDING", name="CC-301 Administración Central Holding", area_type="ADMINISTRATIVO"),
        ]
        db.add_all(default_cost_centers)
        db.commit()

    if db.query(BusinessUnit).count() == 0:
        default_business_units = [
            BusinessUnit(company_id=instituto.id, campus_id=campus.id, code="UN-01", name="UN-01 Diplomados y Carreras MTC (Escuela SpA)"),
            BusinessUnit(company_id=instituto.id, campus_id=campus.id, code="UN-02", name="UN-02 Formación Continua y E-Commerce (Escuela SpA)"),
            BusinessUnit(company_id=clinica.id, campus_id=campus.id, code="UN-03", name="UN-03 Clínica Acupuntura Providencia (Clínica SpA)"),
            BusinessUnit(company_id=clinica.id, campus_id=campus_vina.id, code="UN-04", name="UN-04 Clínica Sede Viña del Mar (Clínica SpA)"),
        ]
        db.add_all(default_business_units)
        db.commit()

    # 3. Crear Usuario Superadministrador inicial si no existe
    admin_username = "admin"
    admin_user = db.query(User).filter(User.username == admin_username).first()
    if not admin_user:
        admin_rut = "11111111-1"
        admin_person = db.query(Person).filter(Person.rut == admin_rut).first()
        if not admin_person:
            admin_person = Person(
                rut=admin_rut,
                first_name="Administrador",
                last_name="San Bao",
                email="admin@sanbao.cl",
                phone="+56 9 9999 9999",
                is_active=True,
            )
            db.add(admin_person)
            db.commit()
            db.refresh(admin_person)

        admin_user = User(
            person_id=admin_person.id,
            username=admin_username,
            password_hash=get_password_hash("AdminSanBao2026!"),
            is_active=True,
            is_superuser=True,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        # Asignar rol SUPERADMIN en ambas sociedades
        superadmin_role = rbac_service.get_role_by_code("SUPERADMIN")
        if superadmin_role:
            rbac_service.assign_user_to_company(admin_user.id, instituto.id, superadmin_role.id)
            rbac_service.assign_user_to_company(admin_user.id, clinica.id, superadmin_role.id)

        logger.info("Usuario superadministrador inicial creado: admin / AdminSanBao2026!")

    # 4. Crear Usuario Alumno de Prueba si no existe
    student_username = "alumno"
    student_user = db.query(User).filter(User.username == student_username).first()
    if not student_user:
        student_rut = "19876543-0"
        student_person = db.query(Person).filter(Person.rut == student_rut).first()
        if not student_person:
            student_person = Person(
                rut=student_rut,
                first_name="Diego",
                last_name="Valenzuela",
                email="alumno@sanbao.cl",
                phone="+56 9 8765 4321",
                gender="MALE",
                is_active=True,
            )
            db.add(student_person)
            db.commit()
            db.refresh(student_person)

        student_user = User(
            person_id=student_person.id,
            username=student_username,
            password_hash=get_password_hash("AlumnoSanBao2026!"),
            is_active=True,
            is_superuser=False,
        )
        db.add(student_user)
        db.commit()
        db.refresh(student_user)

        # Asignar rol ALUMNO / ALUMNO_PRACTICA en Instituto SpA y Clínica SpA
        alumno_role = rbac_service.get_role_by_code("ALUMNO")
        alumno_practica_role = rbac_service.get_role_by_code("ALUMNO_PRACTICA")
        if alumno_role:
            rbac_service.assign_user_to_company(student_user.id, instituto.id, alumno_role.id)
        if alumno_practica_role:
            rbac_service.assign_user_to_company(student_user.id, clinica.id, alumno_practica_role.id)

        logger.info("Usuario alumno inicial creado: alumno / AlumnoSanBao2026!")

    # 5. Crear Usuario Secretaria Clínica si no existe
    sec_username = "secretaria"
    sec_user = db.query(User).filter(User.username == sec_username).first()
    if not sec_user:
        sec_rut = "16234567-2"
        sec_person = db.query(Person).filter(Person.rut == sec_rut).first()
        if not sec_person:
            sec_person = Person(
                rut=sec_rut,
                first_name="Valentina",
                last_name="Morales",
                email="secretaria@sanbao.cl",
                phone="+56 9 7654 3210",
                gender="FEMALE",
                is_active=True,
            )
            db.add(sec_person)
            db.commit()
            db.refresh(sec_person)

        sec_user = User(
            person_id=sec_person.id,
            username=sec_username,
            password_hash=get_password_hash("SecretariaSanBao2026!"),
            is_active=True,
            is_superuser=False,
        )
        db.add(sec_user)
        db.commit()
        db.refresh(sec_user)

        sec_role = rbac_service.get_role_by_code("SECRETARIA_CLINICA")
        if sec_role:
            rbac_service.assign_user_to_company(sec_user.id, clinica.id, sec_role.id)

        logger.info("Usuario secretaria inicial creado: secretaria / SecretariaSanBao2026!")

    # 5.1 Crear Usuario Secretaria Viña del Mar si no existe
    sec_vina_username = "secretaria_vina"
    sec_vina_user = db.query(User).filter(User.username == sec_vina_username).first()
    if not sec_vina_user:
        sec_vina_rut = "17890123-0"
        sec_vina_person = db.query(Person).filter(Person.rut == sec_vina_rut).first()
        if not sec_vina_person:
            sec_vina_person = Person(
                rut=sec_vina_rut,
                first_name="Sofía",
                last_name="Lagos",
                email="secretaria.vina@sanbao.cl",
                phone="+56 9 6543 2109",
                gender="FEMALE",
                is_active=True,
            )
            db.add(sec_vina_person)
            db.commit()
            db.refresh(sec_vina_person)

        sec_vina_user = User(
            person_id=sec_vina_person.id,
            username=sec_vina_username,
            password_hash=get_password_hash("SecretariaVina2026!"),
            is_active=True,
            is_superuser=False,
        )
        db.add(sec_vina_user)
        db.commit()
        db.refresh(sec_vina_user)

        sec_role = rbac_service.get_role_by_code("SECRETARIA_CLINICA")
        if sec_role:
            rbac_service.assign_user_to_company(sec_vina_user.id, clinica.id, sec_role.id)

        logger.info("Usuario secretaria Viña inicial creado: secretaria_vina / SecretariaVina2026!")

    # 6. Crear Usuario Dirección Clínica si no existe
    dir_username = "director"
    dir_user = db.query(User).filter(User.username == dir_username).first()
    if not dir_user:
        dir_rut = "15345678-K"
        dir_person = db.query(Person).filter(Person.rut == dir_rut).first()
        if not dir_person:
            dir_person = Person(
                rut=dir_rut,
                first_name="Roberto",
                last_name="Valenzuela",
                email="direccion.clinica@sanbao.cl",
                phone="+56 9 9123 4567",
                gender="MALE",
                is_active=True,
            )
            db.add(dir_person)
            db.commit()
            db.refresh(dir_person)

        dir_user = User(
            person_id=dir_person.id,
            username=dir_username,
            password_hash=get_password_hash("DirectorSanBao2026!"),
            is_active=True,
            is_superuser=False,
        )
        db.add(dir_user)
        db.commit()
        db.refresh(dir_user)

        dir_role = rbac_service.get_role_by_code("DIRECCION_CLINICA")
        if dir_role:
            rbac_service.assign_user_to_company(dir_user.id, clinica.id, dir_role.id)

        logger.info("Usuario dirección clínica inicial creado: director / DirectorSanBao2026!")

    # 7. Crear Usuario Dirección Académica si no existe
    dir_acad_username = "director_academico"
    dir_acad_user = db.query(User).filter(User.username == dir_acad_username).first()
    if not dir_acad_user:
        dir_acad_rut = "14201345-6"
        dir_acad_person = db.query(Person).filter(Person.rut == dir_acad_rut.replace(".", "").replace("-", "")).first()
        if not dir_acad_person:
            dir_acad_person = Person(
                rut=dir_acad_rut.replace(".", "").replace("-", ""),
                first_name="Marcela",
                last_name="Pérez",
                second_last_name="Morales",
                email="direccion.academica@sanbao.cl",
                phone="+56 9 8123 4567",
                gender="FEMALE",
                is_active=True,
            )
            db.add(dir_acad_person)
            db.commit()
            db.refresh(dir_acad_person)

        dir_acad_user = User(
            person_id=dir_acad_person.id,
            username=dir_acad_username,
            password_hash=get_password_hash("DirectorAcademico2026!"),
            is_active=True,
            is_superuser=False,
        )
        db.add(dir_acad_user)
        db.commit()
        db.refresh(dir_acad_user)

        dir_acad_role = rbac_service.get_role_by_code("DIRECCION_ACADEMICA") or rbac_service.get_role_by_code("ADMIN_ACADEMICO")
        if dir_acad_role:
            rbac_service.assign_user_to_company(dir_acad_user.id, instituto.id, dir_acad_role.id)

        logger.info("Usuario dirección académica inicial creado: director_academico / DirectorAcademico2026!")

    # 8. Crear Usuario Coordinador Académico si no existe
    coord_acad_username = "coordinador"
    coord_acad_user = db.query(User).filter(User.username == coord_acad_username).first()
    if not coord_acad_user:
        coord_acad_rut = "15876543-2"
        coord_acad_person = db.query(Person).filter(Person.rut == coord_acad_rut.replace(".", "").replace("-", "")).first()
        if not coord_acad_person:
            coord_acad_person = Person(
                rut=coord_acad_rut.replace(".", "").replace("-", ""),
                first_name="Camilo",
                last_name="San Martín",
                second_last_name="Bravo",
                email="coordinacion.academica@sanbao.cl",
                phone="+56 9 7123 9876",
                gender="MALE",
                is_active=True,
            )
            db.add(coord_acad_person)
            db.commit()
            db.refresh(coord_acad_person)

        coord_acad_user = User(
            person_id=coord_acad_person.id,
            username=coord_acad_username,
            password_hash=get_password_hash("CoordinadorSanBao2026!"),
            is_active=True,
            is_superuser=False,
        )
        db.add(coord_acad_user)
        db.commit()
        db.refresh(coord_acad_user)

        coord_role = rbac_service.get_role_by_code("COORDINADOR_ACADEMICO") or rbac_service.get_role_by_code("ADMIN_ACADEMICO")
        if coord_role:
            rbac_service.assign_user_to_company(coord_acad_user.id, instituto.id, coord_role.id)

        logger.info("Usuario coordinador académico inicial creado: coordinador / CoordinadorSanBao2026!")

    # 9. Crear Usuario Docente Titular si no existe
    docente_username = "docente"
    docente_user = db.query(User).filter(User.username == docente_username).first()
    if not docente_user:
        docente_rut = "14890123-4"
        docente_person = db.query(Person).filter(Person.rut == docente_rut.replace(".", "").replace("-", "")).first()
        if not docente_person:
            docente_person = Person(
                rut=docente_rut.replace(".", "").replace("-", ""),
                first_name="Zhiwei",
                last_name="Chen",
                second_last_name="Wang",
                email="zhiwei.chen@sanbao.cl",
                phone="+56 9 6123 7890",
                gender="MALE",
                is_active=True,
            )
            db.add(docente_person)
            db.commit()
            db.refresh(docente_person)

        docente_user = User(
            person_id=docente_person.id,
            username=docente_username,
            password_hash=get_password_hash("DocenteSanBao2026!"),
            is_active=True,
            is_superuser=False,
        )
        db.add(docente_user)
        db.commit()
        db.refresh(docente_user)

        docente_role = rbac_service.get_role_by_code("DOCENTE")
        if docente_role:
            rbac_service.assign_user_to_company(docente_user.id, instituto.id, docente_role.id)

        logger.info("Usuario docente inicial creado: docente / DocenteSanBao2026!")
