from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.redis import cache_result
from app.models.models import (
    Alert, Client, Contract, ContractStatus, EmailRecord,
    Employee, Transaction, TransactionType, User,
)
from app.models.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    today = date.today()
    month_start = today.replace(day=1)

    total_clients = db.query(func.count(Client.id)).filter(Client.is_active.is_(True)).scalar()
    active_contracts = db.query(func.count(Contract.id)).filter(
        Contract.status == ContractStatus.ATIVO
    ).scalar()
    contracts_expiring = db.query(func.count(Contract.id)).filter(
        Contract.status == ContractStatus.PROXIMO_VENCIMENTO
    ).scalar()
    total_employees = db.query(func.count(Employee.id)).filter(
        Employee.is_active.is_(True)
    ).scalar()
    pending_alerts = db.query(func.count(Alert.id)).filter(
        Alert.is_read.is_(False)
    ).scalar()
    unread_emails = db.query(func.count(EmailRecord.id)).filter(
        EmailRecord.is_read.is_(False)
    ).scalar()

    monthly_revenue = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.type == TransactionType.RECEITA,
        Transaction.date >= month_start,
    ).scalar()

    monthly_expenses = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.type == TransactionType.DESPESA,
        Transaction.date >= month_start,
    ).scalar()

    return DashboardSummary(
        total_clients=total_clients,
        active_contracts=active_contracts,
        contracts_expiring_soon=contracts_expiring,
        total_employees=total_employees,
        pending_alerts=pending_alerts,
        unread_emails=unread_emails,
        monthly_revenue=monthly_revenue,
        monthly_expenses=monthly_expenses,
        cash_flow_balance=monthly_revenue - monthly_expenses,
    )
