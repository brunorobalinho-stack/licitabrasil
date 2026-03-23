"""
Agente de Alertas de Pagamento de Salário

Monitora datas de pagamento e:
- Alerta N dias antes do 5º dia útil (prazo CLT)
- Identifica funcionários sem registro de pagamento no mês atual
- Calcula total da folha para provisionamento
- Verifica se há saldo suficiente projetado
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.models import (
    AgentRun, Alert, AlertType, Employee, PayrollRecord,
    Transaction, TransactionType,
)

settings = get_settings()


def _get_business_day(year: int, month: int, nth: int) -> date:
    """Get the Nth business day of a given month (simple, no holiday calendar)."""
    d = date(year, month, 1)
    count = 0
    while count < nth:
        if d.weekday() < 5:  # Mon-Fri
            count += 1
            if count == nth:
                return d
        d += timedelta(days=1)
    return d


def run_salary_alerts(db: Session) -> dict:
    """Check salary payment status and generate alerts."""

    agent_run = AgentRun(agent_name="salary_alerts", status="running")
    db.add(agent_run)
    db.commit()

    today = date.today()
    current_month_start = today.replace(day=1)
    alert_days = settings.SALARY_ALERT_DAYS_BEFORE
    items_processed = 0
    issues_found = 0
    results = {
        "unpaid_employees": [],
        "total_payroll": Decimal("0"),
        "payment_deadline": None,
        "days_until_deadline": None,
    }

    try:
        # 5th business day of current month = CLT payment deadline
        payment_deadline = _get_business_day(today.year, today.month, 5)
        days_until = (payment_deadline - today).days
        results["payment_deadline"] = payment_deadline.isoformat()
        results["days_until_deadline"] = days_until

        active_employees = db.query(Employee).filter(
            Employee.is_active.is_(True)
        ).all()

        total_payroll = Decimal("0")
        unpaid = []

        for emp in active_employees:
            items_processed += 1
            total_payroll += emp.salary

            # Check if payment record exists for current month
            has_payment = db.query(PayrollRecord).filter(
                PayrollRecord.employee_id == emp.id,
                PayrollRecord.reference_month == current_month_start,
                PayrollRecord.payment_date.isnot(None),
            ).first()

            if not has_payment:
                unpaid.append({
                    "employee_id": emp.id,
                    "name": emp.name,
                    "salary": str(emp.salary),
                })

        results["unpaid_employees"] = unpaid
        results["total_payroll"] = total_payroll

        # Generate alert if payment deadline is approaching and there are unpaid employees
        if days_until <= alert_days and unpaid:
            issues_found = len(unpaid)
            alert = Alert(
                type=AlertType.SALARY_PAYOUT,
                title=f"Folha de pagamento: {len(unpaid)} funcionários pendentes",
                message=(
                    f"Prazo de pagamento (5º dia útil): {payment_deadline.strftime('%d/%m/%Y')} "
                    f"({days_until} dias). "
                    f"{len(unpaid)} de {len(active_employees)} funcionários sem pagamento registrado. "
                    f"Total da folha: R${total_payroll}."
                ),
                severity="critical" if days_until <= 2 else "warning",
            )
            db.add(alert)

        # Check if there's enough cash to cover payroll
        month_revenue = db.query(func.sum(Transaction.amount)).filter(
            Transaction.type == TransactionType.RECEITA,
            Transaction.date >= current_month_start,
            Transaction.date <= today,
        ).scalar() or Decimal("0")

        month_expenses = db.query(func.sum(Transaction.amount)).filter(
            Transaction.type == TransactionType.DESPESA,
            Transaction.date >= current_month_start,
            Transaction.date <= today,
        ).scalar() or Decimal("0")

        available = month_revenue - month_expenses
        if available < total_payroll:
            shortfall = total_payroll - available
            alert = Alert(
                type=AlertType.CASH_FLOW_WARNING,
                title=f"Saldo insuficiente para folha: déficit R${shortfall}",
                message=(
                    f"Saldo disponível no mês: R${available}. "
                    f"Total da folha: R${total_payroll}. "
                    f"Déficit projetado: R${shortfall}."
                ),
                severity="critical",
            )
            db.add(alert)
            issues_found += 1

        agent_run.status = "completed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.items_processed = items_processed
        agent_run.issues_found = issues_found
        agent_run.result_summary = (
            f"Verificados {items_processed} funcionários, "
            f"{len(unpaid)} sem pagamento, "
            f"prazo em {days_until} dias"
        )
        db.commit()

        return {
            "status": "completed",
            "items_processed": items_processed,
            "issues_found": issues_found,
            **results,
        }

    except Exception as e:
        agent_run.status = "failed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.result_summary = str(e)
        db.commit()
        raise
