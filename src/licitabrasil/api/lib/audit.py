"""SQLAlchemy event-based audit logging for FastAPI stack."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from ..models.audit_log import AuditLog

logger = logging.getLogger(__name__)

AUDITED_TABLES = {"Usuario", "Licitacao", "Documento"}


def _serialize(obj) -> dict | None:
    """Convert an ORM instance to a JSON-safe dict."""
    if obj is None:
        return None
    mapper = inspect(type(obj))
    data = {}
    for col in mapper.columns:
        val = getattr(obj, col.key, None)
        if isinstance(val, datetime):
            val = val.isoformat()
        elif hasattr(val, "__str__") and not isinstance(val, (str, int, float, bool, type(None))):
            val = str(val)
        data[col.key] = val
    return data


def _write_audit_sync(connection, action: str, table: str, record_id: str, old_value, new_value):
    """Synchronous INSERT via the same connection (runs in flush context)."""
    try:
        connection.execute(
            AuditLog.__table__.insert().values(
                id=f"aud_{uuid.uuid4().hex[:20]}",
                action=action,
                model=table,
                recordId=record_id,
                oldValue=old_value,
                newValue=new_value,
                criadoEm=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
    except Exception:
        logger.warning("Audit log write failed for %s %s", action, table, exc_info=True)


def enable_audit_logging():
    """Register SQLAlchemy after_insert/after_update/after_delete listeners."""

    @event.listens_for(Session, "after_flush")
    def after_flush(session, flush_context):
        for obj in session.new:
            table = type(obj).__tablename__
            if table not in AUDITED_TABLES:
                continue
            record_id = str(getattr(obj, "id", "unknown"))
            new_value = _serialize(obj)
            _write_audit_sync(session.connection(), "CREATE", table, record_id, None, new_value)

        for obj in session.dirty:
            table = type(obj).__tablename__
            if table not in AUDITED_TABLES:
                continue
            record_id = str(getattr(obj, "id", "unknown"))
            history = inspect(obj)
            old_value = {}
            new_value = _serialize(obj)
            for attr in history.attrs:
                hist = attr.history
                if hist.has_changes():
                    old_value[attr.key] = hist.deleted[0] if hist.deleted else None
                    if isinstance(old_value[attr.key], datetime):
                        old_value[attr.key] = old_value[attr.key].isoformat()
            if old_value:
                _write_audit_sync(session.connection(), "UPDATE", table, record_id, old_value, new_value)

        for obj in session.deleted:
            table = type(obj).__tablename__
            if table not in AUDITED_TABLES:
                continue
            record_id = str(getattr(obj, "id", "unknown"))
            old_value = _serialize(obj)
            _write_audit_sync(session.connection(), "DELETE", table, record_id, old_value, None)
