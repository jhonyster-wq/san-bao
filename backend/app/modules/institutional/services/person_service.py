from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.modules.institutional.models.person import Person, Supplier
from app.modules.institutional.schemas.person import PersonCreate, PersonUpdate
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException, InvalidRUTException
from app.shared.validators.rut import ChileanRUT


class PersonService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, person_id: str) -> Person:
        person = self.db.query(Person).filter(Person.id == person_id, Person.deleted_at.is_(None)).first()
        if not person:
            raise EntityNotFoundException("Persona", person_id)
        return person

    def get_by_rut(self, rut: str) -> Optional[Person]:
        cleaned_rut = ChileanRUT.clean(rut)
        if not cleaned_rut:
            return None
        unhyphenated = cleaned_rut.replace("-", "")
        formatted = ChileanRUT.format(cleaned_rut, with_dots=True)
        person = (
            self.db.query(Person)
            .filter(
                Person.rut.in_([cleaned_rut, unhyphenated, formatted]),
                Person.deleted_at.is_(None),
            )
            .first()
        )
        if person and person.rut != cleaned_rut:
            # Normalizar de manera no destructiva al formato canónico sin puntos y con guion
            conflict = (
                self.db.query(Person)
                .filter(Person.rut == cleaned_rut, Person.id != person.id)
                .first()
            )
            if not conflict:
                person.rut = cleaned_rut
                self.db.commit()
                self.db.refresh(person)
        return person

    def get_by_email(self, email: str) -> Optional[Person]:
        return self.db.query(Person).filter(Person.email == email.lower().strip(), Person.deleted_at.is_(None)).first()

    def list_all(self, skip: int = 0, limit: int = 50, search: Optional[str] = None) -> tuple[List[Person], int]:
        query = self.db.query(Person).filter(Person.deleted_at.is_(None))
        if search:
            raw_term = search.strip()
            cleaned_rut = ChileanRUT.clean(raw_term)
            search_term = f"%{raw_term}%"
            filters = (
                (Person.first_name.ilike(search_term))
                | (Person.last_name.ilike(search_term))
                | (Person.rut.ilike(search_term))
                | (Person.email.ilike(search_term))
            )
            if cleaned_rut and "-" in cleaned_rut:
                filters = filters | (Person.rut.ilike(f"%{cleaned_rut}%"))
            query = query.filter(filters)
        total = query.count()
        people = query.offset(skip).limit(limit).all()
        return people, total

    def create(self, data: PersonCreate) -> Person:
        cleaned_rut = ChileanRUT.clean(data.rut)
        if not ChileanRUT.validate(cleaned_rut):
            raise InvalidRUTException(data.rut)

        if self.get_by_rut(cleaned_rut):
            raise EntityAlreadyExistsException("Persona", "RUT", cleaned_rut)

        person = Person(
            rut=cleaned_rut,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            second_last_name=data.second_last_name.strip() if data.second_last_name else None,
            email=data.email.lower().strip(),
            phone=data.phone,
            birth_date=data.birth_date,
            gender=data.gender,
            address=data.address,
            city=data.city,
            is_active=data.is_active,
        )
        self.db.add(person)
        self.db.commit()
        self.db.refresh(person)
        return person

    def update(self, person_id: str, data: PersonUpdate) -> Person:
        person = self.get_by_id(person_id)
        update_data = data.model_dump(exclude_unset=True)
        if "email" in update_data and update_data["email"]:
            update_data["email"] = update_data["email"].lower().strip()

        for key, value in update_data.items():
            setattr(person, key, value)
        self.db.commit()
        self.db.refresh(person)
        return person

    def soft_delete(self, person_id: str):
        person = self.get_by_id(person_id)
        person.soft_delete()
        self.db.commit()

    def get_identity_360_by_rut(self, rut: str) -> Dict[str, Any]:
        """
        Fuente Maestra de Identidad (Requerimiento A):
        Retorna la ficha única de persona por RUT chileno normalizado (sin puntos y con guion)
        y todos los roles que desempeña simultáneamente en el ecosistema San Bao:
        ALUMNO, PACIENTE, DOCENTE, TUTOR, PROFESIONAL, COLABORADOR y PROVEEDOR.
        """
        from app.modules.academic.models.student import Student
        from app.modules.academic.models.program import Course
        from app.modules.academic.models.period import Cohort
        from app.modules.clinical.models.patient import Patient
        from app.modules.clinical.models.practitioner import Practitioner
        from app.modules.hr.models import HREmployee, EmployeeType

        cleaned_rut = ChileanRUT.clean(rut)
        if not ChileanRUT.validate(cleaned_rut):
            raise InvalidRUTException(rut)

        person = self.get_by_rut(cleaned_rut)
        if not person:
            return {
                "exists": False,
                "canonical_rut": cleaned_rut,
                "formatted_rut": ChileanRUT.format(cleaned_rut, with_dots=True),
                "mod11_valid": True,
                "master_source": "ERP_CORE_PEOPLE",
                "person": None,
                "active_roles": [],
                "role_profiles": {},
            }

        active_roles: List[str] = []
        role_profiles: Dict[str, Any] = {}

        # 1. ALUMNO
        student = self.db.query(Student).filter(Student.person_id == person.id, Student.deleted_at.is_(None)).first()
        if student:
            active_roles.append("ALUMNO")
            role_profiles["ALUMNO"] = {
                "student_id": student.id,
                "student_number": student.student_number,
                "status": student.status,
                "clinical_practice_approved": bool(student.clinical_practice_approved),
            }

        # 2. PACIENTE
        patient = self.db.query(Patient).filter(Patient.person_id == person.id, Patient.deleted_at.is_(None)).first()
        if patient:
            active_roles.append("PACIENTE")
            role_profiles["PACIENTE"] = {
                "patient_id": patient.id,
                "record_number": patient.record_number,
                "is_active": bool(patient.is_active),
            }

        # 3. PROFESIONAL y 4. TUTOR
        practitioner = (
            self.db.query(Practitioner)
            .filter(Practitioner.person_id == person.id, Practitioner.deleted_at.is_(None))
            .first()
        )
        if practitioner:
            active_roles.append("PROFESIONAL")
            role_profiles["PROFESIONAL"] = {
                "practitioner_id": practitioner.id,
                "license_number": practitioner.license_number,
                "specialty": practitioner.specialty,
                "is_active": bool(practitioner.is_active),
            }
            if practitioner.is_tutor:
                active_roles.append("TUTOR")
                role_profiles["TUTOR"] = {
                    "practitioner_id": practitioner.id,
                    "specialty": practitioner.specialty,
                    "is_tutor": True,
                }

        # 5. DOCENTE y 6. COLABORADOR
        employees = self.db.query(HREmployee).filter(HREmployee.person_id == person.id, HREmployee.is_active == True).all()
        taught_courses = (
            self.db.query(Course)
            .filter((Course.teacher_id == person.id) | (Course.co_teacher_id == person.id))
            .count()
        )
        taught_cohorts = self.db.query(Cohort).filter(Cohort.teacher_id == person.id).count()
        is_teacher_hr = any(e.employee_type == EmployeeType.TEACHER for e in employees)

        if is_teacher_hr or taught_courses > 0 or taught_cohorts > 0:
            active_roles.append("DOCENTE")
            role_profiles["DOCENTE"] = {
                "person_id": person.id,
                "assigned_courses_count": taught_courses,
                "assigned_cohorts_count": taught_cohorts,
            }

        if employees:
            active_roles.append("COLABORADOR")
            role_profiles["COLABORADOR"] = [
                {
                    "employee_id": str(e.id),
                    "company_id": e.company_id,
                    "employee_number": e.employee_number,
                    "job_title": e.job_title,
                    "employee_type": e.employee_type.value if hasattr(e.employee_type, "value") else str(e.employee_type),
                    "status": e.status.value if hasattr(e.status, "value") else str(e.status),
                }
                for e in employees
            ]

        # 7. PROVEEDOR
        supplier = (
            self.db.query(Supplier)
            .filter(
                (Supplier.person_id == person.id) | (Supplier.rut == cleaned_rut),
                Supplier.deleted_at.is_(None),
            )
            .first()
        )
        if supplier:
            active_roles.append("PROVEEDOR")
            role_profiles["PROVEEDOR"] = {
                "supplier_id": supplier.id,
                "business_name": supplier.business_name,
                "trade_category": supplier.trade_category,
                "default_cost_center_code": supplier.default_cost_center_code,
                "is_active": bool(supplier.is_active),
            }

        return {
            "exists": True,
            "canonical_rut": cleaned_rut,
            "formatted_rut": ChileanRUT.format(cleaned_rut, with_dots=True),
            "mod11_valid": True,
            "master_source": "ERP_CORE_PEOPLE",
            "person": {
                "id": person.id,
                "rut": person.canonical_rut,
                "formatted_rut": person.formatted_rut,
                "first_name": person.first_name,
                "last_name": person.last_name,
                "second_last_name": person.second_last_name,
                "full_name": person.full_name,
                "email": person.email,
                "phone": person.phone,
                "address": person.address,
                "city": person.city,
                "is_active": person.is_active,
            },
            "active_roles": active_roles,
            "role_profiles": role_profiles,
        }

    def upsert_master_identity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea o enriquece la identidad maestra única en el ERP (core.people) sin duplicar personas,
        y opcionalmente habilita perfiles adicionales (ej: PROVEEDOR, PACIENTE) reutilizando el mismo UUID.
        Usado por el ERP y consumido por el Gestor de Campo Clínico.
        """
        raw_rut = str(payload.get("rut") or "").strip()
        cleaned_rut = ChileanRUT.clean(raw_rut)
        if not ChileanRUT.validate(cleaned_rut):
            raise InvalidRUTException(raw_rut)

        person = self.get_by_rut(cleaned_rut)
        created_new = False
        if not person:
            created_new = True
            person = Person(
                rut=cleaned_rut,
                first_name=str(payload.get("first_name") or "Nombre").strip(),
                last_name=str(payload.get("last_name") or "Apellido").strip(),
                second_last_name=str(payload.get("second_last_name")).strip() if payload.get("second_last_name") else None,
                email=str(payload.get("email") or f"{cleaned_rut.lower()}@sanbao.cl").lower().strip(),
                phone=payload.get("phone"),
                address=payload.get("address"),
                city=payload.get("city"),
                is_active=True,
            )
            self.db.add(person)
            self.db.commit()
            self.db.refresh(person)
        else:
            # Enriquecer sin sobrescribir destructivamente
            for field in ("phone", "address", "city", "second_last_name"):
                if payload.get(field) and not getattr(person, field):
                    setattr(person, field, payload.get(field))
            if payload.get("email") and not person.email:
                person.email = str(payload["email"]).lower().strip()
            self.db.commit()
            self.db.refresh(person)

        # Si solicita activar o actualizar rol de PROVEEDOR sobre la misma identidad maestra
        if payload.get("enable_supplier") or payload.get("role") == "PROVEEDOR":
            supplier = (
                self.db.query(Supplier)
                .filter(
                    (Supplier.person_id == person.id) | (Supplier.rut == cleaned_rut),
                    Supplier.deleted_at.is_(None),
                )
                .first()
            )
            if not supplier:
                supplier = Supplier(
                    person_id=person.id,
                    company_id=payload.get("company_id"),
                    rut=cleaned_rut,
                    business_name=payload.get("business_name") or person.full_name,
                    trade_category=payload.get("trade_category") or "INSUMOS_CLINICOS",
                    tax_activity=payload.get("tax_activity"),
                    contact_email=payload.get("email") or person.email,
                    contact_phone=payload.get("phone") or person.phone,
                    default_cost_center_code=payload.get("default_cost_center_code"),
                    is_active=True,
                )
                self.db.add(supplier)
                self.db.commit()

        result = self.get_identity_360_by_rut(cleaned_rut)
        result["created_new_identity"] = created_new
        return result

