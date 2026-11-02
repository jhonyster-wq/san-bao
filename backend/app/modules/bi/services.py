from decimal import Decimal
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.modules.institutional.models import Company
from app.modules.academic.models import (
    Student,
    Program,
    Cohort,
    ClinicalPracticeHour,
)
from app.modules.clinical.models.patient import Patient
from app.modules.clinical.models.practitioner import Practitioner
from app.modules.clinical.models.appointment import Appointment
from app.modules.clinical.models.encounter import ClinicalEncounter
from app.modules.finance.models import (
    Payment,
    Installment,
    PaymentCommitment,
)
from app.modules.ecommerce.models import Order
from app.modules.hr.models import (
    HREmployee,
    HRContract,
    HRPayroll,
    HRFeeReceipt,
    FeeReceiptStatus,
)
from app.modules.bi.schemas import (
    ExecutiveDashboardResponse,
    FinancialSummary,
    AcademicKpis,
    ClinicalKpis,
)


class BIService:
    @staticmethod
    def get_executive_dashboard(db: Session, company_id: Optional[UUID] = None) -> ExecutiveDashboardResponse:
        company_name = "Consolidado San Bao"
        if company_id:
            company = db.query(Company).filter(Company.id == str(company_id)).first()
            if company:
                company_name = company.trade_name or company.legal_name

        # 1. Ingresos y Cobranzas
        # Pagos en finanzas (aranceles/matrículas)
        fin_payments_query = db.query(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
        if company_id:
            fin_payments_query = fin_payments_query.filter(Payment.company_id == str(company_id))
        tuition_revenue = Decimal(str(fin_payments_query.scalar() or "0.00"))

        # Ventas E-Commerce pagadas
        ecom_query = db.query(func.coalesce(func.sum(Order.total_amount), Decimal("0.00"))).filter(
            Order.payment_status == "PAID"
        )
        if company_id:
            ecom_query = ecom_query.filter(Order.company_id == str(company_id))
        ecommerce_revenue = Decimal(str(ecom_query.scalar() or "0.00"))

        # Cuentas por cobrar pendientes (cuotas de arancel vencidas o pendientes)
        receivables_query = db.query(func.coalesce(func.sum(Installment.balance), Decimal("0.00"))).filter(
            Installment.status.in_(["PENDING", "OVERDUE"])
        )
        if company_id:
            receivables_query = receivables_query.join(Installment.commitment).filter(
                PaymentCommitment.company_id == str(company_id)
            )
        pending_receivables = Decimal(str(receivables_query.scalar() or "0.00"))

        clinical_revenue = Decimal("0.00")  # Las atenciones pueden facturarse en DTE o finanzas

        total_revenue = tuition_revenue + ecommerce_revenue + clinical_revenue

        # 2. Egresos Operativos y Remuneraciones
        payroll_query = db.query(func.coalesce(func.sum(HRPayroll.total_earnings), Decimal("0.00")))
        if company_id:
            payroll_query = payroll_query.filter(HRPayroll.company_id == company_id)
        payroll_expenses = Decimal(str(payroll_query.scalar() or "0.00"))

        fee_query = db.query(func.coalesce(func.sum(HRFeeReceipt.gross_amount), Decimal("0.00"))).filter(
            HRFeeReceipt.status != FeeReceiptStatus.ANNULLED
        )
        if company_id:
            fee_query = fee_query.filter(HRFeeReceipt.company_id == company_id)
        fee_expenses = Decimal(str(fee_query.scalar() or "0.00"))

        total_expenses = payroll_expenses + fee_expenses
        net_operating_result = total_revenue - total_expenses

        # 3. KPIs Académicos (Pertenecen a Instituto SpA)
        is_clinic = False
        if company_id:
            comp = db.query(Company).filter(Company.id == str(company_id)).first()
            if comp and ("Clínic" in (comp.legal_name or "") or "Clínic" in (comp.trade_name or "")):
                is_clinic = True

        students_query = db.query(Student).filter(Student.deleted_at.is_(None))
        cohorts_query = db.query(Cohort).filter(Cohort.deleted_at.is_(None))
        programs_query = db.query(Program).filter(Program.is_active == True)
        hours_query = db.query(func.coalesce(func.sum(ClinicalPracticeHour.hours_completed), Decimal("0.00")))

        total_active_students = 0 if is_clinic else students_query.count()
        active_cohorts = 0 if is_clinic else cohorts_query.count()
        total_programs = 0 if is_clinic else programs_query.count()
        accredited_clinical_hours = Decimal(str(hours_query.scalar() or "0.00"))

        # 4. KPIs Clínicos
        patients_query = db.query(Patient).filter(Patient.deleted_at.is_(None))
        appointments_query = db.query(Appointment)
        completed_app_query = db.query(Appointment).filter(Appointment.status == "COMPLETED")
        practitioners_query = db.query(Practitioner).filter(Practitioner.is_active == True)
        encounters_query = db.query(ClinicalEncounter).filter(ClinicalEncounter.status == "SIGNED")

        if company_id:
            appointments_query = appointments_query.filter(Appointment.company_id == str(company_id))
            completed_app_query = completed_app_query.filter(Appointment.company_id == str(company_id))
            encounters_query = encounters_query.join(ClinicalEncounter.appointment).filter(Appointment.company_id == str(company_id))

        total_patients = patients_query.count()
        total_appointments = appointments_query.count()
        completed_appointments = completed_app_query.count()
        active_practitioners = practitioners_query.count()
        signed_clinical_encounters = encounters_query.count()

        return ExecutiveDashboardResponse(
            company_id=company_id,
            company_name=company_name,
            financial=FinancialSummary(
                total_revenue=total_revenue,
                tuition_revenue=tuition_revenue,
                clinical_revenue=clinical_revenue,
                ecommerce_revenue=ecommerce_revenue,
                pending_receivables=pending_receivables,
                hr_payroll_expenses=payroll_expenses,
                hr_fee_expenses=fee_expenses,
                total_expenses=total_expenses,
                net_operating_result=net_operating_result,
            ),
            academic=AcademicKpis(
                total_active_students=total_active_students,
                active_cohorts=active_cohorts,
                total_programs=total_programs,
                accredited_clinical_hours=accredited_clinical_hours,
            ),
            clinical=ClinicalKpis(
                total_patients=total_patients,
                total_appointments=total_appointments,
                completed_appointments=completed_appointments,
                active_practitioners=active_practitioners,
                signed_clinical_encounters=signed_clinical_encounters,
            ),
        )
