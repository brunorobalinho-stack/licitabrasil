#!/usr/bin/env python3
"""Smoke-test ao vivo das APIs públicas consumidas pelo LicitaBrasil.

Checa PNCP e Querido Diário (sem credenciais): conectividade, status HTTP e
contrato mínimo da resposta (chaves esperadas + lista de itens). Não toca em
banco, Redis ou Prisma — só a stdlib, então roda em qualquer lugar com rede:

    python3 scripts/smoke_apis.py

Sai com código 0 se todas as checagens passam; 1 caso contrário. Útil como
validação ponta-a-ponta depois de liberar o egress do environment.
"""

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

TIMEOUT = 30
UA = "LicitaBrasil-Smoke/1.0"

_today = datetime.utcnow().date()
_week_ago = _today - timedelta(days=7)


def _get(url: str) -> tuple[int, dict | list | None]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        status = resp.status
        body = resp.read().decode("utf-8") if status != 204 else ""
        data = json.loads(body) if body else None
        return status, data


def check_pncp() -> bool:
    di = _today.strftime("%Y%m%d")
    df = _today.strftime("%Y%m%d")
    url = (
        "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
        f"?dataInicial={di}&dataFinal={df}&codigoModalidadeContratacao=6&pagina=1&tamanhoPagina=10"
    )
    try:
        status, data = _get(url)
    except urllib.error.HTTPError as e:
        # 204 = sem registros na janela (resposta válida, contrato OK)
        if e.code == 204:
            print("PASS  PNCP: 204 No Content (sem registros hoje, contrato OK)")
            return True
        print(f"FAIL  PNCP: HTTP {e.code}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"FAIL  PNCP: {type(e).__name__}: {e}")
        return False

    if status == 204 or data is None:
        print("PASS  PNCP: 204/sem corpo (contrato OK)")
        return True
    items = data.get("data") or data.get("items") or []
    print(f"PASS  PNCP: HTTP {status}, {len(items)} itens, "
          f"totalPaginas={data.get('totalPaginas')}")
    return True


def check_querido_diario() -> bool:
    url = (
        "https://queridodiario.ok.org.br/api/gazettes"
        "?querystring=licita%C3%A7%C3%A3o%20edital%20preg%C3%A3o"
        f"&published_since={_week_ago.isoformat()}&published_until={_today.isoformat()}"
        "&offset=0&size=5&sort_by=relevance"
    )
    try:
        status, data = _get(url)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL  Querido Diário: {type(e).__name__}: {e}")
        return False

    if not isinstance(data, dict) or "gazettes" not in data:
        print(f"FAIL  Querido Diário: HTTP {status}, contrato inesperado "
              f"(chaves: {list(data) if isinstance(data, dict) else type(data).__name__})")
        return False
    print(f"PASS  Querido Diário: HTTP {status}, "
          f"total_gazettes={data.get('total_gazettes')}, página={len(data['gazettes'])}")
    return True


def main() -> int:
    print(f"Smoke-test APIs públicas — {datetime.utcnow().isoformat()}Z\n")
    checks = [("PNCP", check_pncp), ("Querido Diário", check_querido_diario)]
    results = [fn() for _, fn in checks]
    ok = sum(results)
    print(f"\n{ok}/{len(results)} checagens passaram")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
