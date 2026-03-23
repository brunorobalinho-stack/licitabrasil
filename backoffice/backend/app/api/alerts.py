from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Alert, User
from app.models.schemas import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=list[AlertOut])
def list_alerts(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = db.query(Alert)
    if unread_only:
        query = query.filter(Alert.is_read.is_(False))
    return query.order_by(Alert.created_at.desc()).limit(limit).all()


@router.patch("/{alert_id}/read")
def mark_read(
    alert_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert:
        alert.is_read = True
        db.commit()
    return {"ok": True}


@router.patch("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    db.query(Alert).filter(Alert.is_read.is_(False)).update({"is_read": True})
    db.commit()
    return {"ok": True}
