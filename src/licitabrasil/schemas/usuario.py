"""Schemas de usuário."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UsuarioCreate(BaseModel):
    """Criação de usuário."""

    email: EmailStr
    nome: str
    senha: str
    empresa: str | None = None
    cnpj: str | None = None


class UsuarioRead(BaseModel):
    """Leitura de usuário (sem senha)."""

    model_config = {"from_attributes": True}

    id: str
    email: str
    nome: str
    empresa: str | None = None
    cnpj: str | None = None
    role: str
    criado_em: datetime
