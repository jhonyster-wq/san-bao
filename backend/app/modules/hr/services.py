import json
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Any, Dict
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import Base
from app.modules.institutional.models.company import Company
from app.modules.institutional.models.person import Person
from app.modules.hr.models import (
    HREmployee,
    HRContract,
    HRLeaveRequest,
    HRFeeReceipt,
    HRPayroll,
    HRLaborDocument,
    HRAttendanceRecord,
    EmployeeType,
    EmployeeStatus,
    LeaveType,
    LeaveStatus,
    FeeReceiptStatus,
    PayrollStatus,
    ContractStatus,
    ContractType,
)
from app.modules.hr.schemas import (
    HREmployeeCreate,
    HRContractCreate,
    HRLeaveRequestCreate,
    HRFeeReceiptCreate,
    HRPayrollCreate,
)


AFP_RATES: Dict[str, Decimal] = {
    "HABITAT": Decimal("11.27"),
    "PROVIDA": Decimal("11.45"),
    "CAPITAL": Decimal("11.44"),
    "CUPRUM": Decimal("11.44"),
    "MODELO": Decimal("10.58"),
    "PLANVITAL": Decimal("11.16"),
    "UNO": Decimal("10.49"),
}

EMPLOYER_SIS_PCT = Decimal("1.49")       # Seguro de Invalidez y Sobrevivencia (Empleador)
EMPLOYER_MUTUAL_PCT = Decimal("0.93")    # Seguro Accidentes del Trabajo Ley 16.744 (Mutual/ACHS)
EMPLOYER_AFC_INDEF_PCT = Decimal("2.40") # AFC Empleador Contrato Indefinido
EMPLOYER_AFC_FIXED_PCT = Decimal("3.00") # AFC Empleador Contrato Plazo Fijo
WORKER_AFC_INDEF_PCT = Decimal("0.60")   # AFC Trabajador Contrato Indefinido


class HRService:
    @staticmethod
    def create_employee(db: Session, data: HREmployeeCreate) -> HREmployee:
        existing = db.query(HREmployee).filter(
            HREmployee.employee_number == data.employee_number
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un colaborador con el número '{data.employee_number}'."
            )

        employee = HREmployee(
            company_id=str(data.company_id),
            person_id=str(data.person_id),
            employee_number=data.employee_number,
            job_title=data.job_title,
            department=data.department,
            employee_type=data.employee_type,
            hire_date=data.hire_date,
            termination_date=data.termination_date,
            notes=data.notes,
            status=EmployeeStatus.ACTIVE,
        )
        db.add(employee)
        db.commit()
        db.refresh(employee)
        return employee

    @staticmethod
    def get_employees(db: Session, company_id: Optional[str] = None) -> List[HREmployee]:
        query = db.query(HREmployee).filter(HREmployee.is_active == True)
        if company_id:
            query = query.filter(HREmployee.company_id == str(company_id))
        return query.all()

    @staticmethod
    def get_employee_by_id(db: Session, employee_id: UUID) -> HREmployee:
        emp = db.query(HREmployee).filter(HREmployee.id == employee_id).first()
        if not emp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Colaborador no encontrado.")
        return emp

    @staticmethod
    def create_contract(db: Session, data: HRContractCreate) -> HRContract:
        HRService.get_employee_by_id(db, data.employee_id)

        active_contracts = db.query(HRContract).filter(
            HRContract.employee_id == data.employee_id,
            HRContract.status == ContractStatus.ACTIVE
        ).all()
        for c in active_contracts:
            c.status = ContractStatus.EXPIRED

        contract = HRContract(
            employee_id=data.employee_id,
            contract_type=data.contract_type,
            start_date=data.start_date,
            end_date=data.end_date,
            base_salary=data.base_salary,
            hourly_rate=data.hourly_rate,
            clinical_commission_pct=data.clinical_commission_pct,
            weekly_hours=data.weekly_hours,
            afp_name=data.afp_name,
            health_system=data.health_system,
            health_quote_pct=data.health_quote_pct,
            status=ContractStatus.ACTIVE,
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def request_leave(db: Session, data: HRLeaveRequestCreate) -> HRLeaveRequest:
        HRService.get_employee_by_id(db, data.employee_id)
        leave = HRLeaveRequest(
            employee_id=data.employee_id,
            leave_type=data.leave_type,
            start_date=data.start_date,
            end_date=data.end_date,
            days_count=data.days_count,
            reason=data.reason,
            status=LeaveStatus.PENDING,
        )
        db.add(leave)
        db.commit()
        db.refresh(leave)
        return leave

    @staticmethod
    def approve_leave(db: Session, leave_id: UUID, approver_user_id: Any) -> HRLeaveRequest:
        leave = db.query(HRLeaveRequest).filter(HRLeaveRequest.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud de permiso no encontrada.")
        leave.status = LeaveStatus.APPROVED
        leave.approved_by = str(approver_user_id) if approver_user_id else None
        db.commit()
        db.refresh(leave)
        return leave

    @staticmethod
    def issue_fee_receipt(db: Session, data: HRFeeReceiptCreate) -> HRFeeReceipt:
        """Cálculo y registro de Boleta de Honorarios con retención legal SII vigente."""
        HRService.get_employee_by_id(db, data.employee_id)

        rate = data.retention_rate / Decimal("100.00")
        retention = (data.gross_amount * rate).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)
        net = data.gross_amount - retention

        receipt = HRFeeReceipt(
            company_id=str(data.company_id),
            employee_id=data.employee_id,
            receipt_number=data.receipt_number,
            issue_date=data.issue_date,
            period_month=data.period_month,
            period_year=data.period_year,
            description=data.description,
            gross_amount=data.gross_amount,
            retention_rate=data.retention_rate,
            retention_amount=retention,
            net_amount=net,
            status=FeeReceiptStatus.APPROVED,
        )
        db.add(receipt)
        db.commit()
        db.refresh(receipt)
        return receipt

    @staticmethod
    def calculate_and_generate_payroll(db: Session, data: HRPayrollCreate) -> HRPayroll:
        """Calcula y emite liquidación de remuneración mensual conforme al Código del Trabajo de Chile."""
        contract = db.query(HRContract).filter(HRContract.id == data.contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contrato no encontrado.")

        base = data.base_salary if data.base_salary is not None else contract.base_salary

        gratuity = min(
            (base * Decimal("0.25")).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP),
            Decimal("190000.00")
        )

        taxable_salary = base + gratuity + data.bonuses + data.overtime_amount
        total_earnings = taxable_salary + data.non_taxable_allowances

        afp_rate = AFP_RATES.get((contract.afp_name or "PROVIDA").upper(), Decimal("11.45")) / Decimal("100.00")
        pension = (taxable_salary * afp_rate).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

        health_rate = (contract.health_quote_pct or Decimal("7.00")) / Decimal("100.00")
        health = (taxable_salary * health_rate).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

        afc = Decimal("0.00")
        if contract.contract_type == ContractType.INDEFINITE:
            afc = (taxable_salary * Decimal("0.006")).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

        taxable_base_for_tax = taxable_salary - (pension + health + afc)
        income_tax = Decimal("0.00")
        if taxable_base_for_tax > Decimal("900000.00"):
            income_tax = ((taxable_base_for_tax - Decimal("900000.00")) * Decimal("0.04")).quantize(
                Decimal("1.00"), rounding=ROUND_HALF_UP
            )

        total_deductions = pension + health + afc + income_tax
        net_salary = total_earnings - total_deductions

        payroll = HRPayroll(
            company_id=str(data.company_id),
            employee_id=data.employee_id,
            contract_id=data.contract_id,
            period_month=data.period_month,
            period_year=data.period_year,
            worked_days=data.worked_days,
            base_salary=base,
            legal_gratuity=gratuity,
            bonuses=data.bonuses,
            overtime_amount=data.overtime_amount,
            gross_taxable_salary=taxable_salary,
            non_taxable_allowances=data.non_taxable_allowances,
            total_earnings=total_earnings,
            pension_deduction=pension,
            health_deduction=health,
            unemployment_insurance=afc,
            income_tax=income_tax,
            other_deductions=Decimal("0.00"),
            total_deductions=total_deductions,
            net_salary=net_salary,
            status=PayrollStatus.APPROVED,
        )
        db.add(payroll)
        db.commit()
        db.refresh(payroll)
        return payroll


class HRHubService:
    """
    Servicio integral para el Módulo 4: Personas & RRHH de Holding San Bao.
    Cubre las 9 áreas funcionales requeridas:
    1. Registro de trabajadores y colaboradores
    2. Administración de contratos
    3. Control de documentación laboral
    4. Registro de asistencia y permisos
    5. Gestión de honorarios (BHE SII)
    6. Remuneraciones y liquidaciones
    7. Información previsional (AFP, Fonasa/Isapre, AFC, SIS, Mutual, Previred)
    8. Administración de docentes y profesionales
    9. Reportes de costos de personal
    """

    def __init__(self, db: Session):
        self.db = db

    def _ensure_tables(self) -> None:
        try:
            bind = self.db.get_bind()
            Base.metadata.create_all(bind=bind, tables=[HRLaborDocument.__table__, HRAttendanceRecord.__table__])
        except Exception:
            pass

    def _get_instituto_and_clinica(self):
        companies = self.db.query(Company).all()
        instituto = next(
            (c for c in companies if "77123456" in (c.rut or "").replace(".", "") or "instituto" in (c.legal_name or "").lower()),
            None,
        )
        clinica = next(
            (c for c in companies if "76987654" in (c.rut or "").replace(".", "") or "clínic" in (c.legal_name or "").lower() or "clinic" in (c.legal_name or "").lower()),
            None,
        )
        if not instituto and companies:
            instituto = companies[0]
        if not clinica and companies:
            clinica = companies[-1]
        return instituto, clinica

    def _resolve_companies(self, company_filter: Optional[str] = None) -> List[Company]:
        companies = self.db.query(Company).filter(Company.is_active == True).all()
        if not company_filter or company_filter == "consolidated":
            return companies
        cf = company_filter.lower().strip()
        matched = []
        for c in companies:
            if (
                c.id == company_filter
                or cf in (c.rut or "").lower()
                or (cf == "instituto" and ("instituto" in c.legal_name.lower() or "77123456" in c.rut.replace(".", "")))
                or (cf == "clinica" and ("clínic" in c.legal_name.lower() or "clinic" in c.legal_name.lower() or "76987654" in c.rut.replace(".", "")))
            ):
                matched.append(c)
        return matched if matched else companies

    def _find_or_create_person(
        self,
        rut: str,
        full_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
    ) -> Person:
        clean_rut = rut.replace(".", "").strip().upper()
        person = (
            self.db.query(Person)
            .filter((Person.rut == clean_rut) | (Person.rut == rut.strip()))
            .first()
        )
        if person:
            if email and not person.email:
                person.email = email
            if phone and not person.phone:
                person.phone = phone
            return person

        parts = (full_name or "Colaborador San Bao").strip().split()
        first_name = parts[0] if parts else "Nombre"
        last_name = parts[1] if len(parts) > 1 else "Apellido"
        second_last_name = " ".join(parts[2:]) if len(parts) > 2 else None

        person = Person(
            rut=clean_rut,
            first_name=first_name,
            last_name=last_name,
            second_last_name=second_last_name,
            email=email or f"{first_name.lower()}.{last_name.lower()}@sanbao.cl",
            phone=phone or "+56 9 8000 0000",
            address=address or "Av. Providencia 2250, Providencia, Santiago",
            is_active=True,
        )
        self.db.add(person)
        self.db.flush()
        return person

    def _parse_employee_meta(self, emp: HREmployee) -> Dict[str, Any]:
        """Extrae metadatos extendidos (especialidad, registro SIS Minsal, cátedras, box clínico) desde notes o defaults."""
        default_meta: Dict[str, Any] = {
            "specialty": "Medicina Tradicional China Clásica",
            "minsal_sis_registry": "SIS-MTC-44210",
            "academic_degree": "Magíster en Medicina Tradicional China & Acupuntura",
            "assigned_courses": ["Diplomado en Medicina Tradicional China y Acupuntura"],
            "pedagogical_hours_week": 12,
            "clinical_box": "Box Clínico 1 - Acupuntura",
            "monthly_patients": 42,
            "evaluation_score": 4.9,
            "modality": "Presencial",
            "emergency_contact": "+56 9 9400 1122",
            "bank_info": "Banco de Chile • Cta. Corriente",
        }
        emp_num = emp.employee_number or ""
        if "DOC-2026-001" in emp_num:
            default_meta.update({
                "specialty": "Fitoterapia Clásica China (Shang Han Lun) & Diagnóstico MTC",
                "minsal_sis_registry": "SIS-ACU-19842 (MINSAL Dto. 42)",
                "academic_degree": "Dra. en Medicina Tradicional China (Universidad de Medicina China de Nanjing)",
                "assigned_courses": [
                    "Diplomado en Medicina Tradicional China y Acupuntura",
                    "Diplomado Clínico en Fitoterapia Clásica China",
                ],
                "pedagogical_hours_week": 22,
                "clinical_box": "Sala Magistral Laozi / Box Fitoterapia",
                "monthly_patients": 28,
                "evaluation_score": 4.95,
            })
        elif "DOC-2026-002" in emp_num:
            default_meta.update({
                "specialty": "Pulsología Clásica, Acupuntura Distal y Masaje Tuina Clínico",
                "minsal_sis_registry": "SIS-ACU-22109 (MINSAL Dto. 42)",
                "academic_degree": "Licenciado en Medicina China y Tuina (Beijing University of Chinese Medicine)",
                "assigned_courses": [
                    "Diplomado en Medicina Tradicional China y Acupuntura",
                    "Curso Intensivo de Masaje Tuina Clínico",
                ],
                "pedagogical_hours_week": 18,
                "clinical_box": "Aula Práctica Tuina / Box 3",
                "monthly_patients": 36,
                "evaluation_score": 4.92,
            })
        elif "DOC-2026-003" in emp_num:
            default_meta.update({
                "specialty": "Qigong Médico (Neigong), Moxibustión Japón/China y Auriculoterapia",
                "minsal_sis_registry": "SIS-ACU-31054 (MINSAL Dto. 42)",
                "academic_degree": "Especialista en Qigong Médico y Acupuntura Clásica",
                "assigned_courses": [
                    "Curso de Formación en Qigong Médico y Neigong",
                    "Seminario Clínico de Auriculoterapia y Moxibustión",
                ],
                "pedagogical_hours_week": 14,
                "clinical_box": "Salón Daoyin / Box 4",
                "monthly_patients": 24,
                "evaluation_score": 4.88,
            })
        elif "CLI-2026-001" in emp_num:
            default_meta.update({
                "specialty": "Acupuntura Neurofuncional, Manejo del Dolor y Rehabilitación Integrativa",
                "minsal_sis_registry": "SIS-ACU-15408 (MINSAL Dto. 42)",
                "academic_degree": "Kinesiólogo & Acupunturista Acreditado MINSAL",
                "assigned_courses": ["Supervisión de Internado Clínico Acupuntura"],
                "pedagogical_hours_week": 8,
                "clinical_box": "Box Clínico 1 (Dirección Clínica)",
                "monthly_patients": 85,
                "evaluation_score": 4.96,
            })
        elif "CLI-2026-002" in emp_num:
            default_meta.update({
                "specialty": "Ginecología Integrativa MTC, Fertilidad, Moxibustión y Ventosas",
                "minsal_sis_registry": "SIS-ACU-28940 (MINSAL Dto. 42)",
                "academic_degree": "Matrona & Especialista en Acupuntura Obstétrica y Ginecológica",
                "assigned_courses": ["Taller Clínico Ginecología en MTC"],
                "pedagogical_hours_week": 6,
                "clinical_box": "Box Clínico 2 (Salud Integrativa Mujer)",
                "monthly_patients": 74,
                "evaluation_score": 4.91,
            })
        elif "ADM-2026-001" in emp_num:
            default_meta.update({
                "specialty": "Atención de Pacientes, Agenda Médica, Recaudación DTE y Convenios",
                "minsal_sis_registry": "N/A (Estamento Administrativo)",
                "academic_degree": "Técnico de Nivel Superior en Administración de Salud",
                "assigned_courses": [],
                "pedagogical_hours_week": 0,
                "clinical_box": "Recepción Central Clínica San Bao",
                "monthly_patients": 0,
                "evaluation_score": 4.85,
            })
        elif "ADM-2026-002" in emp_num:
            default_meta.update({
                "specialty": "Coordinación Académica, Admisión, Registro Curricular y SENCE",
                "minsal_sis_registry": "N/A (Gestión Académica)",
                "academic_degree": "Ingeniero en Administración educacional",
                "assigned_courses": [],
                "pedagogical_hours_week": 0,
                "clinical_box": "Oficina Coordinación Académica",
                "monthly_patients": 0,
                "evaluation_score": 4.90,
            })

        if emp.notes:
            try:
                parsed = json.loads(emp.notes)
                if isinstance(parsed, dict):
                    default_meta.update(parsed)
            except Exception:
                default_meta["custom_notes"] = emp.notes
        return default_meta

    def ensure_sample_hr_data(self) -> None:
        """Asegura datos completos en las 9 dimensiones de Personas & RRHH."""
        self._ensure_tables()
        from app.modules.finance.services.finance_hub_service import FinanceHubService
        try:
            FinanceHubService(self.db).ensure_sample_finance_data()
        except Exception:
            pass

        instituto, clinica = self._get_instituto_and_clinica()
        if not instituto or not clinica:
            return

        today = date.today()

        # Asegurar al menos 7 colaboradores cubriendo todos los perfiles de ambas sociedades SpA
        extra_staff = [
            {
                "company": instituto,
                "rut": "15987412-3",
                "name": "Sofía Lin Zhang",
                "email": "sofia.lin@sanbao.cl",
                "phone": "+56 9 8412 3390",
                "emp_num": "DOC-2026-003",
                "job_title": "Docente Cátedra Qigong Médico, Moxibustión y Práctica Clínica",
                "department": "Cuerpo Docente MTC",
                "emp_type": EmployeeType.TEACHER,
                "contract_type": ContractType.FEE_HONORARIOS,
                "hire_date": date(2025, 4, 1),
                "base_salary": Decimal("0"),
                "hourly_rate": Decimal("30000"),
                "commission_pct": Decimal("0"),
                "weekly_hours": 14,
                "afp": "CUPRUM",
                "health": "ISAPRE CONSALUD",
                "health_pct": Decimal("7.20"),
                "bonuses": Decimal("0"),
                "allowances": Decimal("0"),
                "bhe_number": "BHE-2026-0089",
                "bhe_gross": Decimal("540000"),
                "bhe_desc": "Docencia Curso Qigong Médico y Supervisión Práctica Moxibustión (18 hrs)",
            },
            {
                "company": clinica,
                "rut": "17456890-1",
                "name": "Javiera Paz Fuenzalida Ríos",
                "email": "javiera.fuenzalida@sanbao.cl",
                "phone": "+56 9 9345 6712",
                "emp_num": "CLI-2026-002",
                "job_title": "Terapeuta Especialista Acupuntura Ginecológica y Moxibustión",
                "department": "Equipo Clínico Terapéutico",
                "emp_type": EmployeeType.PRACTITIONER,
                "contract_type": ContractType.INDEFINITE,
                "hire_date": date(2025, 5, 1),
                "base_salary": Decimal("1150000"),
                "hourly_rate": Decimal("0"),
                "commission_pct": Decimal("35.00"),
                "weekly_hours": 40,
                "afp": "HABITAT",
                "health": "ISAPRE BANMEDICA",
                "health_pct": Decimal("7.40"),
                "bonuses": Decimal("145000"),
                "allowances": Decimal("80000"),
            },
            {
                "company": instituto,
                "rut": "16890234-5",
                "name": "Sebastián Andrés Araya Rojas",
                "email": "coordinacion.academica@sanbao.cl",
                "phone": "+56 9 8711 2233",
                "emp_num": "ADM-2026-002",
                "job_title": "Coordinador Académico, Admisión & Registro Curricular",
                "department": "Dirección Académica",
                "emp_type": EmployeeType.ADMINISTRATIVE,
                "contract_type": ContractType.INDEFINITE,
                "hire_date": date(2025, 3, 1),
                "base_salary": Decimal("980000"),
                "hourly_rate": Decimal("0"),
                "commission_pct": Decimal("0"),
                "weekly_hours": 40,
                "afp": "PROVIDA",
                "health": "FONASA",
                "health_pct": Decimal("7.00"),
                "bonuses": Decimal("75000"),
                "allowances": Decimal("75000"),
            },
        ]

        for s in extra_staff:
            emp = self.db.query(HREmployee).filter(HREmployee.employee_number == s["emp_num"]).first()
            if not emp:
                person = self._find_or_create_person(s["rut"], s["name"], s["email"], s["phone"])
                emp = HREmployee(
                    company_id=s["company"].id,
                    person_id=person.id,
                    employee_number=s["emp_num"],
                    job_title=s["job_title"],
                    department=s["department"],
                    employee_type=s["emp_type"],
                    hire_date=s["hire_date"],
                    status=EmployeeStatus.ACTIVE,
                )
                self.db.add(emp)
                self.db.flush()

                contract = HRContract(
                    employee_id=emp.id,
                    contract_type=s["contract_type"],
                    start_date=s["hire_date"],
                    base_salary=s["base_salary"],
                    hourly_rate=s["hourly_rate"],
                    clinical_commission_pct=s["commission_pct"],
                    weekly_hours=s["weekly_hours"],
                    afp_name=s["afp"],
                    health_system=s["health"],
                    health_quote_pct=s["health_pct"],
                    status=ContractStatus.ACTIVE,
                    document_url=f"/static/hr/contracts/contrato_{s['emp_num'].lower()}.pdf",
                )
                self.db.add(contract)
                self.db.flush()

                if s["contract_type"] == ContractType.INDEFINITE and s["base_salary"] > 0:
                    base = s["base_salary"]
                    gratuity = min((base * Decimal("0.25")).quantize(Decimal("1"), rounding=ROUND_HALF_UP), Decimal("190000"))
                    taxable = base + gratuity + s["bonuses"]
                    total_earnings = taxable + s["allowances"]
                    afp_rate = AFP_RATES.get(s["afp"], Decimal("11.45")) / Decimal("100")
                    pension = (taxable * afp_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    health_ded = (taxable * (s["health_pct"] / Decimal("100"))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    afc = (taxable * Decimal("0.006")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    tax_base = taxable - (pension + health_ded + afc)
                    inc_tax = ((tax_base - Decimal("900000")) * Decimal("0.04")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) if tax_base > Decimal("900000") else Decimal("0")
                    tot_ded = pension + health_ded + afc + inc_tax
                    net_sal = total_earnings - tot_ded

                    self.db.add(
                        HRPayroll(
                            company_id=s["company"].id,
                            employee_id=emp.id,
                            contract_id=contract.id,
                            period_month=today.month,
                            period_year=today.year,
                            worked_days=30,
                            base_salary=base,
                            legal_gratuity=gratuity,
                            bonuses=s["bonuses"],
                            overtime_amount=Decimal("0"),
                            gross_taxable_salary=taxable,
                            non_taxable_allowances=s["allowances"],
                            total_earnings=total_earnings,
                            pension_deduction=pension,
                            health_deduction=health_ded,
                            unemployment_insurance=afc,
                            income_tax=inc_tax,
                            other_deductions=Decimal("0"),
                            total_deductions=tot_ded,
                            net_salary=net_sal,
                            status=PayrollStatus.PAID if s["emp_num"] == "ADM-2026-002" else PayrollStatus.APPROVED,
                            payment_date=today if s["emp_num"] == "ADM-2026-002" else None,
                        )
                    )
                elif s.get("bhe_number"):
                    gross = s["bhe_gross"]
                    ret_rate = Decimal("13.75")
                    ret_amt = (gross * ret_rate / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    self.db.add(
                        HRFeeReceipt(
                            company_id=s["company"].id,
                            employee_id=emp.id,
                            receipt_number=s["bhe_number"],
                            issue_date=today - timedelta(days=2),
                            period_month=today.month,
                            period_year=today.year,
                            description=s["bhe_desc"],
                            gross_amount=gross,
                            retention_rate=ret_rate,
                            retention_amount=ret_amt,
                            net_amount=gross - ret_amt,
                            status=FeeReceiptStatus.PAID,
                            payment_date=today - timedelta(days=1),
                        )
                    )

        self.db.commit()

        # Sembrar Documentación Laboral (HRLaborDocument) si está vacía
        all_employees = self.db.query(HREmployee).filter(HREmployee.is_active == True).all()
        if self.db.query(HRLaborDocument).count() == 0 and all_employees:
            doc_counter = 1
            for emp in all_employees:
                emp_docs = [
                    (
                        "CONTRATO_FIRMADO",
                        f"Contrato {'de Prestación de Servicios Honorarios' if emp.employee_number in ('DOC-2026-002', 'DOC-2026-003') else 'de Trabajo Indefinido'} Firmado ({emp.employee_number})",
                        emp.hire_date,
                        None,
                        "VIGENTE",
                        "Dirección RRHH San Bao",
                        "Ejemplar firmado electrónicamente y registrado en Dirección del Trabajo (DT).",
                    ),
                    (
                        "ENTREGA_RIOHS",
                        "Comprobante Recepción Reglamento Interno de Orden, Higiene y Seguridad (RIOHS)",
                        emp.hire_date,
                        date(today.year + 1, 12, 31),
                        "VIGENTE",
                        "Prevención de Riesgos",
                        "Incluye protocolo de bioseguridad clínica, manejo de agujas/REAS y Ley Karin N° 21.643.",
                    ),
                    (
                        "AFILIACION_AFP_SALUD",
                        "Certificados de Afiliación Previsional AFP y Fonasa / Isapre Vigentes",
                        emp.hire_date,
                        date(today.year, 12, 31),
                        "VIGENTE",
                        "Unidad de Remuneraciones",
                        "Respaldo para pago electrónico en Previred.",
                    ),
                    (
                        "CERTIFICADO_ANTECEDENTES",
                        "Certificado de Antecedentes para Fines Especiales (Registro Civil)",
                        today - timedelta(days=60),
                        today + timedelta(days=25) if emp.employee_number == "CLI-2026-002" else today + timedelta(days=120),
                        "POR_VENCER" if emp.employee_number == "CLI-2026-002" else "VIGENTE",
                        "Coordinación RRHH",
                        "Renovación semestral exigida para personal docente y clínico.",
                    ),
                ]
                if emp.employee_type in (EmployeeType.TEACHER, EmployeeType.PRACTITIONER):
                    emp_docs.append(
                        (
                            "TITULO_REGISTRO_SIS",
                            "Título Profesional y Certificado Inscripción Superintendencia de Salud (MINSAL Dto. 42)",
                            emp.hire_date,
                            None,
                            "PENDIENTE" if emp.employee_number == "DOC-2026-003" else "VIGENTE",
                            "Dirección Médica / Académica",
                            "Habilitación legal para ejercicio clínico y docencia en Acupuntura y MTC.",
                        )
                    )
                    emp_docs.append(
                        (
                            "ENTREGA_EPP_BIOSEGURIDAD",
                            "Acta de Entrega EPP, Protocolo Cortopunzantes REAS y Vacunación Hepatitis B",
                            emp.hire_date + timedelta(days=3),
                            date(today.year + 1, 6, 30),
                            "VIGENTE",
                            "Dirección Clínica San Bao",
                            "Cumplimiento sanitario SEREMI de Salud RM.",
                        )
                    )
                for dtype, title, iss_date, exp_date, st_doc, ver_by, notes_txt in emp_docs:
                    self.db.add(
                        HRLaborDocument(
                            company_id=emp.company_id,
                            employee_id=emp.id,
                            document_type=dtype,
                            document_code=f"DOC-LAB-2026-{doc_counter:04d}",
                            title=title,
                            issue_date=iss_date,
                            expiry_date=exp_date,
                            status=st_doc,
                            file_url=f"/static/hr/docs/{emp.employee_number.lower()}_{dtype.lower()}.pdf",
                            verified_by=ver_by if st_doc != "PENDIENTE" else None,
                            notes=notes_txt,
                        )
                    )
                    doc_counter += 1
            self.db.commit()

        # Sembrar Registro de Asistencia (HRAttendanceRecord) y Permisos/Vacaciones (HRLeaveRequest)
        if self.db.query(HRAttendanceRecord).count() == 0 and all_employees:
            for emp in all_employees:
                is_part_time_teacher = emp.employee_number in ("DOC-2026-002", "DOC-2026-003")
                for day_offset in range(3):
                    att_date = today - timedelta(days=day_offset)
                    if is_part_time_teacher:
                        shift = "Bloque Docente Vespertino (18:00 - 21:30)"
                        c_in = "17:55"
                        c_out = "21:35"
                        w_hrs = Decimal("3.50")
                        ot_hrs = Decimal("0.00")
                        late = 0
                        st_att = "PRESENTE"
                        mod = "AULA_DOCENTE"
                    elif emp.employee_type == EmployeeType.PRACTITIONER:
                        shift = "Jornada Clínica Completa (09:00 - 18:00)"
                        late = 12 if (day_offset == 1 and emp.employee_number == "CLI-2026-002") else 0
                        c_in = "09:12" if late > 0 else "08:54"
                        c_out = "18:30" if day_offset == 0 else "18:05"
                        w_hrs = Decimal("8.00")
                        ot_hrs = Decimal("0.50") if day_offset == 0 else Decimal("0.00")
                        st_att = "ATRASO" if late > 0 else "PRESENTE"
                        mod = "CLINICA_BOX"
                    else:
                        shift = "Jornada Administrativa / Directiva (09:00 - 18:00)"
                        c_in = "08:57"
                        c_out = "18:10"
                        w_hrs = Decimal("8.00")
                        ot_hrs = Decimal("1.00") if (day_offset == 0 and emp.employee_number == "ADM-2026-001") else Decimal("0.00")
                        late = 0
                        st_att = "PRESENTE"
                        mod = "PRESENCIAL"

                    self.db.add(
                        HRAttendanceRecord(
                            company_id=emp.company_id,
                            employee_id=emp.id,
                            attendance_date=att_date,
                            shift_name=shift,
                            check_in=c_in,
                            check_out=c_out,
                            worked_hours=w_hrs,
                            overtime_hours=ot_hrs,
                            late_minutes=late,
                            status=st_att,
                            modality=mod,
                            notes="Marcaje biométrico / reloj control digital verificado." if late == 0 else "Atraso justificado por contingencia transporte Metro.",
                        )
                    )
            self.db.commit()

        if self.db.query(HRLeaveRequest).count() == 0 and all_employees:
            emp_by_num = {e.employee_number: e for e in all_employees}
            sample_leaves = [
                (
                    emp_by_num.get("DOC-2026-001"),
                    LeaveType.ADMINISTRATIVE,
                    today + timedelta(days=5),
                    today + timedelta(days=6),
                    2,
                    "Participación como expositora principal en Congreso Internacional de Medicina China Integrativa.",
                    LeaveStatus.APPROVED,
                ),
                (
                    emp_by_num.get("CLI-2026-001"),
                    LeaveType.VACATION,
                    today + timedelta(days=18),
                    today + timedelta(days=24),
                    5,
                    "Solicitud de 5 días hábiles de Feriado Legal Anual programado con Dirección Clínica.",
                    LeaveStatus.APPROVED,
                ),
                (
                    emp_by_num.get("CLI-2026-002"),
                    LeaveType.MEDICAL_LEAVE,
                    today - timedelta(days=12),
                    today - timedelta(days=9),
                    4,
                    "Licencia Médica Electrónica LME Folio #39481022 (Reposo médico 4 días).",
                    LeaveStatus.APPROVED,
                ),
                (
                    emp_by_num.get("ADM-2026-001"),
                    LeaveType.ADMINISTRATIVE,
                    today + timedelta(days=3),
                    today + timedelta(days=3),
                    1,
                    "Permiso administrativo con goce de sueldo por trámites personales y bancarios.",
                    LeaveStatus.PENDING,
                ),
            ]
            for emp_obj, ltype, sdate, edate, dcount, reason_txt, lstatus in sample_leaves:
                if emp_obj:
                    self.db.add(
                        HRLeaveRequest(
                            employee_id=emp_obj.id,
                            leave_type=ltype,
                            start_date=sdate,
                            end_date=edate,
                            days_count=dcount,
                            reason=reason_txt,
                            status=lstatus,
                        )
                    )
            self.db.commit()

    def _build_contract_document_text(self, emp: HREmployee, contract: HRContract, comp: Optional[Company]) -> str:
        comp_name = comp.legal_name if comp else "Holding San Bao SpA"
        comp_rut = comp.rut if comp else "77.123.456-8"
        person = emp.person
        worker_name = person.full_name if person else emp.employee_number
        worker_rut = person.rut if person else "S/R"
        worker_address = (person.address if person and person.address else "Av. Providencia 2250, Providencia, Santiago")
        ctype = contract.contract_type.value if hasattr(contract.contract_type, "value") else str(contract.contract_type)

        if ctype == "FEE_HONORARIOS":
            return (
                f"CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES Y DOCENTES A HONORARIOS\n"
                f"===========================================================================\n\n"
                f"En Santiago de Chile, a {contract.start_date.strftime('%d/%m/%Y')}, entre {comp_name}, "
                f"RUT {comp_rut}, domiciliada en Av. Providencia 2120, comuna de Providencia, Santiago, en adelante "
                f"\"LA INSTITUCIÓN\", y don/doña {worker_name}, RUT {worker_rut}, domiciliado(a) en {worker_address}, "
                f"en adelante \"EL/LA PROFESIONAL\", se ha convenido el siguiente Contrato de Prestación de Servicios a Honorarios:\n\n"
                f"PRIMERO (OBJETO DEL SERVICIO): El/La Profesional prestará servicios especializados como \"{emp.job_title}\" "
                f"adscrito al departamento de \"{emp.department}\", desarrollando cátedras académicas y/o prestaciones clínicas "
                f"con una dedicación referencial de {contract.weekly_hours} horas semanales.\n\n"
                f"SEGUNDO (HONORARIOS Y RETENCIÓN SII): La Institución pagará al Profesional una tarifa bruta de "
                f"${int(contract.hourly_rate or 0):,} CLP por hora cronológica efectivamente realizada"
                f"{f', más una comisión clínica del {float(contract.clinical_commission_pct):.1f}% sobre atenciones realizadas' if float(contract.clinical_commission_pct or 0) > 0 else ''}. "
                f"El pago se efectuará previa emisión de Boleta de Honorarios Electrónica (BHE) ante el Servicio de Impuestos Internos (SII), "
                f"aplicándose la retención legal vigente de Segunda Categoría (13.75%).\n\n"
                f"TERCERO (VIGENCIA Y CONFIDENCIALIDAD): El presente convenio rige desde el {contract.start_date.strftime('%d/%m/%Y')} "
                f"{'hasta el ' + contract.end_date.strftime('%d/%m/%Y') if contract.end_date else 'con carácter indefinido mientras subsistan las necesidades académicas/clínicas'}, "
                f"obligándose el Profesional al estricto cumplimiento de los protocolos éticos, clínicos y de protección de datos de pacientes y alumnos de San Bao."
            )
        else:
            return (
                f"CONTRATO INDIVIDUAL DE TRABAJO ({'INDEFINIDO' if ctype == 'INDEFINITE' else 'PLAZO FIJO'})\n"
                f"===========================================================================\n\n"
                f"En Santiago de Chile, a {contract.start_date.strftime('%d/%m/%Y')}, entre {comp_name}, "
                f"RUT {comp_rut}, representada legalmente por su Dirección Ejecutiva, domiciliada en Av. Providencia 2120, Providencia, "
                f"en adelante \"EL EMPLEADOR\", y don/doña {worker_name}, RUT {worker_rut}, domiciliado(a) en {worker_address}, "
                f"en adelante \"EL TRABAJADOR\", se celebra el presente Contrato Individual de Trabajo regido por el Código del Trabajo de Chile:\n\n"
                f"PRIMERO (CARGO Y FUNCIONES): El Trabajador se desempeñará en el cargo de \"{emp.job_title}\" en la unidad/departamento "
                f"de \"{emp.department}\" de {comp_name}.\n\n"
                f"SEGUNDO (JORNADA DE TRABAJO - LEY N° 21.561): La jornada ordinaria de trabajo será de {contract.weekly_hours} horas semanales, "
                f"distribuidas de lunes a viernes, en conformidad con la gradualidad de la Ley N° 21.561 (Ley de 40 Horas).\n\n"
                f"TERCERO (REMUNERACIÓN Y BENEFICIOS): El Empleador pagará al Trabajador un Sueldo Base Mensual de "
                f"${int(contract.base_salary or 0):,} CLP, más Gratificación Legal Mensual conforme al Artículo 50 del Código del Trabajo "
                f"(25% de lo devengado con tope de 4,75 Ingresos Mínimos Mensuales anualizados)"
                f"{f', más comisión clínica variable de {float(contract.clinical_commission_pct):.1f}%' if float(contract.clinical_commission_pct or 0) > 0 else ''}.\n\n"
                f"CUARTO (AFILIACIÓN PREVISIONAL): El Trabajador declara encontrarse afiliado a AFP {contract.afp_name or 'PROVIDA'} y "
                f"al sistema de salud {contract.health_system or 'FONASA'} ({float(contract.health_quote_pct or 7):.2f}%), cuyas cotizaciones legales "
                f"serán enteradas mensualmente a través del portal Previred.\n\n"
                f"QUINTO (DURACIÓN): El presente contrato tendrá vigencia {'INDEFINIDA' if ctype == 'INDEFINITE' else 'a PLAZO FIJO'} a contar del "
                f"{contract.start_date.strftime('%d/%m/%Y')}{' y hasta el ' + contract.end_date.strftime('%d/%m/%Y') if contract.end_date else ''}."
            )

    def get_hr_hub_overview(
        self,
        company_filter: Optional[str] = "consolidated",
        search: Optional[str] = None,
        employee_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retorna el estado integral del Módulo 4: Personas & RRHH con las 9 áreas requeridas.
        """
        self.ensure_sample_hr_data()

        companies = self._resolve_companies(company_filter)
        company_ids = [c.id for c in companies]
        company_map = {c.id: c for c in self.db.query(Company).all()}

        # 1. Colaboradores
        emp_query = (
            self.db.query(HREmployee)
            .filter(HREmployee.company_id.in_(company_ids), HREmployee.is_active == True)
            .order_by(HREmployee.employee_number.asc())
        )
        if employee_type and employee_type != "ALL":
            try:
                emp_query = emp_query.filter(HREmployee.employee_type == EmployeeType(employee_type))
            except Exception:
                pass

        all_emps = emp_query.all()
        if search and search.strip():
            q = search.strip().lower()
            filtered_emps = []
            for e in all_emps:
                p = e.person
                p_name = (p.full_name if p else "").lower()
                p_rut = (p.rut if p else "").lower()
                if (
                    q in p_name
                    or q in p_rut
                    or q in (e.employee_number or "").lower()
                    or q in (e.job_title or "").lower()
                    or q in (e.department or "").lower()
                ):
                    filtered_emps.append(e)
            all_emps = filtered_emps

        emp_ids = [e.id for e in all_emps]
        emp_by_id = {e.id: e for e in all_emps}

        # Cargar contratos, documentos, asistencia, permisos, liquidaciones y BHE
        contracts = (
            self.db.query(HRContract)
            .filter(HRContract.employee_id.in_(emp_ids))
            .order_by(HRContract.start_date.desc())
            .all()
            if emp_ids
            else []
        )
        active_contract_by_emp: Dict[UUID, HRContract] = {}
        for c in contracts:
            if c.employee_id not in active_contract_by_emp or c.status == ContractStatus.ACTIVE:
                active_contract_by_emp[c.employee_id] = c

        labor_docs = (
            self.db.query(HRLaborDocument)
            .filter(HRLaborDocument.employee_id.in_(emp_ids))
            .order_by(HRLaborDocument.issue_date.desc())
            .all()
            if emp_ids
            else []
        )
        docs_by_emp: Dict[UUID, List[HRLaborDocument]] = {}
        for d in labor_docs:
            docs_by_emp.setdefault(d.employee_id, []).append(d)

        attendance_rows = (
            self.db.query(HRAttendanceRecord)
            .filter(HRAttendanceRecord.employee_id.in_(emp_ids))
            .order_by(HRAttendanceRecord.attendance_date.desc())
            .all()
            if emp_ids
            else []
        )
        att_by_emp: Dict[UUID, List[HRAttendanceRecord]] = {}
        for a in attendance_rows:
            att_by_emp.setdefault(a.employee_id, []).append(a)

        leave_rows = (
            self.db.query(HRLeaveRequest)
            .filter(HRLeaveRequest.employee_id.in_(emp_ids))
            .order_by(HRLeaveRequest.start_date.desc())
            .all()
            if emp_ids
            else []
        )

        payroll_rows = (
            self.db.query(HRPayroll)
            .filter(HRPayroll.employee_id.in_(emp_ids))
            .order_by(HRPayroll.period_year.desc(), HRPayroll.period_month.desc())
            .all()
            if emp_ids
            else []
        )
        latest_payroll_by_emp: Dict[UUID, HRPayroll] = {}
        for pr in payroll_rows:
            if pr.employee_id not in latest_payroll_by_emp:
                latest_payroll_by_emp[pr.employee_id] = pr

        bhe_rows = (
            self.db.query(HRFeeReceipt)
            .filter(HRFeeReceipt.employee_id.in_(emp_ids))
            .order_by(HRFeeReceipt.issue_date.desc())
            .all()
            if emp_ids
            else []
        )
        latest_bhe_by_emp: Dict[UUID, HRFeeReceipt] = {}
        for bh in bhe_rows:
            if bh.employee_id not in latest_bhe_by_emp:
                latest_bhe_by_emp[bh.employee_id] = bh

        # Construir lista enriquecida 1: Registro de Trabajadores y Colaboradores
        employees_list = []
        # Construir lista 8: Docentes y Profesionales Clínicos
        teachers_and_practitioners = []
        # Construir lista 7: Información Previsional (Previred)
        previsional_rows = []

        total_previred_worker = Decimal("0")
        total_previred_employer = Decimal("0")
        total_previred_combined = Decimal("0")

        for e in all_emps:
            comp = company_map.get(e.company_id)
            p = e.person
            c = active_contract_by_emp.get(e.id)
            meta = self._parse_employee_meta(e)
            edocs = docs_by_emp.get(e.id, [])
            vigente_docs = sum(1 for d in edocs if d.status == "VIGENTE")
            doc_compliance_pct = round((vigente_docs / len(edocs)) * 100, 1) if edocs else 100.0

            e_att = att_by_emp.get(e.id, [])
            on_time_count = sum(1 for a in e_att if a.status == "PRESENTE")
            attendance_pct = round((on_time_count / len(e_att)) * 100, 1) if e_att else 100.0

            emp_type_val = e.employee_type.value if hasattr(e.employee_type, "value") else str(e.employee_type)
            emp_status_val = e.status.value if hasattr(e.status, "value") else str(e.status)
            ctype_val = (c.contract_type.value if hasattr(c.contract_type, "value") else str(c.contract_type)) if c else "INDEFINITE"

            emp_dict = {
                "id": str(e.id),
                "company_id": e.company_id,
                "company_name": comp.legal_name if comp else "Holding San Bao",
                "company_rut": comp.rut if comp else "",
                "person_id": e.person_id,
                "employee_number": e.employee_number,
                "full_name": p.full_name if p else e.employee_number,
                "rut": p.rut if p else "S/R",
                "email": p.email if p else "",
                "phone": p.phone if p else "",
                "address": p.address if p and p.address else "Av. Providencia 2250, Santiago",
                "job_title": e.job_title,
                "department": e.department,
                "employee_type": emp_type_val,
                "hire_date": e.hire_date.isoformat() if e.hire_date else None,
                "status": emp_status_val,
                "contract_id": str(c.id) if c else None,
                "contract_type": ctype_val,
                "weekly_hours": c.weekly_hours if c else 40,
                "base_salary": float(c.base_salary or 0) if c else 0.0,
                "hourly_rate": float(c.hourly_rate or 0) if c else 0.0,
                "clinical_commission_pct": float(c.clinical_commission_pct or 0) if c else 0.0,
                "afp_name": (c.afp_name or "PROVIDA") if c else "PROVIDA",
                "health_system": (c.health_system or "FONASA") if c else "FONASA",
                "health_quote_pct": float(c.health_quote_pct or 7.0) if c else 7.0,
                "doc_compliance_pct": doc_compliance_pct,
                "docs_total": len(edocs),
                "docs_vigentes": vigente_docs,
                "attendance_pct": attendance_pct,
                "specialty": meta.get("specialty"),
                "minsal_sis_registry": meta.get("minsal_sis_registry"),
                "academic_degree": meta.get("academic_degree"),
                "assigned_courses": meta.get("assigned_courses", []),
                "pedagogical_hours_week": meta.get("pedagogical_hours_week", 0),
                "clinical_box": meta.get("clinical_box"),
                "monthly_patients": meta.get("monthly_patients", 0),
                "evaluation_score": meta.get("evaluation_score", 4.9),
                "bank_info": meta.get("bank_info"),
            }
            employees_list.append(emp_dict)

            # Si es Docente o Profesional Clínico, agregarlo a la nómina especializada (Funcionalidad 8)
            if emp_type_val in ("TEACHER", "PRACTITIONER"):
                pr_latest = latest_payroll_by_emp.get(e.id)
                bh_latest = latest_bhe_by_emp.get(e.id)
                monthly_comp = (
                    float(pr_latest.total_earnings)
                    if pr_latest
                    else (float(bh_latest.gross_amount) if bh_latest else float(c.base_salary if c else 0))
                )
                is_docente = emp_type_val == "TEACHER"
                teachers_and_practitioners.append({
                    **emp_dict,
                    "monthly_compensation_gross": monthly_comp,
                    "remuneration_regime": "Honorarios BHE SII" if ctype_val == "FEE_HONORARIOS" else "Contrato Código del Trabajo",
                    "entity_classification": "DOCENTE (Escuela San Bao SpA)" if is_docente else "TUTOR CLÍNICO (Clínica San Bao SpA)",
                    "financial_entity": "Escuela San Bao SpA (Instituto de Medicina China Clásica SpA)" if is_docente else "Clínica San Bao SpA (Servicios Clínicos San Bao SpA)",
                })

            # Cálculo Previsional detallado (Funcionalidad 7: Información Previsional & Previred)
            if c:
                pr_latest = latest_payroll_by_emp.get(e.id)
                bh_latest = latest_bhe_by_emp.get(e.id)
                afp_name = (c.afp_name or "PROVIDA").upper()
                afp_rate = AFP_RATES.get(afp_name, Decimal("11.45"))
                health_pct = Decimal(str(c.health_quote_pct or "7.00"))

                if ctype_val == "FEE_HONORARIOS":
                    taxable_base = bh_latest.gross_amount if bh_latest else (Decimal(str(c.hourly_rate or 0)) * Decimal(str(c.weekly_hours or 12)) * Decimal("4"))
                    pension_amt = Decimal("0")
                    health_amt = Decimal("0")
                    afc_worker_amt = Decimal("0")
                    afc_employer_amt = Decimal("0")
                    sis_employer_amt = Decimal("0")
                    mutual_employer_amt = Decimal("0")
                    bhe_retention = (taxable_base * Decimal("0.1375")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    regime_label = "Boleta de Honorarios (Cotización Anual Operación Renta SII)"
                else:
                    if pr_latest:
                        taxable_base = pr_latest.gross_taxable_salary
                        pension_amt = pr_latest.pension_deduction
                        health_amt = pr_latest.health_deduction
                        afc_worker_amt = pr_latest.unemployment_insurance
                    else:
                        base_s = Decimal(str(c.base_salary or 0))
                        grat = min((base_s * Decimal("0.25")).quantize(Decimal("1"), rounding=ROUND_HALF_UP), Decimal("190000"))
                        taxable_base = base_s + grat
                        pension_amt = (taxable_base * afp_rate / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                        health_amt = (taxable_base * health_pct / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                        afc_worker_amt = (taxable_base * WORKER_AFC_INDEF_PCT / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) if ctype_val == "INDEFINITE" else Decimal("0")

                    afc_emp_pct = EMPLOYER_AFC_INDEF_PCT if ctype_val == "INDEFINITE" else EMPLOYER_AFC_FIXED_PCT
                    afc_employer_amt = (taxable_base * afc_emp_pct / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    sis_employer_amt = (taxable_base * EMPLOYER_SIS_PCT / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    mutual_employer_amt = (taxable_base * EMPLOYER_MUTUAL_PCT / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    bhe_retention = Decimal("0")
                    regime_label = "Previred Mensual (Régimen General DL 3.500)"

                worker_total = pension_amt + health_amt + afc_worker_amt
                employer_total = afc_employer_amt + sis_employer_amt + mutual_employer_amt
                combined_previred = worker_total + employer_total

                total_previred_worker += worker_total
                total_previred_employer += employer_total
                total_previred_combined += combined_previred

                previsional_rows.append({
                    "employee_id": str(e.id),
                    "contract_id": str(c.id),
                    "employee_number": e.employee_number,
                    "full_name": p.full_name if p else e.employee_number,
                    "rut": p.rut if p else "S/R",
                    "company_name": comp.legal_name if comp else "",
                    "contract_type": ctype_val,
                    "regime_label": regime_label,
                    "afp_name": afp_name,
                    "afp_rate_pct": float(afp_rate),
                    "health_system": c.health_system or "FONASA",
                    "health_quote_pct": float(health_pct),
                    "taxable_base": float(taxable_base),
                    "pension_deduction": float(pension_amt),
                    "health_deduction": float(health_amt),
                    "afc_worker": float(afc_worker_amt),
                    "worker_total_deductions": float(worker_total),
                    "afc_employer": float(afc_employer_amt),
                    "sis_employer": float(sis_employer_amt),
                    "mutual_employer": float(mutual_employer_amt),
                    "employer_total_contributions": float(employer_total),
                    "total_previred_payable": float(combined_previred),
                    "bhe_sii_retention": float(bhe_retention),
                })

        # 2. Administración de Contratos
        contracts_list = []
        for c in contracts:
            e = emp_by_id.get(c.employee_id)
            if not e:
                continue
            comp = company_map.get(e.company_id)
            p = e.person
            ctype_val = c.contract_type.value if hasattr(c.contract_type, "value") else str(c.contract_type)
            cstatus_val = c.status.value if hasattr(c.status, "value") else str(c.status)
            contracts_list.append({
                "id": str(c.id),
                "employee_id": str(e.id),
                "employee_number": e.employee_number,
                "employee_name": p.full_name if p else e.employee_number,
                "employee_rut": p.rut if p else "S/R",
                "job_title": e.job_title,
                "department": e.department,
                "company_id": e.company_id,
                "company_name": comp.legal_name if comp else "",
                "contract_type": ctype_val,
                "start_date": c.start_date.isoformat() if c.start_date else None,
                "end_date": c.end_date.isoformat() if c.end_date else None,
                "weekly_hours": c.weekly_hours,
                "base_salary": float(c.base_salary or 0),
                "hourly_rate": float(c.hourly_rate or 0),
                "clinical_commission_pct": float(c.clinical_commission_pct or 0),
                "afp_name": c.afp_name or "PROVIDA",
                "health_system": c.health_system or "FONASA",
                "health_quote_pct": float(c.health_quote_pct or 7.0),
                "status": cstatus_val,
                "document_url": c.document_url or f"/static/hr/contracts/contrato_{e.employee_number.lower()}.pdf",
                "contract_text": self._build_contract_document_text(e, c, comp),
            })

        # 3. Control de Documentación Laboral
        documents_list = []
        for d in labor_docs:
            e = emp_by_id.get(d.employee_id)
            if not e:
                continue
            comp = company_map.get(e.company_id)
            p = e.person
            documents_list.append({
                "id": str(d.id),
                "company_id": d.company_id,
                "company_name": comp.legal_name if comp else "",
                "employee_id": str(e.id),
                "employee_number": e.employee_number,
                "employee_name": p.full_name if p else e.employee_number,
                "employee_rut": p.rut if p else "S/R",
                "job_title": e.job_title,
                "document_type": d.document_type,
                "document_code": d.document_code,
                "title": d.title,
                "issue_date": d.issue_date.isoformat() if d.issue_date else None,
                "expiry_date": d.expiry_date.isoformat() if d.expiry_date else None,
                "status": d.status,
                "file_url": d.file_url,
                "verified_by": d.verified_by,
                "notes": d.notes,
            })

        # 4. Registro de Asistencia y Permisos
        attendance_list = []
        for a in attendance_rows:
            e = emp_by_id.get(a.employee_id)
            if not e:
                continue
            comp = company_map.get(e.company_id)
            p = e.person
            attendance_list.append({
                "id": str(a.id),
                "company_id": a.company_id,
                "company_name": comp.legal_name if comp else "",
                "employee_id": str(e.id),
                "employee_number": e.employee_number,
                "employee_name": p.full_name if p else e.employee_number,
                "employee_rut": p.rut if p else "S/R",
                "department": e.department,
                "attendance_date": a.attendance_date.isoformat() if a.attendance_date else None,
                "shift_name": a.shift_name,
                "check_in": a.check_in,
                "check_out": a.check_out,
                "worked_hours": float(a.worked_hours or 0),
                "overtime_hours": float(a.overtime_hours or 0),
                "late_minutes": int(a.late_minutes or 0),
                "status": a.status,
                "modality": a.modality,
                "notes": a.notes,
            })

        leaves_list = []
        for lv in leave_rows:
            e = emp_by_id.get(lv.employee_id)
            if not e:
                continue
            comp = company_map.get(e.company_id)
            p = e.person
            ltype_val = lv.leave_type.value if hasattr(lv.leave_type, "value") else str(lv.leave_type)
            lstatus_val = lv.status.value if hasattr(lv.status, "value") else str(lv.status)
            leaves_list.append({
                "id": str(lv.id),
                "employee_id": str(e.id),
                "employee_number": e.employee_number,
                "employee_name": p.full_name if p else e.employee_number,
                "employee_rut": p.rut if p else "S/R",
                "job_title": e.job_title,
                "company_name": comp.legal_name if comp else "",
                "leave_type": ltype_val,
                "start_date": lv.start_date.isoformat() if lv.start_date else None,
                "end_date": lv.end_date.isoformat() if lv.end_date else None,
                "days_count": lv.days_count,
                "reason": lv.reason,
                "status": lstatus_val,
                "created_at": lv.created_at.isoformat() if lv.created_at else None,
            })

        # 5. Gestión de Honorarios (BHE SII)
        bhe_list = []
        total_bhe_gross = Decimal("0")
        total_bhe_retention = Decimal("0")
        total_bhe_net = Decimal("0")
        for bh in bhe_rows:
            e = emp_by_id.get(bh.employee_id)
            if not e:
                continue
            comp = company_map.get(bh.company_id)
            p = e.person
            bstatus_val = bh.status.value if hasattr(bh.status, "value") else str(bh.status)
            total_bhe_gross += bh.gross_amount or Decimal("0")
            total_bhe_retention += bh.retention_amount or Decimal("0")
            total_bhe_net += bh.net_amount or Decimal("0")
            bhe_list.append({
                "id": str(bh.id),
                "company_id": bh.company_id,
                "company_name": comp.legal_name if comp else "",
                "company_rut": comp.rut if comp else "",
                "employee_id": str(e.id),
                "employee_number": e.employee_number,
                "employee_name": p.full_name if p else e.employee_number,
                "employee_rut": p.rut if p else "S/R",
                "job_title": e.job_title,
                "receipt_number": bh.receipt_number,
                "issue_date": bh.issue_date.isoformat() if bh.issue_date else None,
                "period": f"{bh.period_month:02d}/{bh.period_year}",
                "period_month": bh.period_month,
                "period_year": bh.period_year,
                "description": bh.description,
                "gross_amount": float(bh.gross_amount or 0),
                "retention_rate": float(bh.retention_rate or 13.75),
                "retention_amount": float(bh.retention_amount or 0),
                "net_amount": float(bh.net_amount or 0),
                "status": bstatus_val,
                "payment_date": bh.payment_date.isoformat() if bh.payment_date else None,
            })

        # 6. Remuneraciones y Liquidaciones
        payrolls_list = []
        total_payroll_taxable = Decimal("0")
        total_payroll_non_taxable = Decimal("0")
        total_payroll_earnings = Decimal("0")
        total_payroll_deductions = Decimal("0")
        total_payroll_net = Decimal("0")

        for pr in payroll_rows:
            e = emp_by_id.get(pr.employee_id)
            if not e:
                continue
            comp = company_map.get(pr.company_id)
            p = e.person
            c = active_contract_by_emp.get(e.id)
            pstatus_val = pr.status.value if hasattr(pr.status, "value") else str(pr.status)

            taxable = pr.gross_taxable_salary or Decimal("0")
            non_taxable = pr.non_taxable_allowances or Decimal("0")
            earnings = pr.total_earnings or Decimal("0")
            deductions = pr.total_deductions or Decimal("0")
            net_s = pr.net_salary or Decimal("0")

            # Aporte patronal sobre imponible de esta liquidación
            ctype_val = (c.contract_type.value if hasattr(c.contract_type, "value") else str(c.contract_type)) if c else "INDEFINITE"
            afc_emp_pct = EMPLOYER_AFC_INDEF_PCT if ctype_val == "INDEFINITE" else EMPLOYER_AFC_FIXED_PCT
            employer_afc = (taxable * afc_emp_pct / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            employer_sis = (taxable * EMPLOYER_SIS_PCT / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            employer_mutual = (taxable * EMPLOYER_MUTUAL_PCT / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            employer_cost = employer_afc + employer_sis + employer_mutual

            total_payroll_taxable += taxable
            total_payroll_non_taxable += non_taxable
            total_payroll_earnings += earnings
            total_payroll_deductions += deductions
            total_payroll_net += net_s

            payrolls_list.append({
                "id": str(pr.id),
                "company_id": pr.company_id,
                "company_name": comp.legal_name if comp else "",
                "company_rut": comp.rut if comp else "",
                "employee_id": str(e.id),
                "contract_id": str(pr.contract_id),
                "employee_number": e.employee_number,
                "employee_name": p.full_name if p else e.employee_number,
                "employee_rut": p.rut if p else "S/R",
                "job_title": e.job_title,
                "department": e.department,
                "afp_name": c.afp_name if c else "PROVIDA",
                "health_system": c.health_system if c else "FONASA",
                "period": f"{pr.period_month:02d}/{pr.period_year}",
                "period_month": pr.period_month,
                "period_year": pr.period_year,
                "worked_days": pr.worked_days,
                "base_salary": float(pr.base_salary or 0),
                "legal_gratuity": float(pr.legal_gratuity or 0),
                "bonuses": float(pr.bonuses or 0),
                "overtime_amount": float(pr.overtime_amount or 0),
                "gross_taxable_salary": float(taxable),
                "non_taxable_allowances": float(non_taxable),
                "total_earnings": float(earnings),
                "pension_deduction": float(pr.pension_deduction or 0),
                "health_deduction": float(pr.health_deduction or 0),
                "unemployment_insurance": float(pr.unemployment_insurance or 0),
                "income_tax": float(pr.income_tax or 0),
                "other_deductions": float(pr.other_deductions or 0),
                "total_deductions": float(deductions),
                "net_salary": float(net_s),
                "employer_contributions": float(employer_cost),
                "total_company_cost": float(earnings + employer_cost),
                "status": pstatus_val,
                "payment_date": pr.payment_date.isoformat() if pr.payment_date else None,
            })

        # 9. Reportes de Costos de Personal (Desglose por Sociedad SpA, Centro de Costo/Departamento y Estamento)
        cost_by_company: Dict[str, Dict[str, Any]] = {}
        cost_by_department: Dict[str, Dict[str, Any]] = {}
        cost_by_estamento: Dict[str, Dict[str, Any]] = {}

        estamento_labels = {
            "TEACHER": "Docentes Académicos (Escuela San Bao SpA)",
            "PRACTITIONER": "Tutores Clínicos & Terapeutas (Clínica San Bao SpA)",
            "ADMINISTRATIVE": "Personal Administrativo & Secretaría",
            "EXECUTIVE": "Dirección Ejecutiva",
        }

        total_company_labor_cost = Decimal("0")

        for e in all_emps:
            comp = company_map.get(e.company_id)
            comp_name = comp.legal_name if comp else "Holding San Bao"
            dept = e.department or "General"
            est_key = e.employee_type.value if hasattr(e.employee_type, "value") else str(e.employee_type)
            est_name = estamento_labels.get(est_key, est_key)

            c = active_contract_by_emp.get(e.id)
            pr = latest_payroll_by_emp.get(e.id)
            bh = latest_bhe_by_emp.get(e.id)

            taxable = pr.gross_taxable_salary if pr else Decimal("0")
            non_taxable = pr.non_taxable_allowances if pr else Decimal("0")
            ctype_val = (c.contract_type.value if hasattr(c.contract_type, "value") else str(c.contract_type)) if c else "INDEFINITE"

            if pr:
                afc_emp_pct = EMPLOYER_AFC_INDEF_PCT if ctype_val == "INDEFINITE" else EMPLOYER_AFC_FIXED_PCT
                emp_contrib = (
                    (taxable * (afc_emp_pct + EMPLOYER_SIS_PCT + EMPLOYER_MUTUAL_PCT) / Decimal("100"))
                    .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                )
            else:
                emp_contrib = Decimal("0")

            bhe_gross = bh.gross_amount if bh else Decimal("0")
            emp_total_cost = taxable + non_taxable + emp_contrib + bhe_gross
            total_company_labor_cost += emp_total_cost

            for bucket_dict, key_id, label_txt in [
                (cost_by_company, e.company_id, comp_name),
                (cost_by_department, f"{comp_name} • {dept}", f"{dept} ({'Instituto SpA' if 'instituto' in comp_name.lower() else 'Clínica SpA'})"),
                (cost_by_estamento, est_key, est_name),
            ]:
                if key_id not in bucket_dict:
                    bucket_dict[key_id] = {
                        "key": key_id,
                        "label": label_txt,
                        "headcount": 0,
                        "taxable_salaries": Decimal("0"),
                        "non_taxable_allowances": Decimal("0"),
                        "employer_contributions": Decimal("0"),
                        "bhe_gross_fees": Decimal("0"),
                        "total_monthly_cost": Decimal("0"),
                    }
                b = bucket_dict[key_id]
                b["headcount"] += 1
                b["taxable_salaries"] += taxable
                b["non_taxable_allowances"] += non_taxable
                b["employer_contributions"] += emp_contrib
                b["bhe_gross_fees"] += bhe_gross
                b["total_monthly_cost"] += emp_total_cost

        def _serialize_cost_buckets(b_dict: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
            out = []
            for item in b_dict.values():
                m_cost = item["total_monthly_cost"]
                share_pct = round(float(m_cost / total_company_labor_cost * Decimal("100")), 1) if total_company_labor_cost > 0 else 0.0
                out.append({
                    "key": item["key"],
                    "label": item["label"],
                    "headcount": item["headcount"],
                    "taxable_salaries": float(item["taxable_salaries"]),
                    "non_taxable_allowances": float(item["non_taxable_allowances"]),
                    "employer_contributions": float(item["employer_contributions"]),
                    "bhe_gross_fees": float(item["bhe_gross_fees"]),
                    "total_monthly_cost": float(m_cost),
                    "annual_projected_cost": float(m_cost * Decimal("12")),
                    "share_pct": share_pct,
                })
            out.sort(key=lambda x: x["total_monthly_cost"], reverse=True)
            return out

        docs_vigentes_total = sum(1 for d in documents_list if d["status"] == "VIGENTE")
        docs_por_vencer_total = sum(1 for d in documents_list if d["status"] == "POR_VENCER")
        docs_pendientes_total = sum(1 for d in documents_list if d["status"] == "PENDIENTE")
        global_doc_compliance = round((docs_vigentes_total / len(documents_list)) * 100, 1) if documents_list else 100.0

        att_present_total = sum(1 for a in attendance_list if a["status"] == "PRESENTE")
        global_attendance_pct = round((att_present_total / len(attendance_list)) * 100, 1) if attendance_list else 100.0
        total_overtime_hours = sum(a["overtime_hours"] for a in attendance_list)

        return {
            "kpis": {
                "active_employees": len(employees_list),
                "teachers_count": sum(1 for e in employees_list if e["employee_type"] == "TEACHER"),
                "practitioners_count": sum(1 for e in employees_list if e["employee_type"] == "PRACTITIONER"),
                "administrative_count": sum(1 for e in employees_list if e["employee_type"] in ("ADMINISTRATIVE", "EXECUTIVE")),
                "active_contracts": sum(1 for c in contracts_list if c["status"] == "ACTIVE"),
                "indefinite_contracts": sum(1 for c in contracts_list if c["contract_type"] == "INDEFINITE" and c["status"] == "ACTIVE"),
                "honorarios_contracts": sum(1 for c in contracts_list if c["contract_type"] == "FEE_HONORARIOS" and c["status"] == "ACTIVE"),
                "doc_compliance_pct": global_doc_compliance,
                "docs_total": len(documents_list),
                "docs_vigentes": docs_vigentes_total,
                "docs_alerts": docs_por_vencer_total + docs_pendientes_total,
                "attendance_rate_pct": global_attendance_pct,
                "total_overtime_hours": round(total_overtime_hours, 1),
                "pending_leaves_count": sum(1 for lv in leaves_list if lv["status"] == "PENDING"),
                "total_payroll_earnings": float(total_payroll_earnings),
                "total_payroll_net": float(total_payroll_net),
                "total_bhe_gross": float(total_bhe_gross),
                "total_bhe_retention": float(total_bhe_retention),
                "total_bhe_net": float(total_bhe_net),
                "total_previred_worker": float(total_previred_worker),
                "total_previred_employer": float(total_previred_employer),
                "total_previred_payable": float(total_previred_combined),
                "total_monthly_company_cost": float(total_company_labor_cost),
                "annual_projected_company_cost": float(total_company_labor_cost * Decimal("12")),
            },
            "companies": [
                {"id": c.id, "legal_name": c.legal_name, "rut": c.rut}
                for c in self.db.query(Company).filter(Company.is_active == True).all()
            ],
            "employees": employees_list,
            "contracts": contracts_list,
            "labor_documents": documents_list,
            "attendance_records": attendance_list,
            "leave_requests": leaves_list,
            "fee_receipts": bhe_list,
            "payrolls": payrolls_list,
            "previsional_matrix": previsional_rows,
            "teachers_and_practitioners": teachers_and_practitioners,
            "teacher_vs_tutor_split": {
                "docentes_escuela_spa": {
                    "entity_name": "Escuela San Bao SpA (Instituto de Medicina China Clásica SpA)",
                    "entity_rut": "77.123.456-8",
                    "headcount": sum(1 for tp in teachers_and_practitioners if tp["employee_type"] == "TEACHER"),
                    "monthly_cost": sum(tp["monthly_compensation_gross"] for tp in teachers_and_practitioners if tp["employee_type"] == "TEACHER"),
                    "members": [tp for tp in teachers_and_practitioners if tp["employee_type"] == "TEACHER"],
                },
                "tutores_clinica_spa": {
                    "entity_name": "Clínica San Bao SpA (Servicios Clínicos San Bao SpA)",
                    "entity_rut": "76.987.654-3",
                    "headcount": sum(1 for tp in teachers_and_practitioners if tp["employee_type"] == "PRACTITIONER"),
                    "monthly_cost": sum(tp["monthly_compensation_gross"] for tp in teachers_and_practitioners if tp["employee_type"] == "PRACTITIONER"),
                    "members": [tp for tp in teachers_and_practitioners if tp["employee_type"] == "PRACTITIONER"],
                },
            },
            "cost_reports": {
                "by_company": _serialize_cost_buckets(cost_by_company),
                "by_department": _serialize_cost_buckets(cost_by_department),
                "by_estamento": _serialize_cost_buckets(cost_by_estamento),
                "summary": {
                    "total_taxable_salaries": float(total_payroll_taxable),
                    "total_non_taxable_allowances": float(total_payroll_non_taxable),
                    "total_employer_contributions": float(total_previred_employer),
                    "total_bhe_gross": float(total_bhe_gross),
                    "total_monthly_company_cost": float(total_company_labor_cost),
                    "annual_projected_company_cost": float(total_company_labor_cost * Decimal("12")),
                },
            },
        }

    # =========================================================================
    # ACCIONES TRANSACCIONALES DEL MÓDULO PERSONAS & RRHH
    # =========================================================================

    def create_employee_from_hub(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Registra un nuevo trabajador/colaborador, su contrato inicial y su carpeta documental laboral."""
        self._ensure_tables()
        instituto, clinica = self._get_instituto_and_clinica()
        company_key = str(payload.get("company_id") or "instituto").lower()
        if company_key == "clinica" and clinica:
            comp = clinica
        elif company_key == "instituto" and instituto:
            comp = instituto
        else:
            comp = self.db.query(Company).filter(Company.id == payload.get("company_id")).first() or instituto

        if not comp:
            raise HTTPException(status_code=400, detail="Sociedad del Holding no encontrada.")

        full_name = (payload.get("full_name") or "").strip()
        rut = (payload.get("rut") or "").strip()
        if not full_name or not rut:
            raise HTTPException(status_code=400, detail="Nombre completo y RUT del colaborador son obligatorios.")

        person = self._find_or_create_person(
            rut=rut,
            full_name=full_name,
            email=payload.get("email"),
            phone=payload.get("phone"),
            address=payload.get("address"),
        )

        emp_type_str = str(payload.get("employee_type") or "TEACHER").upper()
        emp_type = EmployeeType(emp_type_str) if emp_type_str in EmployeeType.__members__ else EmployeeType.TEACHER

        prefix = "DOC" if emp_type == EmployeeType.TEACHER else ("CLI" if emp_type == EmployeeType.PRACTITIONER else "ADM")
        count = self.db.query(HREmployee).count() + 1
        emp_num = payload.get("employee_number") or f"{prefix}-2026-{count:03d}"
        while self.db.query(HREmployee).filter(HREmployee.employee_number == emp_num).first():
            count += 1
            emp_num = f"{prefix}-2026-{count:03d}"

        hire_dt_str = payload.get("hire_date")
        hire_dt = date.fromisoformat(hire_dt_str) if hire_dt_str else date.today()

        meta_notes = {
            "specialty": payload.get("specialty") or "Medicina Tradicional China & Salud Integrativa",
            "minsal_sis_registry": payload.get("minsal_sis_registry") or ("SIS-ACU-PENDIENTE" if emp_type in (EmployeeType.TEACHER, EmployeeType.PRACTITIONER) else "N/A"),
            "academic_degree": payload.get("academic_degree") or "Profesional Acreditado",
            "assigned_courses": [c.strip() for c in str(payload.get("assigned_courses") or "").split(",") if c.strip()],
            "pedagogical_hours_week": int(payload.get("pedagogical_hours_week") or (12 if emp_type == EmployeeType.TEACHER else 0)),
            "clinical_box": payload.get("clinical_box") or ("Box Clínico 3" if emp_type == EmployeeType.PRACTITIONER else "Campus San Bao"),
            "monthly_patients": int(payload.get("monthly_patients") or 0),
            "evaluation_score": 5.0,
        }

        emp = HREmployee(
            company_id=comp.id,
            person_id=person.id,
            employee_number=emp_num,
            job_title=payload.get("job_title") or "Profesional San Bao",
            department=payload.get("department") or ("Cuerpo Docente MTC" if emp_type == EmployeeType.TEACHER else "Equipo Clínico Terapéutico"),
            employee_type=emp_type,
            hire_date=hire_dt,
            status=EmployeeStatus.ACTIVE,
            notes=json.dumps(meta_notes, ensure_ascii=False),
        )
        self.db.add(emp)
        self.db.flush()

        ctype_str = str(payload.get("contract_type") or "INDEFINITE").upper()
        ctype = ContractType(ctype_str) if ctype_str in ContractType.__members__ else ContractType.INDEFINITE

        contract = HRContract(
            employee_id=emp.id,
            contract_type=ctype,
            start_date=hire_dt,
            base_salary=Decimal(str(payload.get("base_salary") or 0)),
            hourly_rate=Decimal(str(payload.get("hourly_rate") or 0)),
            clinical_commission_pct=Decimal(str(payload.get("clinical_commission_pct") or 0)),
            weekly_hours=int(payload.get("weekly_hours") or 40),
            afp_name=str(payload.get("afp_name") or "PROVIDA").upper(),
            health_system=str(payload.get("health_system") or "FONASA").upper(),
            health_quote_pct=Decimal(str(payload.get("health_quote_pct") or 7.0)),
            status=ContractStatus.ACTIVE,
            document_url=f"/static/hr/contracts/contrato_{emp_num.lower()}.pdf",
        )
        self.db.add(contract)
        self.db.flush()

        # Generar carpeta documental inicial automáticamente
        doc_base = self.db.query(HRLaborDocument).count() + 1
        initial_docs = [
            ("CONTRATO_FIRMADO", f"Contrato Laboral / Servicios ({emp_num})", "VIGENTE", "Dirección RRHH San Bao"),
            ("ENTREGA_RIOHS", "Recepción Reglamento Interno RIOHS y Ley Karin", "VIGENTE", "Prevención de Riesgos"),
            ("AFILIACION_AFP_SALUD", "Certificados Afiliación AFP y Salud Previred", "VIGENTE", "Unidad Remuneraciones"),
            ("CERTIFICADO_ANTECEDENTES", "Certificado de Antecedentes Fines Especiales", "VIGENTE", "Coordinación RRHH"),
        ]
        if emp_type in (EmployeeType.TEACHER, EmployeeType.PRACTITIONER):
            initial_docs.append(("TITULO_REGISTRO_SIS", "Título Profesional y Registro SIS MINSAL", "VIGENTE", "Dirección Académica / Clínica"))

        for idx, (dtype, dtitle, dst, dver) in enumerate(initial_docs):
            self.db.add(
                HRLaborDocument(
                    company_id=comp.id,
                    employee_id=emp.id,
                    document_type=dtype,
                    document_code=f"DOC-LAB-2026-{doc_base + idx:04d}",
                    title=dtitle,
                    issue_date=hire_dt,
                    status=dst,
                    file_url=f"/static/hr/docs/{emp_num.lower()}_{dtype.lower()}.pdf",
                    verified_by=dver,
                    notes="Generado automáticamente en proceso de alta de colaborador.",
                )
            )

        # Registrar asistencia del día actual
        self.db.add(
            HRAttendanceRecord(
                company_id=comp.id,
                employee_id=emp.id,
                attendance_date=date.today(),
                shift_name="Jornada Inicial Incorporación (09:00 - 18:00)",
                check_in="08:58",
                check_out="18:02",
                worked_hours=Decimal("8.00"),
                overtime_hours=Decimal("0.00"),
                late_minutes=0,
                status="PRESENTE",
                modality="PRESENCIAL",
                notes="Registro de ingreso e inducción institucional.",
            )
        )

        self.db.commit()
        return {
            "employee_id": str(emp.id),
            "employee_number": emp.employee_number,
            "full_name": person.full_name,
            "contract_id": str(contract.id),
            "message": f"Colaborador {person.full_name} ({emp.employee_number}) registrado con contrato y expediente laboral activo.",
        }

    def create_or_update_contract_from_hub(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo contrato o anexo contractual para un colaborador."""
        emp_id = UUID(str(payload.get("employee_id")))
        emp = HRService.get_employee_by_id(self.db, emp_id)

        active_contracts = (
            self.db.query(HRContract)
            .filter(HRContract.employee_id == emp.id, HRContract.status == ContractStatus.ACTIVE)
            .all()
        )
        for ac in active_contracts:
            ac.status = ContractStatus.EXPIRED

        ctype_str = str(payload.get("contract_type") or "INDEFINITE").upper()
        ctype = ContractType(ctype_str) if ctype_str in ContractType.__members__ else ContractType.INDEFINITE
        start_dt = date.fromisoformat(payload["start_date"]) if payload.get("start_date") else date.today()
        end_dt = date.fromisoformat(payload["end_date"]) if payload.get("end_date") else None

        new_contract = HRContract(
            employee_id=emp.id,
            contract_type=ctype,
            start_date=start_dt,
            end_date=end_dt,
            base_salary=Decimal(str(payload.get("base_salary") or 0)),
            hourly_rate=Decimal(str(payload.get("hourly_rate") or 0)),
            clinical_commission_pct=Decimal(str(payload.get("clinical_commission_pct") or 0)),
            weekly_hours=int(payload.get("weekly_hours") or 40),
            afp_name=str(payload.get("afp_name") or "PROVIDA").upper(),
            health_system=str(payload.get("health_system") or "FONASA").upper(),
            health_quote_pct=Decimal(str(payload.get("health_quote_pct") or 7.0)),
            status=ContractStatus.ACTIVE,
            document_url=f"/static/hr/contracts/anexo_{emp.employee_number.lower()}_{start_dt.isoformat()}.pdf",
        )
        self.db.add(new_contract)
        self.db.commit()
        self.db.refresh(new_contract)
        return {
            "contract_id": str(new_contract.id),
            "employee_number": emp.employee_number,
            "message": f"Contrato / Anexo actualizado exitosamente para {emp.person.full_name if emp.person else emp.employee_number}.",
        }

    def create_labor_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Registra un nuevo documento en el expediente laboral digital del trabajador."""
        self._ensure_tables()
        emp_id = UUID(str(payload.get("employee_id")))
        emp = HRService.get_employee_by_id(self.db, emp_id)

        doc_num = self.db.query(HRLaborDocument).count() + 1
        dtype = str(payload.get("document_type") or "ANEXO_CONTRACTUAL").upper()
        iss_dt = date.fromisoformat(payload["issue_date"]) if payload.get("issue_date") else date.today()
        exp_dt = date.fromisoformat(payload["expiry_date"]) if payload.get("expiry_date") else None
        st = str(payload.get("status") or "VIGENTE").upper()

        doc = HRLaborDocument(
            company_id=emp.company_id,
            employee_id=emp.id,
            document_type=dtype,
            document_code=f"DOC-LAB-2026-{doc_num:04d}",
            title=payload.get("title") or f"Documento Laboral {dtype}",
            issue_date=iss_dt,
            expiry_date=exp_dt,
            status=st,
            file_url=payload.get("file_url") or f"/static/hr/docs/{emp.employee_number.lower()}_{doc_num}.pdf",
            verified_by=payload.get("verified_by") or "Dirección RRHH San Bao",
            notes=payload.get("notes") or "Documento verificado e incorporado a carpeta digital.",
        )
        self.db.add(doc)
        self.db.commit()
        return {
            "document_id": str(doc.id),
            "document_code": doc.document_code,
            "message": f"Documento '{doc.title}' registrado con código {doc.document_code}.",
        }

    def verify_labor_document(self, document_id: UUID) -> Dict[str, Any]:
        """Valida y cambia a estado VIGENTE un documento laboral pendiente o por vencer."""
        doc = self.db.query(HRLaborDocument).filter(HRLaborDocument.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento laboral no encontrado.")
        doc.status = "VIGENTE"
        doc.verified_by = "Dirección RRHH San Bao (Verificación Digital)"
        doc.issue_date = date.today()
        if doc.expiry_date and doc.expiry_date < date.today() + timedelta(days=60):
            doc.expiry_date = date.today() + timedelta(days=365)
        self.db.commit()
        return {
            "document_id": str(doc.id),
            "status": doc.status,
            "message": f"Documento {doc.document_code} validado y actualizado a estado VIGENTE.",
        }

    def create_attendance_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Registra un marcaje de asistencia, bloque docente o horas extras."""
        self._ensure_tables()
        emp_id = UUID(str(payload.get("employee_id")))
        emp = HRService.get_employee_by_id(self.db, emp_id)

        att_dt = date.fromisoformat(payload["attendance_date"]) if payload.get("attendance_date") else date.today()
        late_min = int(payload.get("late_minutes") or 0)
        st = str(payload.get("status") or ("ATRASO" if late_min > 0 else "PRESENTE")).upper()

        rec = HRAttendanceRecord(
            company_id=emp.company_id,
            employee_id=emp.id,
            attendance_date=att_dt,
            shift_name=payload.get("shift_name") or "Jornada Ordinaria (09:00 - 18:00)",
            check_in=payload.get("check_in") or "09:00",
            check_out=payload.get("check_out") or "18:00",
            worked_hours=Decimal(str(payload.get("worked_hours") or 8.0)),
            overtime_hours=Decimal(str(payload.get("overtime_hours") or 0.0)),
            late_minutes=late_min,
            status=st,
            modality=str(payload.get("modality") or "PRESENCIAL").upper(),
            notes=payload.get("notes") or "Marcaje registrado en control de asistencia RRHH.",
        )
        self.db.add(rec)
        self.db.commit()
        return {
            "attendance_id": str(rec.id),
            "message": f"Asistencia registrada para {emp.person.full_name if emp.person else emp.employee_number} ({att_dt.isoformat()}).",
        }

    def create_leave_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Crea una solicitud de vacaciones, licencia médica o permiso administrativo."""
        emp_id = UUID(str(payload.get("employee_id")))
        emp = HRService.get_employee_by_id(self.db, emp_id)

        ltype_str = str(payload.get("leave_type") or "ADMINISTRATIVE").upper()
        ltype = LeaveType(ltype_str) if ltype_str in LeaveType.__members__ else LeaveType.ADMINISTRATIVE

        s_dt = date.fromisoformat(payload["start_date"]) if payload.get("start_date") else date.today()
        e_dt = date.fromisoformat(payload["end_date"]) if payload.get("end_date") else s_dt
        days = int(payload.get("days_count") or max((e_dt - s_dt).days + 1, 1))

        leave = HRLeaveRequest(
            employee_id=emp.id,
            leave_type=ltype,
            start_date=s_dt,
            end_date=e_dt,
            days_count=days,
            reason=payload.get("reason") or "Solicitud ingresada en portal de Personas & RRHH.",
            status=LeaveStatus.PENDING,
        )
        self.db.add(leave)
        self.db.commit()
        return {
            "leave_id": str(leave.id),
            "message": f"Solicitud de {ltype.value} por {days} día(s) registrada correctamente.",
        }

    def update_leave_status(self, leave_id: UUID, new_status: str) -> Dict[str, Any]:
        """Aprueba o rechaza una solicitud de permiso, feriado legal o licencia médica."""
        leave = self.db.query(HRLeaveRequest).filter(HRLeaveRequest.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
        st_upper = new_status.upper().strip()
        leave.status = LeaveStatus(st_upper) if st_upper in LeaveStatus.__members__ else LeaveStatus.APPROVED
        self.db.commit()
        return {
            "leave_id": str(leave.id),
            "status": leave.status.value,
            "message": f"Solicitud actualizada a estado {leave.status.value}.",
        }

    def update_previsional_info(self, contract_id: UUID, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza AFP, Sistema de Salud (Fonasa/Isapre) y % cotización de salud de un contrato activo."""
        contract = self.db.query(HRContract).filter(HRContract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=404, detail="Contrato no encontrado.")
        if payload.get("afp_name"):
            contract.afp_name = str(payload["afp_name"]).upper().strip()
        if payload.get("health_system"):
            contract.health_system = str(payload["health_system"]).upper().strip()
        if payload.get("health_quote_pct") is not None:
            contract.health_quote_pct = Decimal(str(payload["health_quote_pct"]))
        self.db.commit()
        return {
            "contract_id": str(contract.id),
            "afp_name": contract.afp_name,
            "health_system": contract.health_system,
            "health_quote_pct": float(contract.health_quote_pct),
            "message": "Información previsional actualizada para planilla Previred.",
        }

    def update_professional_profile(self, employee_id: UUID, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza cátedras asignadas, horas pedagógicas, registro MINSAL/SIS, box clínico y tarifa/comisión."""
        emp = HRService.get_employee_by_id(self.db, employee_id)
        meta = self._parse_employee_meta(emp)

        for field in ("specialty", "minsal_sis_registry", "academic_degree", "clinical_box"):
            if payload.get(field) is not None:
                meta[field] = str(payload[field]).strip()
        if payload.get("assigned_courses") is not None:
            if isinstance(payload["assigned_courses"], list):
                meta["assigned_courses"] = payload["assigned_courses"]
            else:
                meta["assigned_courses"] = [c.strip() for c in str(payload["assigned_courses"]).split(",") if c.strip()]
        if payload.get("pedagogical_hours_week") is not None:
            meta["pedagogical_hours_week"] = int(payload["pedagogical_hours_week"])
        if payload.get("monthly_patients") is not None:
            meta["monthly_patients"] = int(payload["monthly_patients"])

        emp.notes = json.dumps(meta, ensure_ascii=False)

        contract = (
            self.db.query(HRContract)
            .filter(HRContract.employee_id == emp.id, HRContract.status == ContractStatus.ACTIVE)
            .first()
        )
        if contract:
            if payload.get("hourly_rate") is not None:
                contract.hourly_rate = Decimal(str(payload["hourly_rate"]))
            if payload.get("clinical_commission_pct") is not None:
                contract.clinical_commission_pct = Decimal(str(payload["clinical_commission_pct"]))

        self.db.commit()
        return {
            "employee_id": str(emp.id),
            "message": f"Ficha académica/clínica de {emp.person.full_name if emp.person else emp.employee_number} actualizada.",
        }
