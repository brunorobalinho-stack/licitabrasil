"""Modelos Pydantic para licitações da Prefeitura de SP (via PNCP)."""

import hashlib
import json
from datetime import datetime

from pydantic import BaseModel, Field, computed_field


class OrgaoSP(BaseModel):
    cnpj: str = ""
    razao_social: str = ""
    esfera: str = "M"
    poder: str = ""
    unidade_nome: str = ""
    unidade_codigo: str = ""


class LicitacaoSP(BaseModel):
    numero_controle_pncp: str
    numero_compra: str = ""
    sequencial_compra: int = 0
    numero_processo: str = ""
    ano_compra: int = 0

    orgao: OrgaoSP = Field(default_factory=OrgaoSP)

    modalidade_id: int = 0
    modalidade: str = ""
    modo_disputa_id: int | None = None
    modo_disputa: str = ""
    tipo_instrumento: str = ""
    amparo_legal: str = ""

    objeto: str = ""
    valor_estimado: float | None = None
    valor_homologado: float | None = None
    informacao_complementar: str = ""

    data_publicacao: str = ""
    data_abertura: str = ""
    data_encerramento: str = ""

    situacao_id: int | None = None
    situacao: str = ""
    srp: bool = False

    link_sistema_origem: str = ""
    link_processo_eletronico: str = ""

    # Metadata
    fonte: str = "PNCP-PMSP"
    uf: str = "SP"
    municipio: str = "São Paulo"
    tem_detalhe: bool = False
    data_coleta: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def hash_registro(self) -> str:
        data = {
            "pncp": self.numero_controle_pncp,
            "objeto": self.objeto,
            "situacao": self.situacao,
            "valor_est": self.valor_estimado,
            "valor_hom": self.valor_homologado,
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    @computed_field
    @property
    def url_pncp(self) -> str:
        if not self.numero_controle_pncp:
            return ""
        # Format: cnpj-ano-sequencial -> PNCP URL
        return f"https://pncp.gov.br/app/editais/{self.numero_controle_pncp}"


def parse_api_item(item: dict) -> LicitacaoSP | None:
    """Converte um item da API PNCP em LicitacaoSP.

    Retorna None se o item não for da esfera Municipal.
    """
    orgao_data = item.get("orgaoEntidade", {})
    unidade_data = item.get("unidadeOrgao", {})

    # Filtrar apenas esfera Municipal
    if orgao_data.get("esferaId") != "M":
        return None

    orgao = OrgaoSP(
        cnpj=orgao_data.get("cnpj", ""),
        razao_social=orgao_data.get("razaoSocial", ""),
        esfera=orgao_data.get("esferaId", "M"),
        poder=orgao_data.get("poderId", ""),
        unidade_nome=unidade_data.get("nomeUnidade", ""),
        unidade_codigo=unidade_data.get("codigoUnidade", ""),
    )

    amparo = item.get("amparoLegal") or {}

    return LicitacaoSP(
        numero_controle_pncp=item.get("numeroControlePNCP", ""),
        numero_compra=item.get("numeroCompra", ""),
        sequencial_compra=item.get("sequencialCompra", 0),
        numero_processo=item.get("processo", ""),
        ano_compra=item.get("anoCompra", 0),
        orgao=orgao,
        modalidade_id=item.get("modalidadeId", 0),
        modalidade=item.get("modalidadeNome", ""),
        modo_disputa_id=item.get("modoDisputaId"),
        modo_disputa=item.get("modoDisputaNome", ""),
        tipo_instrumento=item.get("tipoInstrumentoConvocatorioNome", ""),
        amparo_legal=amparo.get("nome", ""),
        objeto=item.get("objetoCompra", ""),
        valor_estimado=item.get("valorTotalEstimado"),
        valor_homologado=item.get("valorTotalHomologado"),
        informacao_complementar=item.get("informacaoComplementar", "") or "",
        data_publicacao=item.get("dataPublicacaoPncp", "") or "",
        data_abertura=item.get("dataAberturaProposta", "") or "",
        data_encerramento=item.get("dataEncerramentoProposta", "") or "",
        situacao_id=item.get("situacaoCompraId"),
        situacao=item.get("situacaoCompraNome", ""),
        srp=item.get("srp", False),
        link_sistema_origem=item.get("linkSistemaOrigem", "") or "",
        link_processo_eletronico=item.get("linkProcessoEletronico", "") or "",
    )
