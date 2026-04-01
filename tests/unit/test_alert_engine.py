"""Testes para o AlertEngine."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from licitabrasil.alerts.engine import (
    AlertEngine,
    CanalNotificacao,
    ConfigAntiSpam,
    DocumentoCompliance,
    FiltroAlerta,
    LicitacaoResumida,
    TipoAlerta,
    Urgencia,
)

# Horário comercial fixo — evita quiet hours (22h-7h) nos testes
AGORA_COMERCIAL = datetime(2025, 6, 1, 10, 0, 0)


@pytest.fixture
def engine():
    return AlertEngine()


@pytest.fixture
def filtro_basico():
    return FiltroAlerta(
        id=1,
        usuario_id=100,
        palavras_chave=["limpeza", "conservação"],
        estados=["PE"],
        canais=[CanalNotificacao.EMAIL],
    )


@pytest.fixture
def filtro_amplo():
    """Filtro sem restrições — casa com tudo."""
    return FiltroAlerta(id=2, usuario_id=200)


@pytest.fixture
def licitacao():
    return LicitacaoResumida(
        id=42,
        numero="PE-001/2025",
        objeto="Contratação de serviços de limpeza e conservação predial",
        modalidade="pregao_eletronico",
        status="publicada",
        valor_estimado=Decimal("500000"),
        data_abertura=AGORA_COMERCIAL + timedelta(hours=20),
        uf="PE",
        municipio="Recife",
        orgao_nome="Prefeitura do Recife",
        match_score=0.8,
    )


# ---------------------------------------------------------------------------
# Match de filtros
# ---------------------------------------------------------------------------

class TestMatchFiltro:
    """Testes para matching entre filtro e licitação."""

    def test_match_por_palavras_chave(self, engine, filtro_basico, licitacao):
        assert engine._match_filtro(filtro_basico, licitacao) is True

    def test_nao_match_palavras_chave(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, palavras_chave=["informática"])
        licitacao.match_score = None
        assert engine._match_filtro(filtro, licitacao) is False

    def test_match_por_score(self, engine, licitacao):
        """Match score >= threshold (0.5) sempre casa, independente dos filtros."""
        filtro = FiltroAlerta(id=1, usuario_id=100, palavras_chave=["xyz_inexistente"])
        licitacao.match_score = 0.8
        assert engine._match_filtro(filtro, licitacao) is True

    def test_match_score_abaixo_threshold(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, palavras_chave=["xyz_inexistente"])
        licitacao.match_score = 0.3
        assert engine._match_filtro(filtro, licitacao) is False

    def test_match_por_estado(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, estados=["PE"])
        licitacao.match_score = None
        assert engine._match_filtro(filtro, licitacao) is True

    def test_nao_match_estado(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, estados=["SP"])
        licitacao.match_score = None
        assert engine._match_filtro(filtro, licitacao) is False

    def test_match_por_modalidade(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, modalidades=["pregao_eletronico"])
        licitacao.match_score = None
        assert engine._match_filtro(filtro, licitacao) is True

    def test_nao_match_modalidade(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, modalidades=["concorrencia"])
        licitacao.match_score = None
        assert engine._match_filtro(filtro, licitacao) is False

    def test_match_por_valor_na_faixa(self, engine, licitacao):
        filtro = FiltroAlerta(
            id=1, usuario_id=100,
            valor_minimo=Decimal("100000"),
            valor_maximo=Decimal("1000000"),
        )
        licitacao.match_score = None
        assert engine._match_filtro(filtro, licitacao) is True

    def test_nao_match_valor_abaixo_minimo(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, valor_minimo=Decimal("1000000"))
        licitacao.match_score = None
        assert engine._match_filtro(filtro, licitacao) is False

    def test_nao_match_valor_acima_maximo(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, valor_maximo=Decimal("100000"))
        licitacao.match_score = None
        assert engine._match_filtro(filtro, licitacao) is False

    def test_match_por_segmento(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, segmentos=["limpeza"])
        licitacao.match_score = None
        licitacao.segmentos = ["limpeza", "manutenção"]
        assert engine._match_filtro(filtro, licitacao) is True

    def test_nao_match_segmento(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, segmentos=["tecnologia"])
        licitacao.match_score = None
        licitacao.segmentos = ["limpeza"]
        assert engine._match_filtro(filtro, licitacao) is False

    def test_filtro_vazio_casa_tudo(self, engine, filtro_amplo, licitacao):
        licitacao.match_score = None
        assert engine._match_filtro(filtro_amplo, licitacao) is True

    def test_match_case_insensitive(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, estados=["pe"], palavras_chave=["LIMPEZA"])
        licitacao.match_score = None
        assert engine._match_filtro(filtro, licitacao) is True


# ---------------------------------------------------------------------------
# Nova oportunidade
# ---------------------------------------------------------------------------

class TestNovaOportunidade:
    """Testes para alertas de nova oportunidade."""

    def test_gera_alerta(self, engine, filtro_basico, licitacao):
        alertas = engine.avaliar([filtro_basico], [licitacao], agora=AGORA_COMERCIAL)
        oportunidades = [a for a in alertas if a.tipo == TipoAlerta.NOVA_OPORTUNIDADE]
        assert len(oportunidades) >= 1

    def test_alerta_contem_dados(self, engine, filtro_basico, licitacao):
        alertas = engine.avaliar([filtro_basico], [licitacao], agora=AGORA_COMERCIAL)
        oport = next(a for a in alertas if a.tipo == TipoAlerta.NOVA_OPORTUNIDADE)
        assert oport.licitacao_id == 42
        assert oport.usuario_id == 100
        assert oport.alerta_id == 1
        assert "limpeza" in oport.mensagem.lower() or "PE-001" in oport.titulo

    def test_urgencia_alta_com_score_alto(self, engine, filtro_basico, licitacao):
        licitacao.match_score = 0.85
        alertas = engine.avaliar([filtro_basico], [licitacao], agora=AGORA_COMERCIAL)
        oport = next(a for a in alertas if a.tipo == TipoAlerta.NOVA_OPORTUNIDADE)
        assert oport.urgencia == Urgencia.ALTA

    def test_urgencia_media_com_score_medio(self, engine, filtro_basico, licitacao):
        licitacao.match_score = 0.55
        alertas = engine.avaliar([filtro_basico], [licitacao], agora=AGORA_COMERCIAL)
        oport = next(a for a in alertas if a.tipo == TipoAlerta.NOVA_OPORTUNIDADE)
        assert oport.urgencia == Urgencia.MEDIA

    def test_sem_match_sem_alerta(self, engine, licitacao):
        filtro = FiltroAlerta(id=1, usuario_id=100, palavras_chave=["xyz_impossivel"])
        licitacao.match_score = None
        alertas = engine.avaliar([filtro], [licitacao])
        oportunidades = [a for a in alertas if a.tipo == TipoAlerta.NOVA_OPORTUNIDADE]
        assert len(oportunidades) == 0


# ---------------------------------------------------------------------------
# Prazo crítico
# ---------------------------------------------------------------------------

class TestPrazoCritico:
    """Testes para alertas de prazo crítico."""

    def test_abertura_em_menos_de_24h(self, engine, filtro_basico):
        lic = LicitacaoResumida(
            id=1, numero="PE-002/2025", objeto="Teste",
            data_abertura=datetime.now() + timedelta(hours=12),
            match_score=None,
        )
        agora = datetime.now()
        alertas = engine.avaliar([filtro_basico], [lic], agora=agora)
        prazos = [a for a in alertas if a.tipo == TipoAlerta.PRAZO_CRITICO]
        assert len(prazos) >= 1
        assert prazos[0].urgencia == Urgencia.CRITICA

    def test_abertura_em_36h(self, engine, filtro_basico):
        lic = LicitacaoResumida(
            id=1, numero="PE-003/2025", objeto="Teste",
            data_abertura=AGORA_COMERCIAL + timedelta(hours=36),
            match_score=None,
        )
        alertas = engine.avaliar([filtro_basico], [lic], agora=AGORA_COMERCIAL)
        prazos = [a for a in alertas if a.tipo == TipoAlerta.PRAZO_CRITICO]
        assert len(prazos) >= 1
        assert prazos[0].urgencia == Urgencia.ALTA

    def test_abertura_em_60h(self, engine, filtro_basico):
        lic = LicitacaoResumida(
            id=1, numero="PE-004/2025", objeto="Teste",
            data_abertura=AGORA_COMERCIAL + timedelta(hours=60),
            match_score=None,
        )
        alertas = engine.avaliar([filtro_basico], [lic], agora=AGORA_COMERCIAL)
        prazos = [a for a in alertas if a.tipo == TipoAlerta.PRAZO_CRITICO]
        assert len(prazos) >= 1
        assert prazos[0].urgencia == Urgencia.MEDIA

    def test_sem_prazo_critico_longe(self, engine, filtro_basico):
        lic = LicitacaoResumida(
            id=1, numero="PE-005/2025", objeto="Teste",
            data_abertura=datetime.now() + timedelta(days=10),
            match_score=None,
        )
        alertas = engine.avaliar([filtro_basico], [lic])
        prazos = [a for a in alertas if a.tipo == TipoAlerta.PRAZO_CRITICO]
        assert len(prazos) == 0

    def test_sem_prazo_critico_passado(self, engine, filtro_basico):
        lic = LicitacaoResumida(
            id=1, numero="PE-006/2025", objeto="Teste",
            data_abertura=datetime.now() - timedelta(hours=5),
            match_score=None,
        )
        alertas = engine.avaliar([filtro_basico], [lic])
        prazos = [a for a in alertas if a.tipo == TipoAlerta.PRAZO_CRITICO]
        assert len(prazos) == 0

    def test_sem_data_abertura(self, engine, filtro_basico):
        lic = LicitacaoResumida(id=1, numero="PE-007/2025", objeto="Teste", match_score=None)
        alertas = engine.avaliar([filtro_basico], [lic])
        prazos = [a for a in alertas if a.tipo == TipoAlerta.PRAZO_CRITICO]
        assert len(prazos) == 0

    def test_prazo_canais_whatsapp_push(self, engine, filtro_basico):
        lic = LicitacaoResumida(
            id=1, numero="PE-008/2025", objeto="Teste",
            data_abertura=datetime.now() + timedelta(hours=10),
            match_score=None,
        )
        alertas = engine.avaliar([filtro_basico], [lic])
        prazo = next(a for a in alertas if a.tipo == TipoAlerta.PRAZO_CRITICO)
        assert CanalNotificacao.WHATSAPP in prazo.canais
        assert CanalNotificacao.PUSH in prazo.canais


# ---------------------------------------------------------------------------
# Mudança de status
# ---------------------------------------------------------------------------

class TestMudancaStatus:
    """Testes para alertas de mudança de status."""

    def test_licitacao_revogada(self, engine, filtro_amplo):
        lic = LicitacaoResumida(
            id=1, numero="PE-010/2025", objeto="Teste",
            status="revogada", status_anterior="aberta",
            match_score=None,
        )
        alertas = engine.avaliar([filtro_amplo], [lic], agora=AGORA_COMERCIAL)
        status_alerts = [a for a in alertas if a.tipo == TipoAlerta.MUDANCA_STATUS]
        assert len(status_alerts) >= 1
        assert status_alerts[0].urgencia == Urgencia.ALTA
        assert "revogada" in status_alerts[0].mensagem.lower()

    def test_licitacao_suspensa(self, engine, filtro_amplo):
        lic = LicitacaoResumida(
            id=1, numero="PE-011/2025", objeto="Teste",
            status="suspensa", status_anterior="aberta",
            match_score=None,
        )
        alertas = engine.avaliar([filtro_amplo], [lic], agora=AGORA_COMERCIAL)
        status_alerts = [a for a in alertas if a.tipo == TipoAlerta.MUDANCA_STATUS]
        assert len(status_alerts) >= 1
        assert status_alerts[0].urgencia == Urgencia.MEDIA

    def test_sem_mudanca_status(self, engine, filtro_amplo):
        lic = LicitacaoResumida(
            id=1, numero="PE-012/2025", objeto="Teste",
            status="aberta", status_anterior="aberta",
            match_score=None,
        )
        alertas = engine.avaliar([filtro_amplo], [lic])
        status_alerts = [a for a in alertas if a.tipo == TipoAlerta.MUDANCA_STATUS]
        assert len(status_alerts) == 0

    def test_status_nao_alertavel(self, engine, filtro_amplo):
        lic = LicitacaoResumida(
            id=1, numero="PE-013/2025", objeto="Teste",
            status="homologada", status_anterior="aberta",
            match_score=None,
        )
        alertas = engine.avaliar([filtro_amplo], [lic])
        status_alerts = [a for a in alertas if a.tipo == TipoAlerta.MUDANCA_STATUS]
        assert len(status_alerts) == 0

    def test_sem_status_anterior(self, engine, filtro_amplo):
        lic = LicitacaoResumida(
            id=1, numero="PE-014/2025", objeto="Teste",
            status="suspensa",
            match_score=None,
        )
        alertas = engine.avaliar([filtro_amplo], [lic])
        status_alerts = [a for a in alertas if a.tipo == TipoAlerta.MUDANCA_STATUS]
        assert len(status_alerts) == 0

    def test_anulada_urgencia_alta(self, engine, filtro_amplo):
        lic = LicitacaoResumida(
            id=1, numero="PE-015/2025", objeto="Teste",
            status="anulada", status_anterior="em_andamento",
            match_score=None,
        )
        alertas = engine.avaliar([filtro_amplo], [lic], agora=AGORA_COMERCIAL)
        status_alerts = [a for a in alertas if a.tipo == TipoAlerta.MUDANCA_STATUS]
        assert status_alerts[0].urgencia == Urgencia.ALTA


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

class TestCompliance:
    """Testes para alertas de compliance (documentos vencendo)."""

    def test_documento_vencido(self, engine):
        docs = [DocumentoCompliance(
            nome="CND Federal",
            data_validade=datetime.now() - timedelta(days=5),
            empresa_cnpj="12345678000190",
        )]
        alertas = engine.verificar_compliance(docs)
        assert len(alertas) == 1
        assert alertas[0].urgencia == Urgencia.CRITICA
        assert "VENCIDO" in alertas[0].titulo

    def test_documento_vence_em_3_dias(self, engine):
        docs = [DocumentoCompliance(
            nome="FGTS",
            data_validade=datetime.now() + timedelta(days=3),
            empresa_cnpj="12345678000190",
        )]
        alertas = engine.verificar_compliance(docs)
        assert len(alertas) == 1
        assert alertas[0].urgencia == Urgencia.CRITICA

    def test_documento_vence_em_7_dias(self, engine):
        docs = [DocumentoCompliance(
            nome="INSS",
            data_validade=datetime.now() + timedelta(days=7),
            empresa_cnpj="12345678000190",
        )]
        alertas = engine.verificar_compliance(docs)
        assert len(alertas) == 1
        assert alertas[0].urgencia == Urgencia.ALTA

    def test_documento_vence_em_15_dias(self, engine):
        docs = [DocumentoCompliance(
            nome="Certidão Municipal",
            data_validade=datetime.now() + timedelta(days=15),
            empresa_cnpj="12345678000190",
        )]
        alertas = engine.verificar_compliance(docs)
        assert len(alertas) == 1
        assert alertas[0].urgencia == Urgencia.MEDIA

    def test_documento_vence_em_30_dias(self, engine):
        docs = [DocumentoCompliance(
            nome="Certidão Estadual",
            data_validade=datetime.now() + timedelta(days=30),
            empresa_cnpj="12345678000190",
        )]
        alertas = engine.verificar_compliance(docs)
        assert len(alertas) == 1
        assert alertas[0].urgencia == Urgencia.BAIXA

    def test_documento_longe_sem_alerta(self, engine):
        docs = [DocumentoCompliance(
            nome="Certidão",
            data_validade=datetime.now() + timedelta(days=90),
            empresa_cnpj="12345678000190",
        )]
        alertas = engine.verificar_compliance(docs)
        assert len(alertas) == 0

    def test_multiplos_documentos(self, engine):
        docs = [
            DocumentoCompliance(nome="CND Federal", data_validade=datetime.now() - timedelta(days=1), empresa_cnpj="11111111000111"),
            DocumentoCompliance(nome="FGTS", data_validade=datetime.now() + timedelta(days=5), empresa_cnpj="11111111000111"),
            DocumentoCompliance(nome="INSS", data_validade=datetime.now() + timedelta(days=60), empresa_cnpj="11111111000111"),
        ]
        alertas = engine.verificar_compliance(docs)
        assert len(alertas) == 2  # Vencido + 5 dias (60 dias = sem alerta)

    def test_compliance_ordenado_por_prioridade(self, engine):
        docs = [
            DocumentoCompliance(nome="A", data_validade=datetime.now() + timedelta(days=15), empresa_cnpj="111"),
            DocumentoCompliance(nome="B", data_validade=datetime.now() - timedelta(days=1), empresa_cnpj="111"),
        ]
        alertas = engine.verificar_compliance(docs)
        assert alertas[0].urgencia == Urgencia.CRITICA  # Vencido vem primeiro


# ---------------------------------------------------------------------------
# Inteligência de mercado
# ---------------------------------------------------------------------------

class TestInteligenciaMercado:
    """Testes para alertas de inteligência de mercado."""

    def test_volume_alto(self, engine):
        alerta = engine.avaliar_inteligencia_mercado("Prefeitura do Recife", 20, 10.0)
        assert alerta is not None
        assert "alto" in alerta.titulo.lower()
        assert alerta.detalhes["variacao_pct"] > 0

    def test_volume_baixo(self, engine):
        alerta = engine.avaliar_inteligencia_mercado("CBTU", 3, 10.0)
        assert alerta is not None
        assert "baixo" in alerta.titulo.lower()
        assert alerta.detalhes["variacao_pct"] < 0

    def test_volume_normal_sem_alerta(self, engine):
        alerta = engine.avaliar_inteligencia_mercado("TRE-PE", 11, 10.0)
        assert alerta is None  # 10% variação < 20% threshold

    def test_media_zero_sem_alerta(self, engine):
        alerta = engine.avaliar_inteligencia_mercado("Orgao Novo", 5, 0.0)
        assert alerta is None


# ---------------------------------------------------------------------------
# Anti-spam
# ---------------------------------------------------------------------------

class TestAntiSpam:
    """Testes para regras anti-spam."""

    def test_quiet_hours_bloqueia(self):
        config = ConfigAntiSpam(quiet_hour_inicio=22, quiet_hour_fim=7)
        engine = AlertEngine(config=config)
        filtro = FiltroAlerta(id=1, usuario_id=100)
        lic = LicitacaoResumida(
            id=1, objeto="Teste", status="suspensa", status_anterior="aberta",
            match_score=None,
        )
        # 23h = quiet hours
        agora = datetime(2025, 6, 1, 23, 0, 0)
        alertas = engine.avaliar([filtro], [lic], agora=agora)
        # Alertas não-críticos devem ser bloqueados (quiet hours filtra MEDIA)
        status_alerts = [a for a in alertas if a.tipo == TipoAlerta.MUDANCA_STATUS]
        assert len(status_alerts) == 0

    def test_quiet_hours_permite_critico(self):
        config = ConfigAntiSpam(quiet_hour_inicio=22, quiet_hour_fim=7)
        engine = AlertEngine(config=config)
        filtro = FiltroAlerta(id=1, usuario_id=100)
        lic = LicitacaoResumida(
            id=1, objeto="Teste",
            data_abertura=datetime(2025, 6, 2, 5, 0, 0),  # Abre em poucas horas
            match_score=None,
        )
        agora = datetime(2025, 6, 2, 0, 0, 0)  # Meia-noite = quiet hours
        alertas = engine.avaliar([filtro], [lic], agora=agora)
        prazos = [a for a in alertas if a.tipo == TipoAlerta.PRAZO_CRITICO]
        # Prazo crítico (5h) = urgência CRITICA → passa quiet hours
        assert len(prazos) == 1

    def test_rate_limit_cooldown(self):
        config = ConfigAntiSpam(cooldown_minutos=60)
        engine = AlertEngine(config=config)
        filtro = FiltroAlerta(id=1, usuario_id=100)

        lic1 = LicitacaoResumida(id=1, objeto="Teste A", status="revogada", status_anterior="aberta", match_score=None)
        lic2 = LicitacaoResumida(id=2, objeto="Teste B", status="suspensa", status_anterior="aberta", match_score=None)

        agora = datetime(2025, 6, 1, 10, 0, 0)
        # Primeiro batch — deve gerar alertas
        alertas1 = engine.avaliar([filtro], [lic1], agora=agora)
        assert len(alertas1) > 0

        # Segundo batch 5 min depois — rate limited
        agora2 = agora + timedelta(minutes=5)
        alertas2 = engine.avaliar([filtro], [lic2], agora=agora2)
        status_2 = [a for a in alertas2 if a.tipo == TipoAlerta.MUDANCA_STATUS]
        assert len(status_2) == 0  # Bloqueado pelo cooldown

    def test_dedup_mesmo_tipo_licitacao_usuario(self, engine, filtro_basico, licitacao):
        """Não gera alertas duplicados do mesmo tipo para mesma licitação."""
        # Dois filtros do mesmo usuário
        filtro2 = FiltroAlerta(id=2, usuario_id=100, palavras_chave=["conservação"])
        alertas = engine.avaliar([filtro_basico, filtro2], [licitacao])
        oportunidades = [a for a in alertas if a.tipo == TipoAlerta.NOVA_OPORTUNIDADE]
        # Deve ter no máximo 1 (dedup)
        assert len(oportunidades) <= 1

    def test_digest_consolida_muitos_alertas(self):
        config = ConfigAntiSpam(consolidar_digest=True, cooldown_minutos=0)
        engine = AlertEngine(config=config)
        filtro = FiltroAlerta(id=1, usuario_id=100)

        # 5 licitações com match → 5 alertas de nova_oportunidade
        lics = [
            LicitacaoResumida(id=i, objeto=f"Teste {i}", match_score=0.8)
            for i in range(5)
        ]
        alertas = engine.avaliar([filtro], lics, agora=AGORA_COMERCIAL)
        # Deve consolidar em 1 digest (≥3 do mesmo tipo)
        assert any("Digest" in a.titulo for a in alertas)

    def test_horario_comercial_permite(self):
        config = ConfigAntiSpam(quiet_hour_inicio=22, quiet_hour_fim=7)
        engine = AlertEngine(config=config)
        assert engine._em_quiet_hours(datetime(2025, 6, 1, 14, 0)) is False

    def test_meia_noite_quiet(self):
        config = ConfigAntiSpam(quiet_hour_inicio=22, quiet_hour_fim=7)
        engine = AlertEngine(config=config)
        assert engine._em_quiet_hours(datetime(2025, 6, 1, 0, 0)) is True

    def test_6h_quiet(self):
        config = ConfigAntiSpam(quiet_hour_inicio=22, quiet_hour_fim=7)
        engine = AlertEngine(config=config)
        assert engine._em_quiet_hours(datetime(2025, 6, 1, 6, 30)) is True

    def test_7h_nao_quiet(self):
        config = ConfigAntiSpam(quiet_hour_inicio=22, quiet_hour_fim=7)
        engine = AlertEngine(config=config)
        assert engine._em_quiet_hours(datetime(2025, 6, 1, 7, 0)) is False


# ---------------------------------------------------------------------------
# Priorização
# ---------------------------------------------------------------------------

class TestPriorizacao:
    """Testes para ordenação por prioridade."""

    def test_ordenacao_por_prioridade(self, engine, filtro_amplo):
        lics = [
            LicitacaoResumida(
                id=1, objeto="Baixa prioridade",
                status="suspensa", status_anterior="aberta",
                match_score=None,
            ),
            LicitacaoResumida(
                id=2, objeto="Alta prioridade",
                data_abertura=datetime.now() + timedelta(hours=5),
                match_score=0.9,
            ),
        ]
        agora = datetime(2025, 6, 1, 10, 0, 0)
        alertas = engine.avaliar([filtro_amplo], lics, agora=agora)
        if len(alertas) >= 2:
            assert alertas[0].prioridade >= alertas[1].prioridade


# ---------------------------------------------------------------------------
# Exceptions custom (scrapers/core.py)
# ---------------------------------------------------------------------------

class TestExceptions:
    """Testes para a hierarquia de exceptions."""

    def test_portal_indisponivel(self):
        from licitabrasil.scrapers.core import PortalIndisponivelError, LicitaBrasilError
        exc = PortalIndisponivelError("PNCP", status_code=503)
        assert isinstance(exc, LicitaBrasilError)
        assert "PNCP" in str(exc)
        assert "503" in str(exc)
        assert exc.portal == "PNCP"

    def test_rate_limit(self):
        from licitabrasil.scrapers.core import RateLimitError, LicitaBrasilError
        exc = RateLimitError("ComprasNet", retry_after=60)
        assert isinstance(exc, LicitaBrasilError)
        assert exc.retry_after == 60
        assert "60s" in str(exc)

    def test_parse_error(self):
        from licitabrasil.scrapers.core import ParseError, LicitaBrasilError
        exc = ParseError("PE Integrado", message="HTML inesperado")
        assert isinstance(exc, LicitaBrasilError)
        assert "HTML inesperado" in str(exc)

    def test_dados_invalidos(self):
        from licitabrasil.scrapers.core import DadosInvalidosError, LicitaBrasilError
        exc = DadosInvalidosError("PNCP", errors=[{"field": "cnpj"}])
        assert isinstance(exc, LicitaBrasilError)
        assert exc.errors == [{"field": "cnpj"}]
        assert "1 erro" in str(exc)

    def test_heranca_base(self):
        from licitabrasil.scrapers.core import (
            LicitaBrasilError, PortalIndisponivelError, RateLimitError,
            ParseError, DadosInvalidosError,
        )
        for cls in [PortalIndisponivelError, RateLimitError, ParseError, DadosInvalidosError]:
            assert issubclass(cls, LicitaBrasilError)
            assert issubclass(cls, Exception)


# ---------------------------------------------------------------------------
# Integração
# ---------------------------------------------------------------------------

class TestIntegracao:
    """Teste de cenário completo."""

    def test_cenario_completo(self):
        """Simula pipeline: nova licitação → avaliação → alertas."""
        config = ConfigAntiSpam(cooldown_minutos=0)  # Sem cooldown para teste
        engine = AlertEngine(config=config)

        # Empresa de limpeza em PE
        filtro = FiltroAlerta(
            id=1,
            usuario_id=100,
            palavras_chave=["limpeza", "conservação"],
            estados=["PE"],
            valor_minimo=Decimal("100000"),
            valor_maximo=Decimal("2000000"),
            canais=[CanalNotificacao.EMAIL, CanalNotificacao.WHATSAPP],
        )

        # Licitação que casa perfeitamente
        lic = LicitacaoResumida(
            id=42,
            numero="PE-001/2025",
            objeto="Contratação de serviços de limpeza predial",
            modalidade="pregao_eletronico",
            status="publicada",
            valor_estimado=Decimal("500000"),
            data_abertura=datetime.now() + timedelta(hours=20),
            uf="PE",
            municipio="Recife",
            orgao_nome="Prefeitura do Recife",
            match_score=0.85,
        )

        agora = datetime.now().replace(hour=10)  # Horário comercial
        alertas = engine.avaliar([filtro], [lic], agora=agora)

        assert len(alertas) >= 1
        tipos = {a.tipo for a in alertas}
        assert TipoAlerta.NOVA_OPORTUNIDADE in tipos

        # Compliance
        docs = [DocumentoCompliance(
            nome="CND Federal",
            data_validade=datetime.now() + timedelta(days=5),
            empresa_cnpj="12345678000190",
        )]
        compliance = engine.verificar_compliance(docs)
        assert len(compliance) == 1
        assert compliance[0].tipo == TipoAlerta.COMPLIANCE
