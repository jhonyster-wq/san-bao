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


class FinancialIntelligenceKpiItem(BaseModel):
    code: str
    name: str
    value: float
    unit: str
    formula: str
    data_source: str
    involved_accounts: List[str]
    period: str
    null_handling: str
    company_id: str
    company_name: str
    cost_center: str
    updated_at: str
    max_refresh_interval_hours: int = 24


class ExecutiveDashboardResponse(BaseModel):
    company_id: Optional[UUID] = None
    company_name: Optional[str] = "Consolidado San Bao"
    updated_at: Optional[str] = None
    max_refresh_interval_hours: int = 24
    financial: FinancialSummary
    academic: AcademicKpis
    clinical: ClinicalKpis
    financial_intelligence_kpis: Optional[Dict[str, FinancialIntelligenceKpiItem]] = None

    model_config = ConfigDict(from_attributes=True)
