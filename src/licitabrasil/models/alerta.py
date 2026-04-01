"""Models: Alerta e AlertaMatch."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from licitabrasil.models.base import Base, FrequenciaAlerta


class Alerta(Base):
    """Alerta configurado por um usuário para monitorar licitações."""

    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(nullable=False)
    palavras_chave: Mapped[str | None] = mapped_column(Text)  # JSON array
    modalidades: Mapped[str | None] = mapped_column(Text)  # JSON array
    esferas: Mapped[str | None] = mapped_column(Text)  # JSON array
    estados: Mapped[str | None] = mapped_column(Text)  # JSON array
    municipios: Mapped[str | None] = mapped_column(Text)  # JSON array
    segmentos: Mapped[str | None] = mapped_column(Text)  # JSON array
    valor_minimo: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    valor_maximo: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    ativo: Mapped[bool] = mapped_column(default=True)
    frequencia: Mapped[FrequenciaAlerta] = mapped_column()
    canal_notificacao: Mapped[str | None] = mapped_column(Text)  # JSON array
    ultimo_envio: Mapped[datetime | None] = mapped_column(DateTime)
    total_enviados: Mapped[int] = mapped_column(default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    licitacao_id: Mapped[int | None] = mapped_column(ForeignKey("licitacoes.id"))
    licitacao: Mapped["Licitacao | None"] = relationship(back_populates="alertas")  # noqa: F821


class AlertaMatch(Base):
    """Registro de match entre alerta e licitação."""

    __tablename__ = "alerta_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    alerta_id: Mapped[int] = mapped_column(ForeignKey("alertas.id"), nullable=False)
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacoes.id"), nullable=False)
    enviado_em: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
