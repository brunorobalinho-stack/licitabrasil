"""Model: Documento."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from licitabrasil.models.base import Base


class Documento(Base):
    """Documento anexo a uma licitação (edital, ata, contrato, etc.).

    Armazena metadados do arquivo: tipo, nome, URL de download,
    tamanho em bytes e formato MIME.
    """

    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacoes.id"))
    tipo: Mapped[str] = mapped_column(String(100))
    nome: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    tamanho: Mapped[int | None] = mapped_column(Integer)
    formato: Mapped[str | None] = mapped_column(String(50))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    licitacao: Mapped["Licitacao"] = relationship(back_populates="documentos")  # noqa: F821
