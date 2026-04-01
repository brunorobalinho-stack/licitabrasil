"""Model: PerfilEmpresa (matching de licitações)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ARRAY, DateTime, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from licitabrasil.models.base import Base


class PerfilEmpresa(Base):
    """Perfil de empresa para matching com licitações."""

    __tablename__ = "perfil_empresa"

    id: Mapped[str] = mapped_column("id", Text, primary_key=True)
    usuario_id: Mapped[str | None] = mapped_column("usuario_id", Text)
    cnpj: Mapped[str] = mapped_column("cnpj", Text, nullable=False, unique=True)
    razao_social: Mapped[str] = mapped_column("razao_social", Text, nullable=False)
    cnaes: Mapped[list[str] | None] = mapped_column("cnaes", ARRAY(Text))
    palavras_chave: Mapped[list[str] | None] = mapped_column("palavras_chave", ARRAY(Text))
    valor_minimo: Mapped[Decimal | None] = mapped_column("valor_minimo", Numeric)
    valor_maximo: Mapped[Decimal | None] = mapped_column("valor_maximo", Numeric)
    estados: Mapped[list[str] | None] = mapped_column("estados", ARRAY(Text))
    municipios: Mapped[list[str] | None] = mapped_column("municipios", ARRAY(Text))
    modalidades: Mapped[list[str] | None] = mapped_column("modalidades", ARRAY(Text))
    endereco: Mapped[str | None] = mapped_column("endereco", Text)
    telefone: Mapped[str | None] = mapped_column("telefone", Text)
    email: Mapped[str | None] = mapped_column("email", Text)
    representante_legal: Mapped[str | None] = mapped_column("representante_legal", Text)
    dados_bancarios = mapped_column("dados_bancarios", JSONB, nullable=True)
    criado_em: Mapped[datetime] = mapped_column("criado_em", DateTime, nullable=False, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column("atualizado_em", DateTime, nullable=False, server_default=func.now())
