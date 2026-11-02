from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class InstallmentResponse(BaseModel):
    id: str
    commitment_id: str
    installment_number: int
    amount: Decimal
    balance: Decimal
    due_date: date
    status: str
    paid_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class PaymentCommitmentBase(BaseModel):
    company_id: str
    person_id: str
    enrollment_id: Optional[str] = None
    concept: str
    total_amount: Decimal
    balance: Decimal
    installments_count: int = 1
    status: str = "PENDING"


class PaymentCommitmentCreate(BaseModel):
    company_id: str
    person_id: str
    enrollment_id: Optional[str] = None
    concept: str
    total_amount: Decimal
    installments_count: int = 1
    first_due_date: date


class PaymentCommitmentResponse(PaymentCommitmentBase):
    id: str
    installments: List[InstallmentResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    company_id: str
    person_id: str
    amount: Decimal = Field(..., gt=0, description="Monto abonado en pesos CLP")
    payment_method: str = Field("TRANSFER", description="TRANSFER, WEBPAY, CASH, CHECK")
    payment_date: Optional[date] = None
    reference_number: Optional[str] = Field(None, description="Comprobante bancario o código de transacción")
    notes: Optional[str] = None
    # Si es None, el sistema abona automáticamente a las cuotas más antiguas vencidas o por vencer
    target_installment_id: Optional[str] = None


class PaymentAllocationResponse(BaseModel):
    installment_id: str
    amount_applied: Decimal
    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    id: str
    company_id: str
    person_id: str
    payment_date: date
    amount: Decimal
    payment_method: str
    reference_number: Optional[str] = None
    allocations: List[PaymentAllocationResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StudentFinancialStatusResponse(BaseModel):
    person_id: str
    total_committed: Decimal
    total_paid: Decimal
    total_balance: Decimal
    has_overdue_debt: bool
    overdue_amount: Decimal
    commitments: List[PaymentCommitmentResponse] = []
