"""Shim de retrocompatibilidade — use licitabrasil.models diretamente."""

from licitabrasil.models import (  # noqa: F401
    Alerta,
    AlertaMatch,
    Base,
    CriterioJulgamento,
    Documento,
    Esfera,
    FonteDados,
    FrequenciaAlerta,
    Licitacao,
    Lote,
    ModalidadeLicitacao,
    Orgao,
    PerfilEmpresa,
    Role,
    StatusLicitacao,
    TipoLicitacao,
    Usuario,
)
