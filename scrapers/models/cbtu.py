"""Modelos Pydantic para licitações da CBTU via portal gov.br."""

import hashlib
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# Classificação de documentos por nome do arquivo.
# Ordem importa: patterns mais específicos primeiro (ex: "impugna" antes de "edital")
DOC_TYPE_PATTERNS = [
    ("recurso", re.compile(r"recurso|contrarraz|impugna", re.I)),
    ("homologacao", re.compile(r"homologa", re.I)),
    ("julgamento", re.compile(r"julgamento|resultado|classifica", re.I)),
    ("termo_referencia", re.compile(r"termo.de.refer|tr[- _]|termo.referencia", re.I)),
    ("nota_tecnica", re.compile(r"nota.t[eé]cnica", re.I)),
    ("decisao", re.compile(r"decis[aã]o|despacho", re.I)),
    ("contrato", re.compile(r"contrato|minuta.de.contrato", re.I)),
    ("ata", re.compile(r"ata.de.registro|ata.srp", re.I)),
    ("aviso", re.compile(r"aviso|dou|publica", re.I)),
    ("edital", re.compile(r"edital|anexo", re.I)),
]


def classify_document(nome: str) -> str:
    """Infere o tipo do documento pelo nome do arquivo."""
    for tipo, pattern in DOC_TYPE_PATTERNS:
        if pattern.search(nome):
            return tipo
    return "outros"


class DocumentoCBTU(BaseModel):
    nome: str
    url: str
    tipo: str = "outros"

    @classmethod
    def from_link(cls, nome: str, url: str) -> "DocumentoCBTU":
        return cls(nome=nome, url=url, tipo=classify_document(nome))


# Inferência de status pela presença de documentos
def infer_status(documentos: list["DocumentoCBTU"]) -> str:
    tipos = {d.tipo for d in documentos}
    if "homologacao" in tipos:
        return "homologada"
    if "recurso" in tipos:
        return "com_recurso"
    if "julgamento" in tipos:
        return "em_julgamento"
    if "edital" in tipos or "termo_referencia" in tipos:
        return "publicada"
    return "desconhecido"


class LicitacaoCBTU(BaseModel):
    numero_processo: str
    modalidade: str
    titulo: str
    unidade_slug: str
    unidade_nome: str
    url_processo: str
    data_publicacao: Optional[datetime] = None
    data_modificacao: Optional[datetime] = None
    status: str = "desconhecido"
    documentos: list[DocumentoCBTU] = Field(default_factory=list)
    valor_estimado: Optional[float] = None
    fonte: str = "CBTU-GOVBR"
    data_coleta: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def hash_registro(self) -> str:
        content = (
            f"{self.numero_processo}|{self.modalidade}|{self.titulo}|"
            f"{self.status}|{len(self.documentos)}"
        )
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:16]
