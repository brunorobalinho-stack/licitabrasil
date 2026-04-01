"""Model: Lote (itens/lotes de uma licitação)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from licitabrasil.models.base import Base


class Lote(Base):
    """Lote ou item individual de uma licitação."""

    __tablename__ = "lotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacoes.id"))
    numero: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str] = mapped_column(Text)
    quantidade: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    unidade: Mapped[str | None] = mapped_column(String(50))
    valor_unitario: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    valor_total: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    codigo_catalogo: Mapped[str | None] = mapped_column(String(50))
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())

    licitacao: Mapped["Licitacao"] = relationship(back_populates="lotes")  # noqa: F821
