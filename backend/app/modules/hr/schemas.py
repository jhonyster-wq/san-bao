from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.modules.hr.models import (
    EmployeeType,
    EmployeeStatus,
    ContractType,
    ContractStatus,
    LeaveType,
    LeaveStatus,
    FeeReceiptStatus,
    PayrollStatus,
)


class HRContractBase(BaseModel):
    contract_type: ContractType
    start_date: date
    end_date: Optional[date] = None
    base_salary: Decimal = Field(default=Decimal("0.00"), ge=0)
    hourly_rate: Decimal = Field(default=Decimal("0.00"), ge=0)
    clinical_commission_pct: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    weekly_hours: int = Field(default=40, ge=1, le=60)
    afp_name: Optional[str] = "MODELO"
    health_system: Optional[str] = "FONASA"
    health_quote_pct: Decimal = Field(default=Decimal("7.00"), ge=0, le=20)


class HRContractCreate(HRContractBase):
    employee_id: UUID


class HRContractResponse(HRContractBase):
    id: UUID
    employee_id: UUID
    status: ContractStatus
    document_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HREmployeeBase(BaseModel):
    employee_number: str
    job_title: str
    department: str
    employee_type: EmployeeType
    hire_date: date
    termination_date: Optional[date] = None
    notes: Optional[str] = None


class HREmployeeCreate(HREmployeeBase):
    company_id: str
    person_id: str


class HREmployeeResponse(HREmployeeBase):
    id: UUID
    company_id: str
    person_id: str
    status: EmployeeStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HRLeaveRequestCreate(BaseModel):
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    days_count: int = Field(gt=0)
    reason: Optional[str] = None


class HRLeaveRequestResponse(BaseModel):
    id: UUID
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    days_count: int
    reason: Optional[str] = None
    status: LeaveStatus
    approved_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HRFeeReceiptCreate(BaseModel):
    company_id: str
    employee_id: UUID
    receipt_number: str
    issue_date: date
    period_month: int = Field(ge=1, le=12)
    period_year: int = Field(ge=2020)
    description: str
    gross_amount: Decimal = Field(gt=0)
    retention_rate: Decimal = Field(default=Decimal("13.75"), ge=0, le=50)


class HRFeeReceiptResponse(BaseModel):
    id: UUID
    company_id: str
    employee_id: UUID
    receipt_number: str
    issue_date: date
    period_month: int
    period_year: int
    description: str
    gross_amount: Decimal
    retention_rate: Decimal
    retention_amount: Decimal
    net_amount: Decimal
    status: FeeReceiptStatus
    payment_date: Optional[date] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HRPayrollCreate(BaseModel):
    company_id: str
    employee_id: UUID
    contract_id: UUID
    period_month: int = Field(ge=1, le=12)
    period_year: int = Field(ge=2020)
    worked_days: int = Field(default=30, ge=1, le=31)
    base_salary: Optional[Decimal] = None  # Si es None se toma del contrato
    bonuses: Decimal = Field(default=Decimal("0.00"), ge=0)
    overtime_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    non_taxable_allowances: Decimal = Field(default=Decimal("0.00"), ge=0)


class HRPayrollResponse(BaseModel):
    id: UUID
    company_id: str
    employee_id: UUID
    contract_id: UUID
    period_month: int
    period_year: int
    worked_days: int
    base_salary: Decimal
    legal_gratuity: Decimal
    bonuses: Decimal
    overtime_amount: Decimal
    gross_taxable_salary: Decimal
    non_taxable_allowances: Decimal
    total_earnings: Decimal
    pension_deduction: Decimal
    health_deduction: Decimal
    unemployment_insurance: Decimal
    income_tax: Decimal
    other_deductions: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    status: PayrollStatus
    payment_date: Optional[date] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
