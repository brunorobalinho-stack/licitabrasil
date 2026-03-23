from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Client, EmailPriority, EmailRecord, User
from app.models.schemas import EmailRecordOut

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("/", response_model=list[EmailRecordOut])
def list_emails(
    client_id: int | None = None,
    priority: EmailPriority | None = None,
    unread_only: bool = False,
    actionable_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = db.query(EmailRecord)
    if client_id:
        query = query.filter(EmailRecord.client_id == client_id)
    if priority:
        query = query.filter(EmailRecord.priority == priority)
    if unread_only:
        query = query.filter(EmailRecord.is_read.is_(False))
    if actionable_only:
        query = query.filter(EmailRecord.is_actionable.is_(True))

    emails = query.order_by(EmailRecord.received_at.desc()).limit(limit).all()

    result = []
    for e in emails:
        out = EmailRecordOut.model_validate(e)
        if e.client:
            out.client_name = e.client.name
        result.append(out)
    return result


@router.patch("/{email_id}/read")
def mark_email_read(
    email_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    email = db.query(EmailRecord).filter(EmailRecord.id == email_id).first()
    if email:
        email.is_read = True
        db.commit()
    return {"ok": True}
