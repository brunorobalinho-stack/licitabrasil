"""Testes da logica de filtragem do purge_encerradas.

Valida classify_status() e should_purge() sem tocar no banco de dados.

Uso:
    python -m app.scripts.test_purge
    python -m pytest app/scripts/test_purge.py -v
"""

from datetime import datetime, timedelta

from app.scripts.purge_encerradas import classify_status, should_purge

NOW = datetime(2026, 3, 5, 12, 0, 0)
OLD_DATE = NOW - timedelta(days=120)
RECENT_DATE = NOW - timedelta(days=10)
BORDERLINE_DATE = NOW - timedelta(days=30)
SUSPEND_OLD = NOW - timedelta(days=100)
SUSPEND_RECENT = NOW - timedelta(days=60)


# ── classify_status ───────────────────────────────────


def test_classify_purge_statuses():
    """Todos os status de encerramento devem retornar 'purge'."""
    purge_cases = [
        "Encerrada", "encerrado", "ENCERRADA",
        "Homologacao", "homologada", "Adjudicacao/Homologacao",
        "Adjudicacao", "adjudicada",
        "Deserta", "deserto",
        "Fracassada", "Fracassado",
        "Revogada", "Revogacao",
        "Anulada", "Anulacao",
        "Cancelada", "cancelado",
        "Finalizada", "finalizado",
        "Concluida", "concluido",
        "Excluida",
    ]
    for status in purge_cases:
        result = classify_status(status)
        assert result == "purge", f"'{status}' deveria ser 'purge', got '{result}'"


def test_classify_suspend_statuses():
    """Status suspensa/suspenso devem retornar 'suspend'."""
    for status in ["Suspensa", "suspenso", "SUSPENSA"]:
        result = classify_status(status)
        assert result == "suspend", f"'{status}' deveria ser 'suspend', got '{result}'"


def test_classify_keep_statuses():
    """Status ativos e desconhecidos devem retornar 'keep'."""
    keep_cases = [
        "Aberta", "aberto",
        "Em andamento",
        "Publicada", "publicada", "Publicacao",
        "Agendada", "agendado",
        "Divulgada no PNCP",
        "Em realizacao",
        "Recebendo propostas",
        "Esperando realizacao",
        "em_julgamento",
        "com_recurso",
        "desconhecido",
        "Habilitacao",
        "Impugnacao/Edital",
        "Publicacao Ata Registro Precos(ARP)",
    ]
    for status in keep_cases:
        result = classify_status(status)
        assert result == "keep", f"'{status}' deveria ser 'keep', got '{result}'"


def test_classify_null_and_empty():
    """None e string vazia devem retornar 'keep' (seguranca)."""
    assert classify_status(None) == "keep"
    assert classify_status("") == "keep"


# ── should_purge ──────────────────────────────────────


def test_purge_encerrada_old():
    """Licitacao encerrada com publicacao antiga -> purga."""
    assert should_purge("Encerrada", OLD_DATE, None, now=NOW) is True


def test_purge_encerrada_no_pubdate():
    """Licitacao encerrada sem data_publicacao -> purga (sem protecao)."""
    assert should_purge("Fracassada", None, None, now=NOW) is True


def test_keep_encerrada_recent():
    """Licitacao encerrada com publicacao recente -> mantida (protecao temporal)."""
    assert should_purge("Encerrada", RECENT_DATE, None, now=NOW) is False


def test_keep_encerrada_borderline():
    """Publicacao exatamente no limite (29 dias) -> mantida."""
    assert should_purge("Encerrada", BORDERLINE_DATE, None, dias_protecao=30, now=NOW) is False


def test_purge_encerrada_past_borderline():
    """Publicacao 1 dia alem do limite (31 dias) -> purga."""
    past = NOW - timedelta(days=31)
    assert should_purge("Encerrada", past, None, dias_protecao=30, now=NOW) is True


def test_keep_status_ativo():
    """Status ativo nunca purga, independente de datas."""
    assert should_purge("Aberta", OLD_DATE, OLD_DATE, now=NOW) is False
    assert should_purge("Em andamento", None, None, now=NOW) is False
    assert should_purge("Publicada", OLD_DATE, None, now=NOW) is False


def test_keep_null_status():
    """Status NULL nunca purga."""
    assert should_purge(None, OLD_DATE, OLD_DATE, now=NOW) is False


def test_suspensa_old_abertura():
    """Suspensa com data_abertura > 90 dias atras -> purga."""
    assert should_purge("Suspensa", OLD_DATE, SUSPEND_OLD, now=NOW) is True


def test_suspensa_recent_abertura():
    """Suspensa com data_abertura < 90 dias atras -> mantida."""
    assert should_purge("Suspensa", OLD_DATE, SUSPEND_RECENT, now=NOW) is False


def test_suspensa_no_abertura():
    """Suspensa sem data_abertura -> mantida (seguranca)."""
    assert should_purge("Suspensa", OLD_DATE, None, now=NOW) is False


def test_suspensa_recent_pub():
    """Suspensa com publicacao recente -> mantida (protecao temporal)."""
    assert should_purge("Suspensa", RECENT_DATE, SUSPEND_OLD, now=NOW) is False


def test_dias_protecao_custom():
    """Flag --dias customizada funciona."""
    date_45_ago = NOW - timedelta(days=45)
    assert should_purge("Encerrada", date_45_ago, None, dias_protecao=30, now=NOW) is True
    assert should_purge("Encerrada", date_45_ago, None, dias_protecao=60, now=NOW) is False


def test_all_real_statuses_from_db():
    """Testa todos os 33 valores reais encontrados no banco."""
    expected = {
        "Finalizada": "purge",
        "Fracassada": "purge",
        "Encerrada": "purge",
        "Divulgada no PNCP": "keep",
        "Em realizacao": "keep",
        "Revogada": "purge",
        "": "keep",
        "Deserta": "purge",
        "Anulada": "purge",
        "Recebendo propostas": "keep",
        "Homologacao": "purge",
        "Em andamento": "keep",
        "Esperando realizacao": "keep",
        "Excluida": "purge",
        "Publicacao": "keep",
        "Suspensa": "suspend",
        "Publicada": "keep",
        "publicada": "keep",
        "Cancelada": "purge",
        "Publicacao Ata Registro Precos(ARP)": "keep",
        "desconhecido": "keep",
        "homologada": "purge",
        "Agendada": "keep",
        "Adjudicacao/Homologacao": "purge",
        "Adjudicacao": "purge",
        "em_julgamento": "keep",
        "com_recurso": "keep",
        "Fracassado": "purge",
        "Revogacao": "purge",
        "Anulacao": "purge",
        "Impugnacao/Edital": "keep",
        "Habilitacao": "keep",
    }
    for status, expected_cls in expected.items():
        result = classify_status(status)
        assert result == expected_cls, (
            f"'{status}': esperado '{expected_cls}', obtido '{result}'"
        )


# ── Runner ────────────────────────────────────────────


def run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    failed = 0
    for test_fn in tests:
        name = test_fn.__name__
        try:
            test_fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"  {passed} passed, {failed} failed")
    print(f"{'='*40}")
    return failed == 0


if __name__ == "__main__":
    import sys
    ok = run_all()
    sys.exit(0 if ok else 1)
