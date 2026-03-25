import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Client, Contract, ContractStatus, User
from app.models.schemas import ContractCreate, ContractOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("/", response_model=list[ContractOut])
def list_contracts(
    status: ContractStatus | None = None,
    client_id: int | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = db.query(Contract).options(joinedload(Contract.client))
    if status:
        query = query.filter(Contract.status == status)
    if client_id:
        query = query.filter(Contract.client_id == client_id)
    contracts = query.order_by(Contract.end_date.asc()).all()

    result = []
    for c in contracts:
        out = ContractOut.model_validate(c)
        out.client_name = c.client.name if c.client else None
        result.append(out)
    return result


@router.post("/", response_model=ContractOut, status_code=201)
def create_contract(
    data: ContractCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    # Validate client exists
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    contract = Contract(**data.model_dump())
    db.add(contract)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Número do contrato já existe")
    db.refresh(contract)
    return ContractOut.model_validate(contract)
