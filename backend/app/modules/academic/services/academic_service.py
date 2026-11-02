from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.modules.academic.models.program import Program, Curriculum, Course, CurriculumCourse
from app.modules.academic.models.period import AcademicPeriod, Cohort
from app.modules.academic.models.student import Student, Enrollment, CohortEnrollment
from app.modules.academic.models.evaluation import Evaluation, Grade, Attendance, ClinicalPracticeHour
from app.modules.academic.schemas.program import (
    ProgramCreate,
    ProgramUpdate,
    CurriculumCreate,
    CourseCreate,
    CourseUpdate,
    AddCourseToCurriculumRequest,
    AssignTeacherRequest,
    AssignCourseToProgramRequest,
)
from app.modules.academic.schemas.period import AcademicPeriodCreate, CohortCreate
from app.modules.academic.schemas.student import StudentCreate, EnrollmentCreate, CohortEnrollmentCreate
from app.modules.academic.schemas.evaluation import EvaluationCreate, GradeRecord, BatchAttendanceCreate, ClinicalPracticeHourCreate
from app.modules.finance.services.finance_service import FinanceService
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException, SanBaoException


class AcademicService:
    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------------------------------
    # Programas, Mallas y Asignaturas
    # --------------------------------------------------------------------------
    def _normalize_program_modality(self, program_type: str, modality: Optional[str]) -> str:
        """
        Normaliza la clasificación de modalidad según tipo de programa:
        - DIPLOMADO / CARRERA: PRESENCIAL, SEMIPRESENCIAL
        - CURSO / FORMACION_CONTINUA: PRESENCIAL, VIRTUAL, HIBRIDO (Presencial y Virtual al mismo tiempo)
        """
        ptype = (program_type or "DIPLOMADO").upper().strip()
        mod = (modality or "PRESENCIAL").upper().strip().replace("Í", "I")
        if ptype in ("DIPLOMADO", "CARRERA"):
            if mod in ("SEMIPRESENCIAL", "SEMI-PRESENCIAL", "HIBRIDO"):
                return "SEMIPRESENCIAL"
            return "PRESENCIAL"
        else:
            if mod in ("VIRTUAL", "ONLINE", "E-LEARNING"):
                return "VIRTUAL"
            if mod in ("HIBRIDO", "HÍBRIDO", "SEMIPRESENCIAL", "PRESENCIAL_Y_VIRTUAL"):
                return "HIBRIDO"
            return "PRESENCIAL"

    def create_program(self, data: ProgramCreate) -> Program:
        self._ensure_course_columns()
        existing = self.db.query(Program).filter(Program.code == data.code.strip().upper(), Program.deleted_at.is_(None)).first()
        if existing:
            raise EntityAlreadyExistsException("Programa", "código", data.code)

        program_type = (getattr(data, "program_type", None) or "DIPLOMADO").upper().strip()
        modality = self._normalize_program_modality(program_type, getattr(data, "modality", "PRESENCIAL"))

        program = Program(
            code=data.code.strip().upper(),
            name=data.name.strip(),
            program_type=program_type,
            modality=modality,
            degree_title=data.degree_title,
            description=data.description,
            total_semesters=data.total_semesters,
            total_theoretical_hours=data.total_theoretical_hours,
            total_practical_hours=data.total_practical_hours,
            min_clinical_hours=data.min_clinical_hours,
            is_active=data.is_active,
        )
        self.db.add(program)
        self.db.commit()
        self.db.refresh(program)
        return program

    def list_programs(self, only_active: bool = False, program_type: Optional[str] = None, q: Optional[str] = None) -> List[Program]:
        self._ensure_course_columns()
        query = self.db.query(Program).filter(Program.deleted_at.is_(None))
        if only_active:
            query = query.filter(Program.is_active == True)
        if program_type:
            query = query.filter(Program.program_type == program_type.upper().strip())
        if q:
            clean_q = f"%{q.strip()}%"
            query = query.filter((Program.name.ilike(clean_q)) | (Program.code.ilike(clean_q)))
        return query.order_by(Program.name.asc()).all()

    def get_program(self, program_id: str) -> Optional[Program]:
        self._ensure_course_columns()
        return self.db.query(Program).filter(
            (Program.id == program_id) | (Program.code == program_id),
            Program.deleted_at.is_(None)
        ).first()

    def update_program(self, program_id: str, data: ProgramUpdate) -> Program:
        self._ensure_course_columns()
        program = self.get_program(program_id)
        if not program:
            raise EntityNotFoundException("Programa", program_id)

        update_dict = data.model_dump(exclude_unset=True)
        if "code" in update_dict and update_dict["code"]:
            new_code = update_dict["code"].strip().upper()
            if new_code != program.code:
                existing = self.db.query(Program).filter(
                    Program.code == new_code,
                    Program.id != program.id,
                    Program.deleted_at.is_(None)
                ).first()
                if existing:
                    raise EntityAlreadyExistsException("Programa", "código", new_code)
                program.code = new_code
            update_dict.pop("code", None)

        if "program_type" in update_dict and update_dict["program_type"]:
            program.program_type = update_dict.pop("program_type").upper().strip()

        if "modality" in update_dict and update_dict["modality"]:
            program.modality = self._normalize_program_modality(
                program.program_type,
                update_dict.pop("modality"),
            )
        else:
            program.modality = self._normalize_program_modality(
                program.program_type,
                getattr(program, "modality", "PRESENCIAL"),
            )

        for key, value in update_dict.items():
            if value is not None and hasattr(program, key):
                setattr(program, key, value)

        self.db.commit()
        self.db.refresh(program)
        return program

    def toggle_program_status(self, program_id: str) -> Program:
        program = self.get_program(program_id)
        if not program:
            raise EntityNotFoundException("Programa", program_id)
        program.is_active = not program.is_active
        self.db.commit()
        self.db.refresh(program)
        return program

    _cols_checked: bool = False
    _programs_seeded: bool = False

    def _ensure_course_columns(self):
        """Garantiza que academic.courses y academic.programs tengan las columnas requeridas (ejecutado 1 vez por proceso)."""
        if AcademicService._cols_checked:
            return
        from sqlalchemy import text
        is_sqlite = self.db.bind.dialect.name == "sqlite" if self.db.bind else False
        ddls = (
            [
                "ALTER TABLE courses ADD COLUMN co_teacher_id VARCHAR(36)",
                "ALTER TABLE courses ADD COLUMN semester INTEGER DEFAULT 1 NOT NULL",
                "ALTER TABLE programs ADD COLUMN modality VARCHAR(50) DEFAULT 'PRESENCIAL' NOT NULL",
            ]
            if is_sqlite
            else [
                "ALTER TABLE academic.courses ADD COLUMN IF NOT EXISTS co_teacher_id VARCHAR(36)",
                "ALTER TABLE academic.courses ADD COLUMN IF NOT EXISTS semester INTEGER DEFAULT 1 NOT NULL",
                "ALTER TABLE academic.programs ADD COLUMN IF NOT EXISTS modality VARCHAR(50) DEFAULT 'PRESENCIAL' NOT NULL",
            ]
        )
        for ddl in ddls:
            try:
                self.db.execute(text(ddl))
                self.db.commit()
            except Exception:
                self.db.rollback()
        AcademicService._cols_checked = True

    def _validate_active_hr_teacher(self, person_id: Optional[str]) -> Optional[str]:
        """Valida que el docente exista y pertenezca al registro de RRHH activo dentro de la organización."""
        if not person_id:
            return None
        from app.modules.institutional.models.person import Person
        from app.modules.institutional.models.company import Company
        from app.modules.hr.models import HREmployee, EmployeeStatus, EmployeeType
        from datetime import date

        person = self.db.query(Person).filter(Person.id == str(person_id), Person.deleted_at.is_(None)).first()
        if not person:
            raise EntityNotFoundException("Docente (RRHH)", str(person_id))

        hr_emp = self.db.query(HREmployee).filter(HREmployee.person_id == person.id).first()
        if hr_emp:
            if not hr_emp.is_active or hr_emp.status != EmployeeStatus.ACTIVE:
                raise SanBaoException(
                    "HR_INACTIVE_TEACHER",
                    f"El profesional {person.full_name} no se encuentra ACTIVO en el registro de RRHH de la organización."
                )
        else:
            # Si fue creado por semilla/test sin ficha HREmployee aún, vincularlo como docente activo en RRHH
            comp = self.db.query(Company).first()
            if comp:
                emp_code = f"DOC-RRHH-{person.rut[-4:] if person.rut else '001'}"
                existing_code = self.db.query(HREmployee).filter(HREmployee.employee_number == emp_code).first()
                if existing_code:
                    emp_code = f"{emp_code}-{str(person.id)[:4].upper()}"
                hr_emp = HREmployee(
                    company_id=comp.id,
                    person_id=person.id,
                    employee_number=emp_code,
                    job_title="Docente Académico MTC Acreditado",
                    department="Cuerpo Docente MTC",
                    employee_type=EmployeeType.TEACHER,
                    hire_date=date(2025, 3, 1),
                    status=EmployeeStatus.ACTIVE,
                    is_active=True,
                )
                self.db.add(hr_emp)
                self.db.flush()
        return person.id

    def create_course(self, data: CourseCreate) -> Course:
        self._ensure_course_columns()
        existing = self.db.query(Course).filter(Course.code == data.code.strip().upper(), Course.deleted_at.is_(None)).first()
        if existing:
            raise EntityAlreadyExistsException("Asignatura", "código", data.code)

        t1_id = self._validate_active_hr_teacher(getattr(data, "teacher_id", None))
        t2_id = self._validate_active_hr_teacher(getattr(data, "co_teacher_id", None))
        if t1_id and t2_id and t1_id == t2_id:
            raise SanBaoException(
                "DUPLICATE_TEACHER",
                "El Segundo Profesor (Co-Docente) debe ser un profesional distinto al Docente Titular 1."
            )

        course = Course(
            code=data.code.strip().upper(),
            name=data.name.strip(),
            description=data.description,
            program_id=getattr(data, "program_id", None),
            teacher_id=t1_id,
            co_teacher_id=t2_id,
            semester=getattr(data, "semester", 1) or 1,
            theoretical_hours=data.theoretical_hours,
            practical_hours=data.practical_hours,
            clinical_hours=data.clinical_hours,
            credits=data.credits,
            is_clinical_practice=data.is_clinical_practice,
            is_active=data.is_active,
        )
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def get_course(self, course_id: str) -> Optional[Course]:
        self._ensure_course_columns()
        return self.db.query(Course).filter(
            (Course.id == course_id) | (Course.code == course_id),
            Course.deleted_at.is_(None)
        ).first()

    def list_courses(self, program_id: Optional[str] = None, only_active: bool = False, q: Optional[str] = None) -> List[Course]:
        self._ensure_course_columns()
        query = self.db.query(Course).filter(Course.deleted_at.is_(None))
        if program_id:
            prog = self.get_program(program_id)
            prog_actual_id = prog.id if prog else program_id
            # Filtrar por program_id directo o a través de curriculums
            query = query.filter(Course.program_id == prog_actual_id)
        if only_active:
            query = query.filter(Course.is_active == True)
        if q:
            clean_q = f"%{q.strip()}%"
            query = query.filter((Course.name.ilike(clean_q)) | (Course.code.ilike(clean_q)))
        return query.order_by(Course.semester.asc(), Course.code.asc()).all()

    def update_course(self, course_id: str, data: CourseUpdate) -> Course:
        self._ensure_course_columns()
        course = self.get_course(course_id)
        if not course:
            raise EntityNotFoundException("Asignatura", course_id)

        update_dict = data.model_dump(exclude_unset=True)
        if "code" in update_dict and update_dict["code"]:
            new_code = update_dict["code"].strip().upper()
            if new_code != course.code:
                existing = self.db.query(Course).filter(
                    Course.code == new_code,
                    Course.id != course.id,
                    Course.deleted_at.is_(None)
                ).first()
                if existing:
                    raise EntityAlreadyExistsException("Asignatura", "código", new_code)
                course.code = new_code
            update_dict.pop("code", None)

        if "teacher_id" in update_dict:
            update_dict["teacher_id"] = self._validate_active_hr_teacher(update_dict["teacher_id"])
        if "co_teacher_id" in update_dict:
            update_dict["co_teacher_id"] = self._validate_active_hr_teacher(update_dict["co_teacher_id"])

        final_t1 = update_dict.get("teacher_id", course.teacher_id)
        final_t2 = update_dict.get("co_teacher_id", getattr(course, "co_teacher_id", None))
        if final_t1 and final_t2 and final_t1 == final_t2:
            raise SanBaoException(
                "DUPLICATE_TEACHER",
                "El Segundo Profesor (Co-Docente) debe ser un profesional distinto al Docente Titular 1."
            )

        for key, value in update_dict.items():
            if hasattr(course, key):
                setattr(course, key, value)

        self.db.commit()
        self.db.refresh(course)
        return course

    def assign_teacher_to_course(
        self,
        course_id: str,
        teacher_id: Optional[str],
        co_teacher_id: Optional[str] = "__UNSET__",
    ) -> Course:
        self._ensure_course_columns()
        course = self.get_course(course_id)
        if not course:
            raise EntityNotFoundException("Asignatura", course_id)

        t1_id = self._validate_active_hr_teacher(teacher_id) if teacher_id else None
        t2_id = (
            getattr(course, "co_teacher_id", None)
            if co_teacher_id == "__UNSET__"
            else (self._validate_active_hr_teacher(co_teacher_id) if co_teacher_id else None)
        )

        if t1_id and t2_id and t1_id == t2_id:
            raise SanBaoException(
                "DUPLICATE_TEACHER",
                "El Segundo Profesor (Co-Docente) debe ser un profesional distinto al Docente Titular 1."
            )

        course.teacher_id = t1_id
        if co_teacher_id != "__UNSET__":
            course.co_teacher_id = t2_id

        self.db.commit()
        self.db.refresh(course)
        return course

    def assign_course_to_program(
        self,
        program_id: str,
        course_id: str,
        semester: Optional[int] = None,
        teacher_id: Optional[str] = "__UNSET__",
        co_teacher_id: Optional[str] = "__UNSET__",
    ) -> Course:
        self._ensure_course_columns()
        program = self.get_program(program_id)
        if not program:
            raise EntityNotFoundException("Programa", program_id)
        course = self.get_course(course_id)
        if not course:
            raise EntityNotFoundException("Asignatura", course_id)
        course.program_id = program.id
        if semester is not None and semester >= 1:
            course.semester = semester
        if teacher_id != "__UNSET__":
            course.teacher_id = self._validate_active_hr_teacher(teacher_id) if teacher_id else None
        if co_teacher_id != "__UNSET__":
            course.co_teacher_id = self._validate_active_hr_teacher(co_teacher_id) if co_teacher_id else None
        if course.teacher_id and course.co_teacher_id and course.teacher_id == course.co_teacher_id:
            raise SanBaoException(
                "DUPLICATE_TEACHER",
                "El Segundo Profesor (Co-Docente) debe ser un profesional distinto al Docente Titular 1."
            )
        self.db.commit()
        self.db.refresh(course)
        return course

    def unassign_course_from_program(self, program_id: str, course_id: str) -> Course:
        course = self.get_course(course_id)
        if not course:
            raise EntityNotFoundException("Asignatura", course_id)
        program = self.get_program(program_id)
        target_prog_id = program.id if program else program_id
        if course.program_id == target_prog_id:
            course.program_id = None
            self.db.commit()
            self.db.refresh(course)
        return course

    def delete_course(self, course_id: str) -> bool:
        course = self.get_course(course_id)
        if not course:
            raise EntityNotFoundException("Asignatura", course_id)
        course.deleted_at = datetime.utcnow()
        course.is_active = False
        self.db.commit()
        return True

    def _sync_teachers_with_active_hr(self):
        """
        Sincroniza el plantel docente y de tutores con el Registro de RRHH Activo (hr.hr_employees),
        diferenciando financieramente y por RRHH:
        - Docentes (TEACHER) -> Escuela San Bao SpA (Instituto de Medicina China Clásica SpA)
        - Tutores Clínicos (PRACTITIONER) -> Clínica San Bao SpA (Servicios Clínicos San Bao SpA)
        """
        from app.modules.clinical.routers.management import ensure_sample_tutors
        from app.modules.clinical.models.practitioner import Practitioner
        from app.modules.institutional.models.person import Person
        from app.modules.institutional.models.company import Company
        from app.modules.hr.models import HREmployee, EmployeeStatus, EmployeeType
        from app.modules.hr.services import HRHubService
        from datetime import date

        ensure_sample_tutors(self.db)
        hr_svc = HRHubService(self.db)
        try:
            hr_svc.ensure_sample_hr_data()
        except Exception:
            self.db.rollback()

        instituto, clinica = hr_svc._get_instituto_and_clinica()
        comp_default = instituto or self.db.query(Company).first()
        if not comp_default:
            return

        # Garantizar que todo tutor/docente acreditado tenga su ficha activa en hr.hr_employees
        tutors = (
            self.db.query(Practitioner, Person)
            .join(Person, Practitioner.person_id == Person.id)
            .filter(Person.deleted_at.is_(None), Practitioner.is_active == True)
            .all()
        )
        # RUTs que son Tutores Clínicos de Clínica San Bao SpA:
        tutor_clinica_ruts = {"128765431", "15432876K", "174568901"}
        for idx, (pract, person) in enumerate(tutors, start=1):
            clean_rut = (person.rut or "").replace(".", "").replace("-", "").upper()
            is_clinical_tutor = clean_rut in tutor_clinica_ruts
            target_comp = (clinica or comp_default) if is_clinical_tutor else (instituto or comp_default)
            emp = self.db.query(HREmployee).filter(HREmployee.person_id == person.id).first()
            if not emp:
                prefix = "CLI" if is_clinical_tutor else "DOC"
                emp_code = f"{prefix}-2026-10{idx}"
                if self.db.query(HREmployee).filter(HREmployee.employee_number == emp_code).first():
                    emp_code = f"{prefix}-2026-{str(person.id)[:4].upper()}"
                emp = HREmployee(
                    company_id=target_comp.id,
                    person_id=person.id,
                    employee_number=emp_code,
                    job_title=(
                        f"Tutor Clínico Supervisor • {pract.specialty or 'Campo Clínico San Bao'}"
                        if is_clinical_tutor
                        else f"Docente Titular Escuela • {pract.specialty or 'Medicina Tradicional China'}"
                    ),
                    department="Tutoría & Supervisión Clínica (Clínica San Bao SpA)" if is_clinical_tutor else "Cuerpo Docente MTC (Escuela San Bao SpA)",
                    employee_type=EmployeeType.PRACTITIONER if is_clinical_tutor else EmployeeType.TEACHER,
                    hire_date=date(2025, 3, 1),
                    status=EmployeeStatus.ACTIVE,
                    is_active=True,
                )
                self.db.add(emp)
            else:
                # Asegurar asignación correcta de sociedad SpA según rol (Docente = Escuela SpA, Tutor = Clínica SpA)
                if emp.employee_type == EmployeeType.TEACHER and instituto:
                    emp.company_id = instituto.id
                elif emp.employee_type == EmployeeType.PRACTITIONER and clinica:
                    emp.company_id = clinica.id
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()

    def list_teachers(self) -> List[dict]:
        """Obtiene la nómina de docentes y profesionales ACTIVOS en el registro de RRHH de la organización."""
        from app.modules.clinical.models.practitioner import Practitioner
        from app.modules.institutional.models.person import Person
        from app.modules.institutional.models.company import Company
        from app.modules.hr.models import HREmployee, EmployeeStatus, EmployeeType

        self._sync_teachers_with_active_hr()

        comp_map = {c.id: c for c in self.db.query(Company).all()}

        # Consultar exclusivamente colaboradores activos en el registro de RRHH (hr.hr_employees)
        hr_rows = (
            self.db.query(HREmployee, Person)
            .join(Person, HREmployee.person_id == Person.id)
            .filter(
                HREmployee.is_active == True,
                HREmployee.status == EmployeeStatus.ACTIVE,
                HREmployee.employee_type.in_([EmployeeType.TEACHER, EmployeeType.PRACTITIONER]),
                Person.deleted_at.is_(None),
            )
            .order_by(Person.last_name.asc())
            .all()
        )

        pract_map = {
            p.person_id: p
            for p in self.db.query(Practitioner).filter(Practitioner.deleted_at.is_(None)).all()
        }

        result = []
        seen = set()
        for emp, person in hr_rows:
            if person.id in seen:
                continue
            seen.add(person.id)
            pract = pract_map.get(person.id)
            comp = comp_map.get(emp.company_id)
            emp_type_str = emp.employee_type.value if hasattr(emp.employee_type, "value") else str(emp.employee_type)
            is_docente_escuela = emp_type_str == "TEACHER"
            specialty = (pract.specialty if pract and pract.specialty else None) or emp.job_title or "Docente MTC Acreditado"
            salutation = (
                "Dra."
                if person.gender == "FEMALE"
                or any(n in (person.first_name or "") for n in ["Marcela", "Patricia", "Mei", "Sofía", "Javiera", "Camila"])
                else ("Prof." if "Chen" in (person.first_name or "") else "Dr.")
            )
            result.append({
                "id": person.id,
                "person_id": person.id,
                "hr_employee_id": str(emp.id),
                "employee_number": emp.employee_number,
                "job_title": emp.job_title,
                "department": emp.department,
                "employee_type": emp_type_str,
                "company_id": emp.company_id,
                "company_name": comp.legal_name if comp else ("Instituto de Medicina China Clásica SpA" if is_docente_escuela else "Servicios Clínicos San Bao SpA"),
                "entity_classification": "DOCENTE ESCUELA SAN BAO SPA" if is_docente_escuela else "TUTOR CLÍNICA SAN BAO SPA",
                "hr_status": "ACTIVO EN RRHH",
                "salutation": salutation,
                "display_name": f"{salutation} {person.full_name}",
                "name": person.full_name,
                "first_name": person.first_name,
                "last_name": person.last_name,
                "rut": person.formatted_rut,
                "email": person.email,
                "specialty": specialty,
                "is_tutor": pract.is_tutor if pract else True,
                "is_active": True,
            })
        return result

    def ensure_sample_programs_and_courses(self):
        """Garantiza la existencia de programas oficiales de San Bao (Diplomados, Cursos, Formación Continua)."""
        from app.modules.institutional.models.person import Person

        self._ensure_course_columns()
        if (
            AcademicService._programs_seeded
            and self.db.query(Program.id).filter(Program.code == "DIP-MTC-01").first() is not None
            and self.db.query(Course.id).filter(Course.code == "MTC-101").first() is not None
        ):
            return
        self._sync_teachers_with_active_hr()
        AcademicService._programs_seeded = True

        # Mapa de docentes activos en RRHH
        perez = self.db.query(Person).filter(Person.rut == "142013456").first()
        lin = self.db.query(Person).filter(Person.rut == "189445123").first()
        gomez = self.db.query(Person).filter(Person.rut == "128765431").first()
        soto = self.db.query(Person).filter(Person.rut == "15432876K").first()
        morales = self.db.query(Person).filter(Person.rut == "139876542").first()

        sample_programs = [
            {
                "code": "DIP-MTC-01",
                "name": "Diplomado Superior en Medicina China Tradicional",
                "program_type": "DIPLOMADO",
                "modality": "SEMIPRESENCIAL",
                "degree_title": "Diplomado Superior en Medicina Tradicional China",
                "description": "Formación integral en fundamentos taoístas, diagnóstico diferencial por pulso y lengua, y terapéutica de canales y puntos.",
                "total_semesters": 2,
                "total_theoretical_hours": 240,
                "total_practical_hours": 120,
                "min_clinical_hours": 60,
                "is_active": True,
                "courses": [
                    {
                        "code": "MTC-101",
                        "name": "Fundamentos de Medicina China y Filosofía Taoísta",
                        "description": "Teoría del Yin-Yang, Cinco Elementos (Wu Xing), Sustancias Vitales y Fisiología Zang-Fu.",
                        "semester": 1,
                        "theoretical_hours": 60,
                        "practical_hours": 20,
                        "clinical_hours": 0,
                        "credits": 5,
                        "teacher_id": perez.id if perez else None,
                        "co_teacher_id": lin.id if lin else None,
                    },
                    {
                        "code": "MTC-102",
                        "name": "Diagnóstico Tradicional: Semiología de la Lengua y Pulsología",
                        "description": "Los 4 métodos de examen diagnóstico (Si Zhen) e interpretación clínica de signos tradicionales.",
                        "semester": 1,
                        "theoretical_hours": 50,
                        "practical_hours": 30,
                        "clinical_hours": 0,
                        "credits": 5,
                        "teacher_id": morales.id if morales else None,
                        "co_teacher_id": soto.id if soto else None,
                    },
                    {
                        "code": "MTC-103",
                        "name": "Canales, Colaterales y Puntos de Acupuntura I",
                        "description": "Recorrido anatómico, localización precisa y combinaciones terapéuticas de los 12 canales principales.",
                        "semester": 2,
                        "theoretical_hours": 60,
                        "practical_hours": 40,
                        "clinical_hours": 0,
                        "credits": 6,
                        "teacher_id": gomez.id if gomez else None,
                        "co_teacher_id": perez.id if perez else None,
                    },
                    {
                        "code": "MTC-204",
                        "name": "Práctica Clínica Supervisada en Acupuntura y Diagnóstico Integrativo",
                        "description": "Atención clínica supervisada en Box San Bao con aplicación de Acupuntura, Moxibustión y Pulsología.",
                        "semester": 2,
                        "theoretical_hours": 20,
                        "practical_hours": 30,
                        "clinical_hours": 60,
                        "credits": 8,
                        "is_clinical_practice": True,
                        "teacher_id": gomez.id if gomez else None,
                        "co_teacher_id": morales.id if morales else None,
                    },
                ]
            },
            {
                "code": "CUR-TUI-01",
                "name": "Curso de Especialización en Masaje Terapéutico Tuina y Ventosas",
                "program_type": "CURSO",
                "modality": "PRESENCIAL",
                "degree_title": "Especialista en Masaje Clínico Tuina y Técnicas Afines",
                "description": "Especialización en manipulaciones de tejido blando, tracciones articulares y ventosaterapia tradicional.",
                "total_semesters": 1,
                "total_theoretical_hours": 60,
                "total_practical_hours": 60,
                "min_clinical_hours": 30,
                "is_active": True,
                "courses": [
                    {
                        "code": "TUI-101",
                        "name": "Bases y Maniobras de Tuina Tradicional",
                        "description": "Técnicas de balanceo (Gun Fa), empuje (Tui Fa), amasamiento (Nie Fa) y percusión.",
                        "semester": 1,
                        "theoretical_hours": 30,
                        "practical_hours": 30,
                        "clinical_hours": 0,
                        "credits": 4,
                        "teacher_id": soto.id if soto else None,
                        "co_teacher_id": morales.id if morales else None,
                    },
                    {
                        "code": "TUI-102",
                        "name": "Tuina Clínico y Patologías del Aparato Locomotor",
                        "description": "Tratamiento de lumbalgias, cervicalgias, periartritis de hombro y lesiones tendinomusculares.",
                        "semester": 1,
                        "theoretical_hours": 30,
                        "practical_hours": 30,
                        "clinical_hours": 20,
                        "credits": 4,
                        "is_clinical_practice": True,
                        "teacher_id": lin.id if lin else None,
                    },
                ]
            },
            {
                "code": "DIP-FITO-02",
                "name": "Diplomado Superior en Fitoterapia y Farmacopea China",
                "program_type": "DIPLOMADO",
                "modality": "PRESENCIAL",
                "degree_title": "Diplomado Superior en Farmacopea y Fórmulas Magistrales MTC",
                "description": "Estudio exhaustivo de hierbas chinas, propiedades térmicas, sabores, trofismo de canal y formulaciones clásicas.",
                "total_semesters": 2,
                "total_theoretical_hours": 200,
                "total_practical_hours": 80,
                "min_clinical_hours": 40,
                "is_active": True,
                "courses": [
                    {
                        "code": "FIT-101",
                        "name": "Farmacopea China y Materia Médica Tradicional",
                        "description": "Categorías herbales, preparación (Pao Zhi) y sinergias botánicas tradicionales.",
                        "semester": 1,
                        "theoretical_hours": 60,
                        "practical_hours": 20,
                        "clinical_hours": 0,
                        "credits": 5,
                        "teacher_id": lin.id if lin else None,
                        "co_teacher_id": perez.id if perez else None,
                    },
                    {
                        "code": "FIT-102",
                        "name": "Prescripciones Clásicas y Fórmulas Magistrales MTC",
                        "description": "Arquitectura de fórmulas (Emperador, Ministro, Asistente, Mensajero) para síndromes complejos.",
                        "semester": 2,
                        "theoretical_hours": 60,
                        "practical_hours": 30,
                        "clinical_hours": 0,
                        "credits": 5,
                        "teacher_id": lin.id if lin else None,
                    },
                ]
            },
            {
                "code": "FC-CRANEO-01",
                "name": "Formación Continua en Craneopuntura YNSA y Auriculoterapia",
                "program_type": "FORMACION_CONTINUA",
                "modality": "HIBRIDO",
                "degree_title": "Certificado de Formación Continua en Microsistemas Acupunturales",
                "description": "Actualización clínica en nueva craneopuntura de Yamamoto (YNSA) y auriculopuntura francesa y china.",
                "total_semesters": 1,
                "total_theoretical_hours": 45,
                "total_practical_hours": 45,
                "min_clinical_hours": 20,
                "is_active": True,
                "courses": [
                    {
                        "code": "FC-101",
                        "name": "Craneopuntura de Yamamoto (YNSA) y Neurología MTC",
                        "description": "Puntos básicos, puntos de pares craneales y tratamiento de secuelas de ACV y dolor.",
                        "semester": 1,
                        "theoretical_hours": 25,
                        "practical_hours": 25,
                        "clinical_hours": 0,
                        "credits": 3,
                        "teacher_id": gomez.id if gomez else None,
                    },
                    {
                        "code": "FC-102",
                        "name": "Auriculoterapia Avanzada y Manejo de Adicciones",
                        "description": "Zonas reflejas auriculares, somatotopía y protocolos de deshabituación tabáquica y estrés.",
                        "semester": 1,
                        "theoretical_hours": 20,
                        "practical_hours": 20,
                        "clinical_hours": 0,
                        "credits": 3,
                        "teacher_id": soto.id if soto else None,
                    },
                ]
            },
        ]

        for p_data in sample_programs:
            courses_data = p_data.pop("courses", [])
            prog = self.db.query(Program).filter(Program.code == p_data["code"]).first()
            if not prog:
                prog = Program(**p_data)
                self.db.add(prog)
                self.db.commit()
                self.db.refresh(prog)
            else:
                if p_data.get("modality") and getattr(prog, "modality", "PRESENCIAL") == "PRESENCIAL":
                    prog.modality = p_data["modality"]
                    self.db.commit()

            for c_data in courses_data:
                course = self.db.query(Course).filter(Course.code == c_data["code"]).first()
                if not course:
                    course = Course(program_id=prog.id, **c_data)
                    self.db.add(course)
                    self.db.commit()
                else:
                    if not course.program_id:
                        course.program_id = prog.id
                    if not course.teacher_id and c_data.get("teacher_id"):
                        course.teacher_id = c_data["teacher_id"]
                    if not getattr(course, "co_teacher_id", None) and c_data.get("co_teacher_id") and course.teacher_id != c_data.get("co_teacher_id"):
                        course.co_teacher_id = c_data["co_teacher_id"]
                    if c_data.get("semester") and getattr(course, "semester", 1) == 1:
                        course.semester = c_data["semester"]
                    self.db.commit()

    def create_curriculum(self, data: CurriculumCreate) -> Curriculum:
        program = self.db.query(Program).filter(Program.id == data.program_id, Program.deleted_at.is_(None)).first()
        if not program:
            raise EntityNotFoundException("Programa", data.program_id)

        curriculum = Curriculum(
            program_id=data.program_id,
            code=data.code.strip().upper(),
            version_name=data.version_name.strip(),
            effective_year=data.effective_year,
            is_active=data.is_active,
        )
        self.db.add(curriculum)
        self.db.commit()
        self.db.refresh(curriculum)
        return curriculum

    def add_course_to_curriculum(self, curriculum_id: str, data: AddCourseToCurriculumRequest) -> CurriculumCourse:
        curriculum = self.db.query(Curriculum).filter(Curriculum.id == curriculum_id, Curriculum.deleted_at.is_(None)).first()
        if not curriculum:
            raise EntityNotFoundException("Malla", curriculum_id)

        course = self.db.query(Course).filter(Course.id == data.course_id, Course.deleted_at.is_(None)).first()
        if not course:
            raise EntityNotFoundException("Asignatura", data.course_id)

        link = CurriculumCourse(
            curriculum_id=curriculum_id,
            course_id=data.course_id,
            semester=data.semester,
            is_mandatory=data.is_mandatory,
            prerequisite_course_id=data.prerequisite_course_id,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link

    # --------------------------------------------------------------------------
    # Períodos Académicos y Cohortes / Secciones
    # --------------------------------------------------------------------------
    def create_academic_period(self, data: AcademicPeriodCreate) -> AcademicPeriod:
        existing = self.db.query(AcademicPeriod).filter(AcademicPeriod.code == data.code.strip().upper(), AcademicPeriod.deleted_at.is_(None)).first()
        if existing:
            raise EntityAlreadyExistsException("Período Académico", "código", data.code)

        period = AcademicPeriod(
            code=data.code.strip().upper(),
            name=data.name.strip(),
            year=data.year,
            semester_number=data.semester_number,
            start_date=data.start_date,
            end_date=data.end_date,
            is_enrollment_open=data.is_enrollment_open,
            is_active=data.is_active,
        )
        self.db.add(period)
        self.db.commit()
        self.db.refresh(period)
        return period

    def create_cohort(self, data: CohortCreate) -> Cohort:
        course = self.db.query(Course).filter(Course.id == data.course_id, Course.deleted_at.is_(None)).first()
        if not course:
            raise EntityNotFoundException("Asignatura", data.course_id)

        period = self.db.query(AcademicPeriod).filter(AcademicPeriod.id == data.academic_period_id, AcademicPeriod.deleted_at.is_(None)).first()
        if not period:
            raise EntityNotFoundException("Período Académico", data.academic_period_id)

        cohort = Cohort(
            course_id=data.course_id,
            academic_period_id=data.academic_period_id,
            code=data.code.strip().upper(),
            teacher_id=data.teacher_id,
            campus_id=data.campus_id,
            room_id=data.room_id,
            schedule=data.schedule,
            quota=data.quota,
            status=data.status,
        )
        self.db.add(cohort)
        self.db.commit()
        self.db.refresh(cohort)
        return cohort

    # --------------------------------------------------------------------------
    # Admisión, Matrícula y Finanzas Integradas
    # --------------------------------------------------------------------------
    def admit_student(self, data: StudentCreate) -> Student:
        """Registra a una persona como estudiante formal del Instituto."""
        existing = self.db.query(Student).filter(Student.person_id == data.person_id, Student.deleted_at.is_(None)).first()
        if existing:
            raise EntityAlreadyExistsException("Estudiante", "persona", data.person_id)

        admission_date = data.admission_date or date.today()

        if not data.student_number:
            year = admission_date.year
            count = self.db.query(Student).filter(Student.student_number.like(f"MAT-{year}-%")).count()
            student_number = f"MAT-{year}-{count + 1:04d}"
        else:
            student_number = data.student_number.strip().upper()

        student = Student(
            person_id=data.person_id,
            student_number=student_number,
            admission_date=admission_date,
            status=data.status,
            notes=data.notes,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def enroll_student(self, data: EnrollmentCreate, company_id: str) -> Enrollment:
        """
        Formaliza la matrícula académica del estudiante e integra automáticamente
        la creación del arancel financiero particionado en cuotas en el Instituto SpA.
        """
        student = self.db.query(Student).filter(Student.id == data.student_id, Student.deleted_at.is_(None)).first()
        if not student:
            raise EntityNotFoundException("Estudiante", data.student_id)

        program = self.db.query(Program).filter(Program.id == data.program_id, Program.deleted_at.is_(None)).first()
        if not program:
            raise EntityNotFoundException("Programa", data.program_id)

        period = self.db.query(AcademicPeriod).filter(AcademicPeriod.id == data.academic_period_id, AcademicPeriod.deleted_at.is_(None)).first()
        if not period:
            raise EntityNotFoundException("Período Académico", data.academic_period_id)

        # Verificar si ya está matriculado en este período y programa
        existing = (
            self.db.query(Enrollment)
            .filter(
                Enrollment.student_id == student.id,
                Enrollment.program_id == program.id,
                Enrollment.academic_period_id == period.id,
                Enrollment.status != "CANCELLED",
                Enrollment.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            raise SanBaoException("El estudiante ya se encuentra matriculado en este programa para el período académico seleccionado.")

        enrollment_date = data.enrollment_date or date.today()

        enrollment = Enrollment(
            student_id=student.id,
            program_id=program.id,
            academic_period_id=period.id,
            enrollment_date=enrollment_date,
            status="CONFIRMED",
        )
        self.db.add(enrollment)
        self.db.flush()

        # Generar compromiso financiero integrado mediante FinanceService
        finance_service = FinanceService(self.db)
        concept = f"Arancel {program.name} - Semestre {period.code}"
        finance_service.create_tuition_commitment(
            company_id=company_id,
            person_id=student.person_id,
            enrollment_id=enrollment.id,
            concept=concept,
            total_amount=data.total_tuition_amount,
            installments_count=data.installments_count,
            first_due_date=data.first_due_date or enrollment_date,
        )

        self.db.commit()
        self.db.refresh(enrollment)
        return enrollment

    def enroll_in_cohort(self, enrollment_id: str, cohort_id: str) -> CohortEnrollment:
        """Inscribe una asignatura específica (cohorte) para un alumno matriculado."""
        enrollment = self.db.query(Enrollment).filter(Enrollment.id == enrollment_id, Enrollment.deleted_at.is_(None)).first()
        if not enrollment:
            raise EntityNotFoundException("Matrícula", enrollment_id)

        cohort = self.db.query(Cohort).filter(Cohort.id == cohort_id, Cohort.deleted_at.is_(None)).first()
        if not cohort:
            raise EntityNotFoundException("Cohorte", cohort_id)

        current_count = self.db.query(CohortEnrollment).filter(CohortEnrollment.cohort_id == cohort_id, CohortEnrollment.status != "WITHDRAWN").count()
        if current_count >= cohort.quota:
            raise SanBaoException(f"La sección '{cohort.code}' no cuenta con vacantes disponibles (Cupo: {cohort.quota})")

        existing = (
            self.db.query(CohortEnrollment)
            .filter(
                CohortEnrollment.enrollment_id == enrollment_id,
                CohortEnrollment.cohort_id == cohort_id,
                CohortEnrollment.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            raise SanBaoException("El estudiante ya está inscrito en esta sección.")

        item = CohortEnrollment(
            enrollment_id=enrollment.id,
            student_id=enrollment.student_id,
            cohort_id=cohort.id,
            status="ENROLLED",
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    # --------------------------------------------------------------------------
    # Evaluaciones y Calificaciones (Escala 1.0 a 7.0)
    # --------------------------------------------------------------------------
    def create_evaluation(self, data: EvaluationCreate) -> Evaluation:
        cohort = self.db.query(Cohort).filter(Cohort.id == data.cohort_id, Cohort.deleted_at.is_(None)).first()
        if not cohort:
            raise EntityNotFoundException("Cohorte", data.cohort_id)

        eval_obj = Evaluation(
            cohort_id=data.cohort_id,
            name=data.name.strip(),
            description=data.description,
            weight_percentage=data.weight_percentage,
            evaluation_date=data.evaluation_date,
        )
        self.db.add(eval_obj)
        self.db.commit()
        self.db.refresh(eval_obj)
        return eval_obj

    def record_grade(self, evaluation_id: str, data: GradeRecord, graded_by: Optional[str] = None) -> Grade:
        """Registra la nota de un estudiante validando la escala de 1.0 a 7.0."""
        evaluation = self.db.query(Evaluation).filter(Evaluation.id == evaluation_id, Evaluation.deleted_at.is_(None)).first()
        if not evaluation:
            raise EntityNotFoundException("Evaluación", evaluation_id)

        student = self.db.query(Student).filter(Student.id == data.student_id, Student.deleted_at.is_(None)).first()
        if not student:
            raise EntityNotFoundException("Estudiante", data.student_id)

        grade = (
            self.db.query(Grade)
            .filter(Grade.evaluation_id == evaluation_id, Grade.student_id == data.student_id)
            .first()
        )
        if not grade:
            grade = Grade(
                evaluation_id=evaluation_id,
                student_id=data.student_id,
                score=data.score,
                feedback=data.feedback,
                graded_by=graded_by,
            )
            self.db.add(grade)
        else:
            grade.score = data.score
            grade.feedback = data.feedback
            grade.graded_by = graded_by

        self.db.commit()
        self.db.refresh(grade)

        # Actualizar promedio final en CohortEnrollment si procede
        self._update_cohort_final_grade(evaluation.cohort_id, student.id)
        return grade

    def _update_cohort_final_grade(self, cohort_id: str, student_id: str):
        """Calcula el promedio ponderado del estudiante en la cohorte."""
        evaluations = self.db.query(Evaluation).filter(Evaluation.cohort_id == cohort_id, Evaluation.deleted_at.is_(None)).all()
        if not evaluations:
            return

        total_weight = sum(e.weight_percentage for e in evaluations)
        if total_weight == 0:
            return

        weighted_sum = Decimal(0)
        graded_weight = Decimal(0)

        for e in evaluations:
            g = self.db.query(Grade).filter(Grade.evaluation_id == e.id, Grade.student_id == student_id).first()
            if g:
                weighted_sum += g.score * (e.weight_percentage / Decimal(100))
                graded_weight += e.weight_percentage

        cohort_enrollment = (
            self.db.query(CohortEnrollment)
            .filter(CohortEnrollment.cohort_id == cohort_id, CohortEnrollment.student_id == student_id)
            .first()
        )
        if cohort_enrollment and graded_weight == 100:
            final_grade = round(weighted_sum, 1)
            cohort_enrollment.final_grade = final_grade
            # En Chile se aprueba con nota >= 4.0
            cohort_enrollment.status = "APPROVED" if final_grade >= Decimal("4.0") else "FAILED"
            self.db.commit()

    # --------------------------------------------------------------------------
    # Prácticas Clínicas Supervisadas (Acreditación de horas)
    # --------------------------------------------------------------------------
    def log_clinical_practice_hours(self, data: ClinicalPracticeHourCreate) -> ClinicalPracticeHour:
        """Registra y acredita horas prácticas de atención bajo tutoría clínica."""
        record = ClinicalPracticeHour(
            student_id=data.student_id,
            cohort_id=data.cohort_id,
            tutor_id=data.tutor_id,
            activity_date=data.activity_date,
            hours_completed=data.hours_completed,
            patient_encounter_id=data.patient_encounter_id,
            comments=data.comments,
            status="APPROVED",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_student_clinical_hours_summary(self, student_id: str) -> int:
        """Retorna el total de horas clínicas aprobadas y acumuladas por el alumno."""
        records = (
            self.db.query(ClinicalPracticeHour)
            .filter(
                ClinicalPracticeHour.student_id == student_id,
                ClinicalPracticeHour.status == "APPROVED",
                ClinicalPracticeHour.deleted_at.is_(None),
            )
            .all()
        )
        return sum(r.hours_completed for r in records)
