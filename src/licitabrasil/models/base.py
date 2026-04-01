"""Enums, Base declarativa e tipos compartilhados."""

from __future__ import annotations

import enum

from sqlalchemy.orm import DeclarativeBase


# ---------------------------------------------------------------------------
# Enums — modelos standalone (novos, lowercase)
# ---------------------------------------------------------------------------

class ModalidadeLicitacao(str, enum.Enum):
    PREGAO_ELETRONICO = "pregao_eletronico"
    PREGAO_PRESENCIAL = "pregao_presencial"
    CONCORRENCIA = "concorrencia"
    TOMADA_PRECOS = "tomada_precos"
    CONVITE = "convite"
    CONCURSO = "concurso"
    DIALOGO_COMPETITIVO = "dialogo_competitivo"
    DISPENSA = "dispensa"
    INEXIGIBILIDADE = "inexigibilidade"
    LEILAO = "leilao"


class StatusLicitacao(str, enum.Enum):
    PUBLICADA = "publicada"
    ABERTA = "aberta"
    EM_ANDAMENTO = "em_andamento"
    SUSPENSA = "suspensa"
    ENCERRADA = "encerrada"
    DESERTA = "deserta"
    FRACASSADA = "fracassada"
    REVOGADA = "revogada"
    ANULADA = "anulada"
    HOMOLOGADA = "homologada"
    ADJUDICADA = "adjudicada"


class CriterioJulgamento(str, enum.Enum):
    MENOR_PRECO = "menor_preco"
    MAIOR_DESCONTO = "maior_desconto"
    MELHOR_TECNICA = "melhor_tecnica"
    TECNICA_PRECO = "tecnica_preco"
    MAIOR_LANCE = "maior_lance"
    MAIOR_RETORNO = "maior_retorno"


class Esfera(str, enum.Enum):
    FEDERAL = "FEDERAL"
    ESTADUAL = "ESTADUAL"
    MUNICIPAL = "MUNICIPAL"


class TipoLicitacao(str, enum.Enum):
    COMPRA = "COMPRA"
    SERVICO = "SERVICO"
    OBRA = "OBRA"
    SERVICO_ENGENHARIA = "SERVICO_ENGENHARIA"
    ALIENACAO = "ALIENACAO"
    CONCESSAO = "CONCESSAO"
    PERMISSAO = "PERMISSAO"
    LOCACAO = "LOCACAO"
    OUTRO = "OUTRO"


class FrequenciaAlerta(str, enum.Enum):
    TEMPO_REAL = "TEMPO_REAL"
    DIARIO = "DIARIO"
    SEMANAL = "SEMANAL"


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    USER = "USER"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass
