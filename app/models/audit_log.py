"""AuditLog model — tracks all data mutations for compliance."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class AuditLog(Base):
    __tablename__ = "AuditLog"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    action: Mapped[str] = mapped_column(String, nullable=False)  # CREATE, UPDATE, DELETE
    model: Mapped[str] = mapped_column(String, nullable=False)
    recordId: Mapped[str] = mapped_column("recordId", String, nullable=False)
    oldValue: Mapped[Optional[dict]] = mapped_column("oldValue", JSONB, nullable=True)
    newValue: Mapped[Optional[dict]] = mapped_column("newValue", JSONB, nullable=True)
    userId: Mapped[Optional[str]] = mapped_column("userId", String, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    criadoEm: Mapped[datetime] = mapped_column("criadoEm", server_default=func.now())
