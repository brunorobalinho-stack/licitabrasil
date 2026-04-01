"""Models: Orgao e FonteDados."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from licitabrasil.models.base import Base, Esfera


class Orgao(Base):
    """Órgão público responsável pela licitação."""

    __tablename__ = "orgaos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(500))
    sigla: Mapped[str | None] = mapped_column(String(50))
    cnpj: Mapped[str | None] = mapped_column(String(18), unique=True)
    esfera: Mapped[Esfera | None] = mapped_column()
    uf: Mapped[str | None] = mapped_column(String(2))
    municipio: Mapped[str | None] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    licitacoes: Mapped[list["Licitacao"]] = relationship(back_populates="orgao")  # noqa: F821


class FonteDados(Base):
    """Configuração de fonte de dados (scraper)."""

    __tablename__ = "FonteDados"

    id: Mapped[str] = mapped_column("id", Text, primary_key=True)
    nome: Mapped[str] = mapped_column("nome", Text, nullable=False, unique=True)
    url: Mapped[str] = mapped_column("url", Text, nullable=False)
    tipo: Mapped[str] = mapped_column("tipo", Text, nullable=False)
    esfera: Mapped[Esfera] = mapped_column("esfera", nullable=False)
    ativo: Mapped[bool] = mapped_column("ativo", Boolean, nullable=False, server_default=text("true"))
    ultima_coleta: Mapped[datetime | None] = mapped_column("ultimaColeta", DateTime)
    ultimo_sucesso: Mapped[datetime | None] = mapped_column("ultimoSucesso", DateTime)
    ultima_falha: Mapped[datetime | None] = mapped_column("ultimaFalha", DateTime)
    total_coletados: Mapped[int] = mapped_column("totalColetados", Integer, nullable=False, server_default=text("0"))
    total_erros: Mapped[int] = mapped_column("totalErros", Integer, nullable=False, server_default=text("0"))
    intervalo_minutos: Mapped[int] = mapped_column("intervaloMinutos", Integer, nullable=False, server_default=text("30"))
    configuracao = mapped_column("configuracao", JSONB, nullable=True)
    criado_em: Mapped[datetime] = mapped_column("criadoEm", DateTime, nullable=False, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column("atualizadoEm", DateTime, nullable=False)
