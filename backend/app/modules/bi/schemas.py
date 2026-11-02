from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class FinancialSummary(BaseModel):
    total_revenue: Decimal
    tuition_revenue: Decimal
    clinical_revenue: Decimal
    ecommerce_revenue: Decimal
    pending_receivables: Decimal  # Cuentas por cobrar / Morosidad
    hr_payroll_expenses: Decimal  # Nóminas
    hr_fee_expenses: Decimal      # Honorarios
    total_expenses: Decimal
    net_operating_result: Decimal

    model_config = ConfigDict(from_attributes=True)


class AcademicKpis(BaseModel):
    total_active_students: int
    active_cohorts: int
    total_programs: int
    accredited_clinical_hours: Decimal

    model_config = ConfigDict(from_attributes=True)


class ClinicalKpis(BaseModel):
    total_patients: int
    total_appointments: int
    completed_appointments: int
    active_practitioners: int
    signed_clinical_encounters: int

    model_config = ConfigDict(from_attributes=True)


class ExecutiveDashboardResponse(BaseModel):
    company_id: Optional[UUID] = None
    company_name: Optional[str] = "Consolidado San Bao"
    financial: FinancialSummary
    academic: AcademicKpis
    clinical: ClinicalKpis

    model_config = ConfigDict(from_attributes=True)
