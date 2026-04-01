"""Model: Usuario."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from licitabrasil.models.base import Base, Role


class Usuario(Base):
    """Conta de usuário do sistema LicitaBrasil."""

    __tablename__ = "Usuario"

    id: Mapped[str] = mapped_column("id", Text, primary_key=True)
    email: Mapped[str] = mapped_column("email", Text, nullable=False, unique=True)
    nome: Mapped[str] = mapped_column("nome", Text, nullable=False)
    empresa: Mapped[str | None] = mapped_column("empresa", Text)
    cnpj: Mapped[str | None] = mapped_column("cnpj", Text)
    senha: Mapped[str] = mapped_column("senha", Text, nullable=False)
    role: Mapped[Role] = mapped_column("role", Enum(Role), nullable=False, server_default=text("'USER'"))
    reset_token: Mapped[str | None] = mapped_column("resetToken", String)
    reset_token_expiry: Mapped[datetime | None] = mapped_column("resetTokenExpiry", DateTime)
    criado_em: Mapped[datetime] = mapped_column("criadoEm", DateTime, nullable=False, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column("atualizadoEm", DateTime, nullable=False)
