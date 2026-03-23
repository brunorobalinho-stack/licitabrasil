"""
Agente de Projeção de Fluxo de Caixa

Analisa transações históricas e projeta:
- Receitas e despesas futuras (3-12 meses)
- Identifica tendências
- Alerta sobre meses com saldo negativo projetado
- Considera transações recorrentes
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    AgentRun, Alert, AlertType, Transaction, TransactionType,
)


def _get_monthly_totals(db: Session, months_back: int = 6) -> list[dict]:
    """Get monthly revenue/expense totals for the last N months."""
    today = date.today()
    start = today.replace(day=1) - relativedelta(months=months_back)

    results = (
        db.query(
            func.date_trunc("month", Transaction.date).label("month"),
            Transaction.type,
            func.sum(Transaction.amount).label("total"),
        )
        .filter(Transaction.date >= start)
        .group_by("month", Transaction.type)
        .order_by("month")
        .all()
    )

    monthly = {}
    for row in results:
        month_key = row.month.strftime("%Y-%m") if hasattr(row.month, "strftime") else str(row.month)[:7]
        if month_key not in monthly:
            monthly[month_key] = {"revenue": Decimal("0"), "expenses": Decimal("0")}
        if row.type == TransactionType.RECEITA:
            monthly[month_key]["revenue"] = row.total
        else:
            monthly[month_key]["expenses"] = row.total

    return monthly


def _get_recurring_transactions(db: Session) -> tuple[Decimal, Decimal]:
    """Sum up recurring monthly revenue and expenses."""
    recurring = db.query(Transaction).filter(
        Transaction.is_recurring.is_(True)
    ).all()

    recurring_revenue = sum(
        (t.amount for t in recurring if t.type == TransactionType.RECEITA),
        Decimal("0"),
    )
    recurring_expenses = sum(
        (t.amount for t in recurring if t.type == TransactionType.DESPESA),
        Decimal("0"),
    )
    return recurring_revenue, recurring_expenses


def run_cashflow_projection(db: Session, months_ahead: int = 6) -> dict:
    """Generate cash flow projection for the next N months."""

    agent_run = AgentRun(agent_name="cashflow_projection", status="running")
    db.add(agent_run)
    db.commit()

    try:
        historical = _get_monthly_totals(db, months_back=6)
        recurring_rev, recurring_exp = _get_recurring_transactions(db)

        # Calculate average trends from historical data
        if historical:
            avg_revenue = sum(m["revenue"] for m in historical.values()) / len(historical)
            avg_expenses = sum(m["expenses"] for m in historical.values()) / len(historical)
        else:
            avg_revenue = recurring_rev
            avg_expenses = recurring_exp

        # Blend historical average with recurring known amounts
        base_revenue = max(avg_revenue, recurring_rev)
        base_expenses = max(avg_expenses, recurring_exp)

        # Project forward
        today = date.today()
        projections = []
        issues_found = 0

        for i in range(1, months_ahead + 1):
            future_month = today.replace(day=1) + relativedelta(months=i)
            month_str = future_month.strftime("%Y-%m")

            # Simple projection with slight growth/decay factor
            projected_rev = (base_revenue * (Decimal("1") + Decimal("0.01") * i)).quantize(Decimal("0.01"))
            projected_exp = (base_expenses * (Decimal("1") + Decimal("0.005") * i)).quantize(Decimal("0.01"))
            balance = projected_rev - projected_exp

            projections.append({
                "month": month_str,
                "projected_revenue": projected_rev,
                "projected_expenses": projected_exp,
                "balance": balance,
            })

            # Alert if projected negative balance
            if balance < 0:
                issues_found += 1
                alert = Alert(
                    type=AlertType.CASH_FLOW_WARNING,
                    title=f"Saldo negativo projetado: {month_str}",
                    message=(
                        f"Projeção para {month_str}: "
                        f"Receita R${projected_rev}, Despesa R${projected_exp}, "
                        f"Saldo R${balance}. Ação preventiva recomendada."
                    ),
                    severity="warning",
                )
                db.add(alert)

        agent_run.status = "completed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.items_processed = months_ahead
        agent_run.issues_found = issues_found
        agent_run.result_summary = (
            f"Projeção de {months_ahead} meses gerada, "
            f"{issues_found} meses com saldo negativo"
        )
        db.commit()

        return {
            "status": "completed",
            "months_projected": months_ahead,
            "negative_months": issues_found,
            "projections": projections,
            "recurring_revenue": recurring_rev,
            "recurring_expenses": recurring_exp,
        }

    except Exception as e:
        agent_run.status = "failed"
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.result_summary = str(e)
        db.commit()
        raise
