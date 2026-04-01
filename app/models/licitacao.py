from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

ModalidadeEnum = SAEnum(
    "PREGAO_ELETRONICO", "PREGAO_PRESENCIAL", "CONCORRENCIA",
    "CONCORRENCIA_ELETRONICA", "TOMADA_DE_PRECOS", "CONVITE", "CONCURSO",
    "LEILAO", "DIALOGO_COMPETITIVO", "DISPENSA", "INEXIGIBILIDADE",
    "CREDENCIAMENTO", "RDC", "OUTRA",
    name="Modalidade", create_type=False,
)
StatusEnum = SAEnum(
    "PUBLICADA", "ABERTA", "EM_ANDAMENTO", "SUSPENSA", "ADIADA",
    "ENCERRADA", "ANULADA", "REVOGADA", "DESERTA", "FRACASSADA",
    "HOMOLOGADA", "ADJUDICADA",
    name="StatusLicitacao", create_type=False,
)
EsferaEnum = SAEnum("FEDERAL", "ESTADUAL", "MUNICIPAL", name="Esfera", create_type=False)


class Licitacao(Base):
    __tablename__ = "Licitacao"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    numeroProcesso: Mapped[Optional[str]] = mapped_column("numeroProcesso", String(255))
    modalidade: Mapped[str] = mapped_column(ModalidadeEnum)
    objeto: Mapped[str] = mapped_column(Text)
    orgao: Mapped[str] = mapped_column(String(500))
    uf: Mapped[Optional[str]] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(StatusEnum)
    valorEstimado: Mapped[Optional[Decimal]] = mapped_column("valorEstimado", Numeric(65, 30))
    fonteOrigem: Mapped[str] = mapped_column("fonteOrigem", String(255))
    urlOrigem: Mapped[str] = mapped_column("urlOrigem", Text)
    hashConteudo: Mapped[str] = mapped_column("hashConteudo", String(255), unique=True)
    esfera: Mapped[str] = mapped_column(EsferaEnum)
    municipio: Mapped[Optional[str]] = mapped_column(String(255))
    dataPublicacao: Mapped[datetime] = mapped_column("dataPublicacao")
    dataAbertura: Mapped[Optional[datetime]] = mapped_column("dataAbertura")
    dataEncerramento: Mapped[Optional[datetime]] = mapped_column("dataEncerramento")
    criadoEm: Mapped[datetime] = mapped_column("criadoEm", server_default=func.now())
    atualizadoEm: Mapped[datetime] = mapped_column(
        "atualizadoEm", server_default=func.now(), onupdate=func.now()
    )

    documentos: Mapped[list["Documento"]] = relationship(
        back_populates="licitacao", cascade="all, delete-orphan",
        foreign_keys="Documento.licitacaoId",
    )

    # Compatibility properties for existing route code
    @property
    def numero_processo(self) -> Optional[str]:
        return self.numeroProcesso

    @property
    def valor_estimado(self) -> Optional[Decimal]:
        return self.valorEstimado

    @property
    def fonte(self) -> str:
        return self.fonteOrigem

    @property
    def data_publicacao(self) -> datetime:
        return self.dataPublicacao

    @property
    def data_abertura(self) -> Optional[datetime]:
        return self.dataAbertura

    @property
    def data_encerramento(self) -> Optional[datetime]:
        return self.dataEncerramento

    @property
    def created_at(self) -> datetime:
        return self.criadoEm


class Documento(Base):
    __tablename__ = "Documento"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    licitacaoId: Mapped[str] = mapped_column(
        "licitacaoId", ForeignKey("Licitacao.id", ondelete="CASCADE")
    )
    nome: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(100))
    tamanho: Mapped[Optional[int]] = mapped_column()
    formato: Mapped[Optional[str]] = mapped_column(String(50))
    criadoEm: Mapped[datetime] = mapped_column("criadoEm", server_default=func.now())

    licitacao: Mapped["Licitacao"] = relationship(
        back_populates="documentos", foreign_keys=[licitacaoId]
    )


class ScraperRun(Base):
    """SQLAlchemy-only table for tracking scraper execution history."""
    __tablename__ = "scraper_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    fonte: Mapped[str] = mapped_column(String(50), index=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))  # running, success, error
    total_new: Mapped[int] = mapped_column(default=0)
    total_updated: Mapped[int] = mapped_column(default=0)
    total_unchanged: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
