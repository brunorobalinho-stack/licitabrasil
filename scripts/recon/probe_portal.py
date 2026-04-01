#!/usr/bin/env python3
"""Reconhecimento de portal de licitações.

Uso: python scripts/recon/probe_portal.py <url> [--save fixtures/nome_portal/]

Faz:
1. GET na URL com diferentes headers (Accept: application/json, text/html)
2. Detecta tecnologia (Server header, meta tags, JS frameworks)
3. Salva response completa (headers + body) como fixture
4. Identifica endpoints de API se existirem
5. Mapeia paginação
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("probe_portal")

# ---------------------------------------------------------------------------
# Detecção de tecnologia
# ---------------------------------------------------------------------------

TECH_SIGNATURES: dict[str, list[dict]] = {
    "Plone": [
        {"type": "header", "key": "x-powered-by", "pattern": r"(?i)plone"},
        {"type": "header", "key": "server", "pattern": r"(?i)zope"},
        {"type": "body", "pattern": r"portal_css|portal_javascripts|plone"},
    ],
    "JSF": [
        {"type": "body", "pattern": r"javax\.faces|jsf\.js|ViewState"},
        {"type": "body", "pattern": r"ice:form|icefaces"},
    ],
    "Angular": [
        {"type": "body", "pattern": r"ng-app|ng-controller|angular\.module"},
        {"type": "body", "pattern": r'<app-root|"@angular/core"'},
    ],
    "React": [
        {"type": "body", "pattern": r"react\.production|__NEXT_DATA__|reactroot"},
        {"type": "body", "pattern": r"data-reactroot|_reactRootContainer"},
    ],
    "WordPress": [
        {"type": "body", "pattern": r"wp-content|wp-includes|wordpress"},
        {"type": "header", "key": "x-powered-by", "pattern": r"(?i)wordpress"},
    ],
    "ASP.NET": [
        {"type": "header", "key": "x-powered-by", "pattern": r"(?i)asp\.net"},
        {"type": "body", "pattern": r"__VIEWSTATE|__EVENTVALIDATION"},
    ],
    "IBM Lotus/Domino": [
        {"type": "header", "key": "server", "pattern": r"(?i)lotus|domino"},
        {"type": "body", "pattern": r"domino|nsf\?open|\.nsf"},
    ],
    "Django": [
        {"type": "header", "key": "x-frame-options", "pattern": r"DENY"},
        {"type": "body", "pattern": r"csrfmiddlewaretoken|django"},
    ],
    "Spring": [
        {"type": "header", "key": "x-application-context", "pattern": r".+"},
        {"type": "body", "pattern": r"spring-security|SPRING_SECURITY"},
    ],
}

PAGINATION_PATTERNS = [
    r'[?&](page|pagina|p|offset|start|skip)=\d+',
    r'[?&](pageSize|per_page|limit|tamanhoPagina|qtd)=\d+',
    r'"(next|proximo|proxima|nextPage)":\s*"[^"]+"',
    r'"(totalPages|totalPaginas|total_pages|pages)":\s*\d+',
    r'"(hasMore|hasNext|temMais)":\s*(true|false)',
    r'rel="next"',
    r'class="[^"]*paginat[^"]*"',
]


def detectar_tecnologias(headers: dict[str, str], body: str) -> list[str]:
    """Detecta tecnologias a partir dos headers e body da resposta."""
    encontradas = []
    for tech, signatures in TECH_SIGNATURES.items():
        for sig in signatures:
            if sig["type"] == "header":
                valor = headers.get(sig["key"], "")
                if re.search(sig["pattern"], valor):
                    encontradas.append(tech)
                    break
            elif sig["type"] == "body":
                if re.search(sig["pattern"], body[:50_000]):
                    encontradas.append(tech)
                    break
    return encontradas


def detectar_paginacao(body: str) -> list[str]:
    """Identifica padrões de paginação no corpo da resposta."""
    encontrados = []
    for pattern in PAGINATION_PATTERNS:
        matches = re.findall(pattern, body[:100_000])
        if matches:
            encontrados.append(f"Padrão: {pattern} → {matches[:3]}")
    return encontrados


def extrair_links_api(body: str, base_url: str) -> list[str]:
    """Extrai URLs que parecem endpoints de API."""
    api_patterns = [
        r'href="(/api/[^"]+)"',
        r'"(https?://[^"]*api[^"]*)"',
        r'"(@id|url|href)":\s*"(https?://[^"]+)"',
        r'action="(/[^"]+)"',
        r'"(https?://[^"]*\.(json|xml|csv)[^"]*)"',
    ]
    links = set()
    for pattern in api_patterns:
        for match in re.finditer(pattern, body[:100_000]):
            url = match.group(match.lastindex)
            if url.startswith("/"):
                url = urljoin(base_url, url)
            links.add(url)
    return sorted(links)


# ---------------------------------------------------------------------------
# Probe principal
# ---------------------------------------------------------------------------

def probe(url: str, save_dir: Path | None = None) -> dict:
    """Faz reconhecimento completo de um portal.

    Retorna dict com resultados consolidados.
    """
    parsed = urlparse(url)
    resultado = {
        "url": url,
        "dominio": parsed.netloc,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "probes": [],
        "tecnologias": [],
        "paginacao": [],
        "links_api": [],
        "recomendacao": "",
    }

    accept_headers = [
        ("application/json", "json"),
        ("text/html", "html"),
        ("application/xml, text/xml", "xml"),
    ]

    client = httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "LicitaBrasil-Recon/1.0"},
    )

    todas_tecnologias = set()
    toda_paginacao = []
    todos_links_api = set()

    for accept, label in accept_headers:
        logger.info("Probando %s com Accept: %s", url, accept)
        try:
            resp = client.get(url, headers={"Accept": accept})
        except httpx.HTTPError as e:
            logger.warning("Falha com Accept=%s: %s", accept, e)
            resultado["probes"].append({
                "accept": accept,
                "label": label,
                "erro": str(e),
            })
            continue

        headers_dict = dict(resp.headers)
        content_type = resp.headers.get("content-type", "")
        body = resp.text

        # Detectar se retornou JSON válido
        is_json = False
        json_data = None
        if "json" in content_type or "json" in accept:
            try:
                json_data = resp.json()
                is_json = True
            except (json.JSONDecodeError, ValueError):
                pass

        probe_info = {
            "accept": accept,
            "label": label,
            "status": resp.status_code,
            "content_type": content_type,
            "content_length": len(body),
            "is_json": is_json,
            "server": headers_dict.get("server", ""),
            "powered_by": headers_dict.get("x-powered-by", ""),
        }

        # Detecção de tecnologia
        techs = detectar_tecnologias(headers_dict, body)
        if techs:
            todas_tecnologias.update(techs)
            probe_info["tecnologias"] = techs

        # Paginação
        pag = detectar_paginacao(body)
        if pag:
            toda_paginacao.extend(pag)
            probe_info["paginacao"] = pag

        # Links de API
        links = extrair_links_api(body, url)
        if links:
            todos_links_api.update(links)
            probe_info["links_api"] = links[:10]

        # Resumo JSON
        if is_json and json_data:
            if isinstance(json_data, dict):
                probe_info["json_keys"] = list(json_data.keys())[:20]
                probe_info["json_type"] = "object"
                # Detectar total/count
                for k in ("total", "count", "totalPages", "total_pages", "items_total"):
                    if k in json_data:
                        probe_info[f"json_{k}"] = json_data[k]
            elif isinstance(json_data, list):
                probe_info["json_type"] = "array"
                probe_info["json_count"] = len(json_data)
                if json_data:
                    probe_info["json_item_keys"] = list(json_data[0].keys())[:20] if isinstance(json_data[0], dict) else []

        resultado["probes"].append(probe_info)

        # Salvar fixture
        if save_dir:
            save_dir.mkdir(parents=True, exist_ok=True)
            # Headers
            (save_dir / f"response_{label}_headers.json").write_text(
                json.dumps(headers_dict, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            # Body
            ext = "json" if is_json else label
            body_file = save_dir / f"response_{label}.{ext}"
            body_file.write_text(body[:500_000], encoding="utf-8")
            logger.info("Fixture salva: %s", body_file)

    client.close()

    resultado["tecnologias"] = sorted(todas_tecnologias)
    resultado["paginacao"] = toda_paginacao
    resultado["links_api"] = sorted(todos_links_api)[:20]
    resultado["recomendacao"] = gerar_recomendacao(resultado)

    return resultado


# ---------------------------------------------------------------------------
# Recomendação
# TODO: Implemente a lógica de decisão httpx vs Playwright.
#       Considere: se retornou JSON válido → httpx puro;
#       se é Angular/React SPA sem API → Playwright;
#       se é JSF com ViewState → httpx com session tracking.
# ---------------------------------------------------------------------------

def gerar_recomendacao(resultado: dict) -> str:
    """Gera recomendação de abordagem para o scraper."""
    techs = resultado["tecnologias"]
    probes = resultado["probes"]

    tem_json = any(p.get("is_json") for p in probes)
    tem_spa = bool(set(techs) & {"Angular", "React"})
    tem_viewstate = "ASP.NET" in techs or "JSF" in techs

    if tem_json:
        return "httpx — portal retorna JSON, scraper direto via API"
    if tem_spa:
        return "playwright — SPA detectado, necessita renderização JS"
    if tem_viewstate:
        return "httpx+session — ViewState/ASP.NET, manter sessão entre requests"
    if "Plone" in techs:
        return "httpx — Plone detectado, tentar Accept: application/json"
    if "IBM Lotus/Domino" in techs:
        return "httpx — Lotus/Domino, HTML parsing pesado"
    return "httpx — abordagem padrão, verificar manualmente"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def imprimir_resultado(resultado: dict) -> None:
    """Imprime resultado formatado no terminal."""
    print(f"\n{'='*60}")
    print(f" RECONHECIMENTO: {resultado['dominio']}")
    print(f"{'='*60}")
    print(f" URL: {resultado['url']}")
    print(f" Data: {resultado['timestamp']}")

    for p in resultado["probes"]:
        print(f"\n--- Accept: {p['accept']} ---")
        if "erro" in p:
            print(f"  ERRO: {p['erro']}")
            continue
        print(f"  Status: {p['status']}")
        print(f"  Content-Type: {p['content_type']}")
        print(f"  Tamanho: {p['content_length']:,} bytes")
        print(f"  JSON válido: {'Sim' if p.get('is_json') else 'Nao'}")
        if p.get("server"):
            print(f"  Server: {p['server']}")
        if p.get("tecnologias"):
            print(f"  Tecnologias: {', '.join(p['tecnologias'])}")
        if p.get("json_keys"):
            print(f"  JSON keys: {p['json_keys']}")
        if p.get("json_item_keys"):
            print(f"  JSON item keys: {p['json_item_keys']}")
            print(f"  JSON items: {p.get('json_count', '?')}")
        if p.get("paginacao"):
            print(f"  Paginação: {len(p['paginacao'])} padrões")

    if resultado["tecnologias"]:
        print(f"\n Tecnologias detectadas: {', '.join(resultado['tecnologias'])}")

    if resultado["links_api"]:
        print(f"\n Possíveis endpoints de API ({len(resultado['links_api'])}):")
        for link in resultado["links_api"][:10]:
            print(f"   - {link}")

    if resultado["paginacao"]:
        print(f"\n Paginação ({len(resultado['paginacao'])} padrões):")
        for p in resultado["paginacao"][:5]:
            print(f"   - {p}")

    print(f"\n>> RECOMENDACAO: {resultado['recomendacao']}")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    # Forçar UTF-8 no stdout/stderr (Windows cp1252 não suporta acentos)
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Reconhecimento de portal de licitações",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", help="URL do portal para investigar")
    parser.add_argument(
        "--save", type=Path, default=None,
        help="Diretório para salvar fixtures (headers + body)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output em JSON (para pipeline)",
    )
    args = parser.parse_args()

    resultado = probe(args.url, save_dir=args.save)

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        imprimir_resultado(resultado)

    # Salvar relatório consolidado
    if args.save:
        relatorio = args.save / "probe_report.json"
        relatorio.write_text(
            json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Relatório salvo: %s", relatorio)


if __name__ == "__main__":
    main()
