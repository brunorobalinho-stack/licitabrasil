import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Client, Transaction, TransactionType, User
from app.models.schemas import TransactionCreate, TransactionOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    type: TransactionType | None = None,
    client_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = db.query(Transaction)
    if type:
        query = query.filter(Transaction.type == type)
    if client_id:
        query = query.filter(Transaction.client_id == client_id)
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    return query.order_by(Transaction.transaction_date.desc()).limit(limit).all()


@router.post("/", response_model=TransactionOut, status_code=201)
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if data.client_id:
        client = db.query(Client).filter(Client.id == data.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")

    txn = Transaction(**data.model_dump())
    db.add(txn)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflito ao criar transação")
    db.refresh(txn)
    return txn


@router.get("/monthly-summary")
def monthly_summary(
    months: int = Query(default=6, le=24),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    results = (
        db.query(
            func.date_trunc("month", Transaction.transaction_date).label("month"),
            Transaction.type,
            func.sum(Transaction.amount).label("total"),
        )
        .group_by("month", Transaction.type)
        .order_by("month")
        .limit(months * 2)
        .all()
    )

    monthly = {}
    for row in results:
        month_key = row.month.strftime("%Y-%m") if hasattr(row.month, "strftime") else str(row.month)[:7]
        if month_key not in monthly:
            monthly[month_key] = {"month": month_key, "revenue": 0, "expenses": 0}
        if row.type == TransactionType.RECEITA:
            monthly[month_key]["revenue"] = float(row.total)
        else:
            monthly[month_key]["expenses"] = float(row.total)

    return list(monthly.values())
