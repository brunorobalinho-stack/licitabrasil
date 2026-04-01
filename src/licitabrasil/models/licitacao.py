"""Model: Licitacao."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from licitabrasil.models.base import (
    Base,
    CriterioJulgamento,
    ModalidadeLicitacao,
    StatusLicitacao,
)


class Licitacao(Base):
    """Licitação pública coletada de portais governamentais."""

    __tablename__ = "licitacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(100), index=True)
    numero_original: Mapped[str] = mapped_column(String(200))
    ano: Mapped[int]
    processo: Mapped[str | None] = mapped_column(String(100))
    uasg: Mapped[str | None] = mapped_column(String(20))

    modalidade: Mapped[ModalidadeLicitacao]
    status: Mapped[StatusLicitacao] = mapped_column(default=StatusLicitacao.PUBLICADA)
    criterio_julgamento: Mapped[CriterioJulgamento | None]
    tipo_contratacao: Mapped[str | None] = mapped_column(String(50))

    objeto: Mapped[str] = mapped_column(Text)
    objeto_resumido: Mapped[str | None] = mapped_column(String(500))

    valor_estimado: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    valor_homologado: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))

    data_publicacao: Mapped[datetime | None]
    data_abertura: Mapped[datetime | None]
    data_encerramento: Mapped[datetime | None]
    data_homologacao: Mapped[datetime | None]

    # LC 123/2006 — tratamento diferenciado ME/EPP
    exclusiva_me_epp: Mapped[bool] = mapped_column(default=False)
    cota_reservada: Mapped[bool] = mapped_column(default=False)
    margem_preferencia: Mapped[bool] = mapped_column(default=False)

    # Origem
    portal_origem: Mapped[str] = mapped_column(String(50))
    url_original: Mapped[str] = mapped_column(Text)
    url_edital: Mapped[str | None] = mapped_column(Text)

    # Controle
    coletado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    hash_conteudo: Mapped[str] = mapped_column(String(64))

    # Classificação (preenchidos por processadores)
    cnaes_detectados: Mapped[str | None] = mapped_column(Text)  # JSON array
    segmentos: Mapped[str | None] = mapped_column(Text)  # JSON array
    keywords: Mapped[str | None] = mapped_column(Text)  # JSON array
    score_relevancia: Mapped[float | None]

    # Relacionamentos
    orgao_id: Mapped[int] = mapped_column(ForeignKey("orgaos.id"))
    orgao: Mapped["Orgao"] = relationship(back_populates="licitacoes")  # noqa: F821
    lotes: Mapped[list["Lote"]] = relationship(  # noqa: F821
        back_populates="licitacao", cascade="all, delete-orphan"
    )
    documentos: Mapped[list["Documento"]] = relationship(back_populates="licitacao")  # noqa: F821
    alertas: Mapped[list["Alerta"]] = relationship(back_populates="licitacao")  # noqa: F821

    __table_args__ = (
        Index("ix_licitacao_portal_numero", "portal_origem", "numero", unique=True),
        Index("ix_licitacao_abertura", "data_abertura"),
        Index("ix_licitacao_status_modalidade", "status", "modalidade"),
    )
