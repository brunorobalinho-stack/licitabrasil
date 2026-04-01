"""AlertEngine — motor de regras para alertas de licitações.

Tipos de alerta:
1. NOVA_OPORTUNIDADE — Match score >= threshold (imediato)
2. PRAZO_CRITICO — Abertura/impugnação/esclarecimento vencendo (24h, 48h, 72h)
3. MUDANCA_STATUS — Licitação suspensa/revogada/retificada/prorrogada
4. INTELIGENCIA_MERCADO — Órgão frequente, volume acima/abaixo da média (digest semanal)
5. COMPLIANCE — Certidão vencendo, documento desatualizado

Anti-spam:
- Rate limit por empresa+canal (configurable cooldown)
- Consolidação de alertas do mesmo tipo em digest
- Quiet hours: horário comercial (configurable)
- Priorização: score × urgência
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TipoAlerta(str, Enum):
    """Tipos de alerta suportados."""
    NOVA_OPORTUNIDADE = "nova_oportunidade"
    PRAZO_CRITICO = "prazo_critico"
    MUDANCA_STATUS = "mudanca_status"
    INTELIGENCIA_MERCADO = "inteligencia_mercado"
    COMPLIANCE = "compliance"


class CanalNotificacao(str, Enum):
    """Canais de entrega disponíveis."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PUSH = "push"
    WEBHOOK = "webhook"


class Urgencia(str, Enum):
    """Nível de urgência do alerta."""
    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


# ---------------------------------------------------------------------------
# Models de entrada (Pydantic, desacoplados do SQLAlchemy)
# ---------------------------------------------------------------------------

class FiltroAlerta(BaseModel):
    """Filtros configurados em um alerta de monitoramento.

    Espelha os campos do model Alerta do banco, mas como Pydantic puro
    para permitir avaliação sem acesso ao SQLAlchemy.
    """
    id: int
    usuario_id: int
    palavras_chave: list[str] = Field(default_factory=list)
    modalidades: list[str] = Field(default_factory=list)
    esferas: list[str] = Field(default_factory=list)
    estados: list[str] = Field(default_factory=list)
    municipios: list[str] = Field(default_factory=list)
    segmentos: list[str] = Field(default_factory=list)
    valor_minimo: Decimal | None = None
    valor_maximo: Decimal | None = None
    frequencia: str = "DIARIO"
    canais: list[CanalNotificacao] = Field(default_factory=lambda: [CanalNotificacao.EMAIL])

    # Anti-spam
    ultimo_envio: datetime | None = None
    total_enviados: int = 0


class LicitacaoResumida(BaseModel):
    """Dados mínimos de uma licitação para avaliação de alertas.

    Faz o papel de DTO: quem chama o engine converte do SQLAlchemy
    ou de qualquer fonte para este formato.
    """
    id: int
    numero: str = ""
    objeto: str = ""
    modalidade: str = ""
    esfera: str = ""
    status: str = ""
    status_anterior: str | None = None  # Para detectar mudança
    valor_estimado: Decimal | None = None
    data_abertura: datetime | None = None
    data_publicacao: datetime | None = None
    uf: str | None = None
    municipio: str | None = None
    orgao_nome: str = ""
    segmentos: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    match_score: float | None = None  # Score do MatchEngine, se disponível


class DocumentoCompliance(BaseModel):
    """Documento ou certidão com data de validade."""
    nome: str
    data_validade: datetime
    empresa_cnpj: str


# ---------------------------------------------------------------------------
# Models de saída
# ---------------------------------------------------------------------------

class AlertaGerado(BaseModel):
    """Alerta gerado pelo engine, pronto para envio."""
    tipo: TipoAlerta
    urgencia: Urgencia
    titulo: str
    mensagem: str
    detalhes: dict = Field(default_factory=dict)
    canais: list[CanalNotificacao] = Field(default_factory=list)
    alerta_id: int | None = None  # ID do FiltroAlerta que gerou
    licitacao_id: int | None = None
    usuario_id: int | None = None
    prioridade: float = 0.0  # score × urgencia, para ordenação


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

class ConfigAntiSpam(BaseModel):
    """Configuração do anti-spam."""
    cooldown_minutos: int = 60  # Mínimo entre envios do mesmo tipo
    max_por_hora: int = 10  # Máximo de alertas por empresa por hora
    max_por_dia: int = 50  # Máximo de alertas por empresa por dia
    quiet_hour_inicio: int = 22  # Não enviar após 22h
    quiet_hour_fim: int = 7  # Não enviar antes das 7h
    consolidar_digest: bool = True  # Agrupa alertas do mesmo tipo


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Score mínimo do MatchEngine para gerar alerta NOVA_OPORTUNIDADE
MATCH_THRESHOLD_PADRAO = 0.5

# Prazos críticos em horas
PRAZOS_CRITICOS_HORAS = [24, 48, 72]

# Status que geram alerta de MUDANCA_STATUS
STATUS_ALERTAVEIS = {"suspensa", "revogada", "anulada", "fracassada", "deserta"}

# Peso de urgência para cálculo de prioridade
PESOS_URGENCIA: dict[Urgencia, float] = {
    Urgencia.CRITICA: 1.0,
    Urgencia.ALTA: 0.75,
    Urgencia.MEDIA: 0.5,
    Urgencia.BAIXA: 0.25,
}

# Dias antes do vencimento para alertar compliance
COMPLIANCE_DIAS_ALERTA = [30, 15, 7, 3, 1]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AlertEngine:
    """Motor de regras para avaliação e geração de alertas.

    Uso típico (pipeline):
        engine = AlertEngine()
        alertas_filtro = [FiltroAlerta(...), ...]  # Carregados do banco
        licitacoes = [LicitacaoResumida(...), ...]  # Novas ou atualizadas

        gerados = engine.avaliar(alertas_filtro, licitacoes)
        # → lista de AlertaGerado prontos para envio via Notifier

    Uso compliance:
        docs = [DocumentoCompliance(...), ...]
        alertas = engine.verificar_compliance(docs, data_referencia=datetime.now())
    """

    def __init__(
        self,
        config: ConfigAntiSpam | None = None,
        match_threshold: float = MATCH_THRESHOLD_PADRAO,
    ):
        """Inicializa o motor de alertas.

        Args:
            config: Configuração anti-spam. Usa padrão se não informada.
            match_threshold: Score mínimo para gerar alerta de nova oportunidade.
        """
        self.config = config or ConfigAntiSpam()
        self.match_threshold = match_threshold
        self._envios_recentes: dict[str, list[datetime]] = {}  # chave: "{usuario_id}:{tipo}"

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------

    def avaliar(
        self,
        filtros: list[FiltroAlerta],
        licitacoes: list[LicitacaoResumida],
        agora: datetime | None = None,
    ) -> list[AlertaGerado]:
        """Avalia licitações contra todos os filtros e gera alertas.

        Executa na ordem:
        1. NOVA_OPORTUNIDADE — licitações que batem com filtros
        2. PRAZO_CRITICO — abertura iminente
        3. MUDANCA_STATUS — status mudou para alertável

        Returns:
            Lista de AlertaGerado, ordenada por prioridade (desc).
        """
        agora = agora or datetime.now()
        alertas: list[AlertaGerado] = []

        for filtro in filtros:
            for lic in licitacoes:
                # 1. Nova oportunidade
                if self._match_filtro(filtro, lic):
                    alerta = self._gerar_nova_oportunidade(filtro, lic)
                    if alerta:
                        alertas.append(alerta)

                # 2. Prazo crítico
                alerta_prazo = self._verificar_prazo_critico(filtro, lic, agora)
                if alerta_prazo:
                    alertas.append(alerta_prazo)

                # 3. Mudança de status
                alerta_status = self._verificar_mudanca_status(filtro, lic)
                if alerta_status:
                    alertas.append(alerta_status)

        # Anti-spam: filtra, consolida, ordena
        alertas = self._aplicar_antispam(alertas, agora)
        alertas.sort(key=lambda a: a.prioridade, reverse=True)

        return alertas

    def verificar_compliance(
        self,
        documentos: list[DocumentoCompliance],
        data_referencia: datetime | None = None,
    ) -> list[AlertaGerado]:
        """Verifica documentos/certidões próximos do vencimento.

        Args:
            documentos: Lista de documentos com datas de validade.
            data_referencia: Data base para cálculo (padrão: agora).

        Returns:
            Lista de AlertaGerado de compliance.
        """
        data_ref = data_referencia or datetime.now()
        alertas: list[AlertaGerado] = []

        for doc in documentos:
            dias_restantes = (doc.data_validade - data_ref).days

            if dias_restantes < 0:
                # Já vencido
                alertas.append(AlertaGerado(
                    tipo=TipoAlerta.COMPLIANCE,
                    urgencia=Urgencia.CRITICA,
                    titulo=f"{doc.nome} VENCIDO",
                    mensagem=(
                        f"O documento {doc.nome} da empresa {doc.empresa_cnpj} "
                        f"venceu há {abs(dias_restantes)} dia(s)"
                    ),
                    detalhes={
                        "documento": doc.nome,
                        "vencimento": doc.data_validade.isoformat(),
                        "dias_restantes": dias_restantes,
                        "cnpj": doc.empresa_cnpj,
                    },
                    canais=[CanalNotificacao.EMAIL, CanalNotificacao.WHATSAPP],
                    prioridade=1.0,
                ))
            elif 0 <= dias_restantes <= max(COMPLIANCE_DIAS_ALERTA):
                urgencia = self._urgencia_compliance(dias_restantes)
                alertas.append(AlertaGerado(
                    tipo=TipoAlerta.COMPLIANCE,
                    urgencia=urgencia,
                    titulo=f"{doc.nome} vence em {dias_restantes} dia(s)",
                    mensagem=(
                        f"O documento {doc.nome} da empresa {doc.empresa_cnpj} "
                        f"vence em {doc.data_validade.strftime('%d/%m/%Y')} "
                        f"({dias_restantes} dias)"
                    ),
                    detalhes={
                        "documento": doc.nome,
                        "vencimento": doc.data_validade.isoformat(),
                        "dias_restantes": dias_restantes,
                        "cnpj": doc.empresa_cnpj,
                    },
                    canais=[CanalNotificacao.EMAIL],
                    prioridade=PESOS_URGENCIA[urgencia],
                ))

        alertas.sort(key=lambda a: a.prioridade, reverse=True)
        return alertas

    def avaliar_inteligencia_mercado(
        self,
        orgao_nome: str,
        total_licitacoes_periodo: int,
        media_historica: float,
    ) -> AlertaGerado | None:
        """Gera alerta de inteligência de mercado.

        Compara volume de licitações de um órgão no período com a média histórica.
        """
        if media_historica <= 0:
            return None

        variacao = (total_licitacoes_periodo - media_historica) / media_historica * 100

        if abs(variacao) < 20:
            return None  # Dentro do normal

        if variacao > 0:
            titulo = f"Volume alto de licitações: {orgao_nome}"
            mensagem = (
                f"{orgao_nome} publicou {total_licitacoes_periodo} licitações no período, "
                f"{variacao:+.0f}% acima da média histórica ({media_historica:.0f})"
            )
        else:
            titulo = f"Volume baixo de licitações: {orgao_nome}"
            mensagem = (
                f"{orgao_nome} publicou {total_licitacoes_periodo} licitações no período, "
                f"{variacao:+.0f}% abaixo da média histórica ({media_historica:.0f})"
            )

        return AlertaGerado(
            tipo=TipoAlerta.INTELIGENCIA_MERCADO,
            urgencia=Urgencia.BAIXA,
            titulo=titulo,
            mensagem=mensagem,
            detalhes={
                "orgao": orgao_nome,
                "total_periodo": total_licitacoes_periodo,
                "media_historica": media_historica,
                "variacao_pct": round(variacao, 1),
            },
            canais=[CanalNotificacao.EMAIL],
            prioridade=PESOS_URGENCIA[Urgencia.BAIXA],
        )

    # ------------------------------------------------------------------
    # Matching de filtros
    # ------------------------------------------------------------------

    def _match_filtro(self, filtro: FiltroAlerta, lic: LicitacaoResumida) -> bool:
        """Verifica se a licitação bate com os filtros do alerta.

        Todos os filtros preenchidos devem casar (AND).
        Filtros vazios são ignorados (wildcard).
        """
        # Match score do MatchEngine (se disponível)
        if lic.match_score is not None and lic.match_score >= self.match_threshold:
            return True

        # Palavras-chave: ao menos uma deve aparecer no objeto
        if filtro.palavras_chave:
            objeto_lower = lic.objeto.lower()
            if not any(kw.lower() in objeto_lower for kw in filtro.palavras_chave):
                return False

        # Modalidade
        if filtro.modalidades:
            if lic.modalidade and lic.modalidade.lower() not in [m.lower() for m in filtro.modalidades]:
                return False

        # Esfera
        if filtro.esferas:
            if lic.esfera and lic.esfera.upper() not in [e.upper() for e in filtro.esferas]:
                return False

        # Estado (UF)
        if filtro.estados:
            if lic.uf and lic.uf.upper() not in [e.upper() for e in filtro.estados]:
                return False

        # Município
        if filtro.municipios:
            if lic.municipio and lic.municipio.upper() not in [m.upper() for m in filtro.municipios]:
                return False

        # Faixa de valor
        if filtro.valor_minimo is not None and lic.valor_estimado is not None:
            if lic.valor_estimado < filtro.valor_minimo:
                return False
        if filtro.valor_maximo is not None and lic.valor_estimado is not None:
            if lic.valor_estimado > filtro.valor_maximo:
                return False

        # Segmentos
        if filtro.segmentos:
            if not (set(s.lower() for s in lic.segmentos) & set(s.lower() for s in filtro.segmentos)):
                return False

        # Passou em tudo (ou sem filtros = wildcard)
        return True

    # ------------------------------------------------------------------
    # Geradores de alerta por tipo
    # ------------------------------------------------------------------

    def _gerar_nova_oportunidade(
        self,
        filtro: FiltroAlerta,
        lic: LicitacaoResumida,
    ) -> AlertaGerado:
        """Gera alerta de nova oportunidade."""
        score = lic.match_score or 0.5
        urgencia = Urgencia.ALTA if score >= 0.7 else Urgencia.MEDIA

        prazo_texto = ""
        if lic.data_abertura:
            dias = (lic.data_abertura - datetime.now()).days
            if dias > 0:
                prazo_texto = f" | Abertura em {dias} dia(s)"

        valor_texto = ""
        if lic.valor_estimado:
            valor_texto = f" | R$ {lic.valor_estimado:,.2f}"

        return AlertaGerado(
            tipo=TipoAlerta.NOVA_OPORTUNIDADE,
            urgencia=urgencia,
            titulo=f"Nova oportunidade: {lic.numero or lic.objeto[:60]}",
            mensagem=(
                f"{lic.objeto[:200]}\n"
                f"Órgão: {lic.orgao_nome}{valor_texto}{prazo_texto}"
            ),
            detalhes={
                "licitacao_numero": lic.numero,
                "orgao": lic.orgao_nome,
                "modalidade": lic.modalidade,
                "valor_estimado": str(lic.valor_estimado) if lic.valor_estimado else None,
                "match_score": score,
            },
            canais=filtro.canais,
            alerta_id=filtro.id,
            licitacao_id=lic.id,
            usuario_id=filtro.usuario_id,
            prioridade=score * PESOS_URGENCIA[urgencia],
        )

    def _verificar_prazo_critico(
        self,
        filtro: FiltroAlerta,
        lic: LicitacaoResumida,
        agora: datetime,
    ) -> AlertaGerado | None:
        """Verifica se a abertura é iminente (24h, 48h ou 72h)."""
        if not lic.data_abertura:
            return None

        horas_restantes = (lic.data_abertura - agora).total_seconds() / 3600
        if horas_restantes < 0:
            return None  # Já passou

        for limite in PRAZOS_CRITICOS_HORAS:
            if horas_restantes <= limite:
                if horas_restantes <= 24:
                    urgencia = Urgencia.CRITICA
                elif horas_restantes <= 48:
                    urgencia = Urgencia.ALTA
                else:
                    urgencia = Urgencia.MEDIA

                horas_int = int(horas_restantes)
                return AlertaGerado(
                    tipo=TipoAlerta.PRAZO_CRITICO,
                    urgencia=urgencia,
                    titulo=f"Abertura em {horas_int}h: {lic.numero}",
                    mensagem=(
                        f"A licitação {lic.numero} ({lic.orgao_nome}) "
                        f"abre em {horas_int}h — "
                        f"{lic.data_abertura.strftime('%d/%m/%Y %H:%M')}"
                    ),
                    detalhes={
                        "licitacao_numero": lic.numero,
                        "data_abertura": lic.data_abertura.isoformat(),
                        "horas_restantes": horas_int,
                    },
                    canais=[CanalNotificacao.WHATSAPP, CanalNotificacao.PUSH],
                    alerta_id=filtro.id,
                    licitacao_id=lic.id,
                    usuario_id=filtro.usuario_id,
                    prioridade=PESOS_URGENCIA[urgencia],
                )

        return None

    def _verificar_mudanca_status(
        self,
        filtro: FiltroAlerta,
        lic: LicitacaoResumida,
    ) -> AlertaGerado | None:
        """Verifica se o status mudou para um estado alertável."""
        if not lic.status_anterior:
            return None

        if lic.status.lower() == lic.status_anterior.lower():
            return None

        status_lower = lic.status.lower()
        if status_lower not in STATUS_ALERTAVEIS:
            return None

        urgencia = Urgencia.ALTA if status_lower in ("revogada", "anulada") else Urgencia.MEDIA

        return AlertaGerado(
            tipo=TipoAlerta.MUDANCA_STATUS,
            urgencia=urgencia,
            titulo=f"Status alterado: {lic.numero} → {lic.status.upper()}",
            mensagem=(
                f"A licitação {lic.numero} ({lic.orgao_nome}) "
                f"mudou de {lic.status_anterior} para {lic.status}"
            ),
            detalhes={
                "licitacao_numero": lic.numero,
                "status_anterior": lic.status_anterior,
                "status_novo": lic.status,
            },
            canais=[CanalNotificacao.EMAIL],
            alerta_id=filtro.id,
            licitacao_id=lic.id,
            usuario_id=filtro.usuario_id,
            prioridade=PESOS_URGENCIA[urgencia],
        )

    # ------------------------------------------------------------------
    # Anti-spam
    # ------------------------------------------------------------------

    def _aplicar_antispam(
        self,
        alertas: list[AlertaGerado],
        agora: datetime,
    ) -> list[AlertaGerado]:
        """Aplica regras anti-spam à lista de alertas."""
        resultado: list[AlertaGerado] = []

        for alerta in alertas:
            # Quiet hours
            if self._em_quiet_hours(agora) and alerta.urgencia != Urgencia.CRITICA:
                logger.debug("Alerta adiado por quiet hours: %s", alerta.titulo)
                continue

            # Rate limit por usuário+tipo
            chave = f"{alerta.usuario_id}:{alerta.tipo.value}"
            if self._excede_rate_limit(chave, agora):
                logger.debug("Alerta bloqueado por rate limit: %s", alerta.titulo)
                continue

            # Dedup: mesmo tipo + mesma licitação + mesmo usuário
            if self._ja_existe(resultado, alerta):
                continue

            self._registrar_envio(chave, agora)
            resultado.append(alerta)

        # Consolidação de digest
        if self.config.consolidar_digest:
            resultado = self._consolidar_digest(resultado)

        return resultado

    def _em_quiet_hours(self, agora: datetime) -> bool:
        """Verifica se estamos em horário de silêncio."""
        hora = agora.hour
        inicio = self.config.quiet_hour_inicio
        fim = self.config.quiet_hour_fim

        if inicio > fim:
            # Ex: 22h-7h (cruza meia-noite)
            return hora >= inicio or hora < fim
        else:
            return inicio <= hora < fim

    def _excede_rate_limit(self, chave: str, agora: datetime) -> bool:
        """Verifica se o rate limit foi excedido para esta chave."""
        envios = self._envios_recentes.get(chave, [])
        # Limpa envios antigos (>24h)
        envios = [e for e in envios if (agora - e).total_seconds() < 86400]
        self._envios_recentes[chave] = envios

        # Cooldown
        if envios:
            ultimo = max(envios)
            if (agora - ultimo).total_seconds() < self.config.cooldown_minutos * 60:
                return True

        # Limite por hora
        ultima_hora = [e for e in envios if (agora - e).total_seconds() < 3600]
        if len(ultima_hora) >= self.config.max_por_hora:
            return True

        # Limite por dia
        if len(envios) >= self.config.max_por_dia:
            return True

        return False

    def _registrar_envio(self, chave: str, agora: datetime) -> None:
        """Registra um envio para controle de rate limit."""
        self._envios_recentes.setdefault(chave, []).append(agora)

    @staticmethod
    def _ja_existe(alertas: list[AlertaGerado], novo: AlertaGerado) -> bool:
        """Verifica se já existe alerta igual (dedup)."""
        return any(
            a.tipo == novo.tipo
            and a.licitacao_id == novo.licitacao_id
            and a.usuario_id == novo.usuario_id
            for a in alertas
        )

    def _consolidar_digest(self, alertas: list[AlertaGerado]) -> list[AlertaGerado]:
        """Consolida alertas do mesmo tipo+usuário em digest.

        Só consolida se houver 3+ alertas do mesmo tipo para o mesmo usuário.
        Alertas CRITICOS nunca são consolidados.
        """
        if len(alertas) < 3:
            return alertas

        # Separa críticos (nunca consolidam)
        criticos = [a for a in alertas if a.urgencia == Urgencia.CRITICA]
        outros = [a for a in alertas if a.urgencia != Urgencia.CRITICA]

        # Agrupa por (usuario_id, tipo)
        grupos: dict[str, list[AlertaGerado]] = {}
        for a in outros:
            chave = f"{a.usuario_id}:{a.tipo.value}"
            grupos.setdefault(chave, []).append(a)

        resultado = list(criticos)

        for chave, grupo in grupos.items():
            if len(grupo) < 3:
                resultado.extend(grupo)
            else:
                # Consolida em digest
                digest = AlertaGerado(
                    tipo=grupo[0].tipo,
                    urgencia=max(grupo, key=lambda a: PESOS_URGENCIA[a.urgencia]).urgencia,
                    titulo=f"Digest: {len(grupo)} alertas de {grupo[0].tipo.value}",
                    mensagem="\n".join(f"• {a.titulo}" for a in grupo[:10]),
                    detalhes={
                        "total_alertas": len(grupo),
                        "alertas": [
                            {"titulo": a.titulo, "licitacao_id": a.licitacao_id}
                            for a in grupo[:20]
                        ],
                    },
                    canais=grupo[0].canais,
                    usuario_id=grupo[0].usuario_id,
                    prioridade=max(a.prioridade for a in grupo),
                )
                resultado.append(digest)

        return resultado

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    @staticmethod
    def _urgencia_compliance(dias_restantes: int) -> Urgencia:
        """Determina urgência baseado nos dias restantes."""
        if dias_restantes <= 3:
            return Urgencia.CRITICA
        if dias_restantes <= 7:
            return Urgencia.ALTA
        if dias_restantes <= 15:
            return Urgencia.MEDIA
        return Urgencia.BAIXA
