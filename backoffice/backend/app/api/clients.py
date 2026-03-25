import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Client, User
from app.models.schemas import ClientCreate, ClientOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(Client).filter(Client.is_active.is_(True)).all()


@router.post("/", response_model=ClientOut, status_code=201)
def create_client(
    data: ClientCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    existing = db.query(Client).filter(Client.cnpj == data.cnpj).first()
    if existing:
        raise HTTPException(status_code=409, detail="CNPJ já cadastrado")
    client = Client(**data.model_dump())
    db.add(client)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="CNPJ já cadastrado (conflito)")
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client
