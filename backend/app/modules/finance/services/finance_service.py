from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from app.modules.finance.models.commitment import PaymentCommitment, Installment, Payment, PaymentAllocation
from app.modules.finance.schemas.commitment import PaymentCreate, StudentFinancialStatusResponse, PaymentCommitmentResponse
from app.core.exceptions import EntityNotFoundException, SanBaoException


def add_months(sourcedate: date, months: int) -> date:
    """Suma 'months' meses a una fecha considerando límites de fin de mes."""
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days_in_month = [31, 29 if is_leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(sourcedate.day, days_in_month[month - 1])
    return date(year, month, day)


class FinanceService:
    def __init__(self, db: Session):
        self.db = db

    def create_tuition_commitment(
        self,
        company_id: str,
        person_id: str,
        enrollment_id: str,
        concept: str,
        total_amount: Decimal,
        installments_count: int = 10,
        first_due_date: Optional[date] = None,
    ) -> PaymentCommitment:
        """
        Genera el compromiso financiero de arancel académico particionado en cuotas mensuales.
        Regla: la suma exacta de las cuotas debe ser igual a total_amount.
        """
        if total_amount <= 0:
            raise SanBaoException("El monto total del arancel debe ser superior a 0")
        if installments_count < 1:
            installments_count = 1

        if not first_due_date:
            first_due_date = date.today()

        commitment = PaymentCommitment(
            company_id=company_id,
            person_id=person_id,
            enrollment_id=enrollment_id,
            concept=concept,
            total_amount=total_amount,
            balance=total_amount,
            installments_count=installments_count,
            status="PENDING",
        )
        self.db.add(commitment)
        self.db.flush()

        # Calcular cuota base y residuo para cuadratura de centavos/pesos
        base_installment = total_amount // installments_count
        remainder = total_amount - (base_installment * installments_count)

        for i in range(installments_count):
            # El residuo de división entera se suma a la primera cuota
            quota_amount = base_installment + (remainder if i == 0 else Decimal(0))
            due_date = add_months(first_due_date, i)

            installment = Installment(
                commitment_id=commitment.id,
                installment_number=i + 1,
                amount=quota_amount,
                balance=quota_amount,
                due_date=due_date,
                status="PENDING",
            )
            self.db.add(installment)

        self.db.commit()
        self.db.refresh(commitment)
        return commitment

    def record_payment(self, payload: PaymentCreate, received_by: Optional[str] = None) -> Payment:
        """
        Registra la recepción de un pago y lo imputa automáticamente a las cuotas pendientes
        (priorizando las cuotas vencidas y más antiguas, salvo que se especifique una cuota destino).
        """
        payment_date = payload.payment_date or date.today()

        payment = Payment(
            company_id=payload.company_id,
            person_id=payload.person_id,
            payment_date=payment_date,
            amount=payload.amount,
            payment_method=payload.payment_method,
            reference_number=payload.reference_number,
            notes=payload.notes,
            received_by=received_by,
        )
        self.db.add(payment)
        self.db.flush()

        remaining_to_apply = payload.amount

        if payload.target_installment_id:
            target = self.db.query(Installment).filter(Installment.id == payload.target_installment_id).first()
            if not target:
                raise EntityNotFoundException("Cuota", payload.target_installment_id)
            installments = [target]
        else:
            # Buscar cuotas pendientes de esta persona en esta sociedad ordenadas por fecha de vencimiento
            installments = (
                self.db.query(Installment)
                .join(PaymentCommitment)
                .filter(
                    PaymentCommitment.person_id == payload.person_id,
                    PaymentCommitment.company_id == payload.company_id,
                    Installment.balance > 0,
                )
                .order_by(Installment.due_date.asc(), Installment.installment_number.asc())
                .all()
            )

        for inst in installments:
            if remaining_to_apply <= 0:
                break

            amount_for_inst = min(remaining_to_apply, inst.balance)
            inst.balance -= amount_for_inst
            remaining_to_apply -= amount_for_inst

            if inst.balance == 0:
                inst.status = "PAID"
                inst.paid_at = datetime.now(timezone.utc)
            else:
                inst.status = "PARTIALLY_PAID"

            allocation = PaymentAllocation(
                payment_id=payment.id,
                installment_id=inst.id,
                amount_applied=amount_for_inst,
            )
            self.db.add(allocation)

            # Actualizar saldo del compromiso padre
            commitment = inst.commitment
            commitment.balance -= amount_for_inst
            if commitment.balance == 0:
                commitment.status = "PAID"
            else:
                commitment.status = "PARTIALLY_PAID"

        self.db.commit()
        self.db.refresh(payment)
        return payment

    def get_person_financial_status(self, person_id: str, company_id: Optional[str] = None) -> StudentFinancialStatusResponse:
        """Calcula el estado financiero de un alumno: deuda total, pagado, mora y cuotas."""
        query = self.db.query(PaymentCommitment).filter(
            PaymentCommitment.person_id == person_id,
            PaymentCommitment.deleted_at.is_(None),
        )
        if company_id:
            query = query.filter(PaymentCommitment.company_id == company_id)

        commitments = query.all()
        today = date.today()

        total_committed = Decimal(0)
        total_balance = Decimal(0)
        overdue_amount = Decimal(0)
        has_overdue = False

        for c in commitments:
            total_committed += c.total_amount
            total_balance += c.balance
            for inst in c.installments:
                if inst.balance > 0 and inst.due_date < today:
                    has_overdue = True
                    overdue_amount += inst.balance

        total_paid = total_committed - total_balance

        return StudentFinancialStatusResponse(
            person_id=person_id,
            total_committed=total_committed,
            total_paid=total_paid,
            total_balance=total_balance,
            has_overdue_debt=has_overdue,
            overdue_amount=overdue_amount,
            commitments=commitments,
        )
