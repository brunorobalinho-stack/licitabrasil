# Scraper Prefeitura de SP — Design

**Data:** 2026-03-05
**Fonte:** PNCP API (filtro municipal São Paulo)
**Tipo:** Python standalone (padrão Natal/Maceió/CE)

## Estratégia

Consumir a API REST do PNCP filtrando por `codigoMunicipioIbge=3550308` (São Paulo)
e pós-filtrando `esferaId=M` (esfera municipal). Itera sobre 13 modalidades de
contratação. Armazena em SQLite local.

### Fontes analisadas e descartadas

- **Diário Oficial SP**: HTML POST funcional, mas dados menos estruturados. Pode ser
  adicionado no futuro como fonte complementar.
- **Dados Abertos SP**: CSV estático anual, ~6 meses de atraso. Só contratos, não
  licitações completas. Descartado.

## Estrutura

```
scrapers/prefeitura_sp/
├── __init__.py
├── __main__.py
├── config.py      — Settings(env_prefix="PREFSP_")
├── models.py      — LicitacaoSP, OrgaoSP
├── client.py      — PrefeituraSPClient (httpx async)
├── storage.py     — SQLite, PK = numero_controle_pncp
├── cli.py         — sync, search, stats, export
```

## API PNCP

**Endpoint:** `GET /api/consulta/v1/contratacoes/publicacao`

**Parâmetros de filtro:**
- `dataInicial`, `dataFinal` (yyyyMMdd) — obrigatórios, max 365 dias
- `codigoModalidadeContratacao` (1-13) — obrigatório
- `uf=SP` + `codigoMunicipioIbge=3550308` — filtro geográfico
- `pagina` (min 1), `tamanhoPagina` (10-50)

**Pós-filtro client-side:** `item.orgaoEntidade.esferaId == "M"`

Isso retorna os 14+ órgãos municipais de SP automaticamente (secretarias,
subprefeituras, autarquias).

## Modelo de dados

- `numero_controle_pncp` — PK (ex: "46395000000139-1-000005/2025")
- `numero_compra`, `numero_processo`, `ano_compra`
- Órgão: `orgao_cnpj`, `orgao_nome`, `orgao_unidade`
- Modalidade: `modalidade_id`, `modalidade`, `modo_disputa`
- `objeto`, `valor_estimado`, `valor_homologado`
- Datas: `data_publicacao`, `data_abertura`, `data_encerramento`
- `situacao`, `srp`, `link_sistema_origem`
- Metadados: `fonte="PNCP-PMSP"`, `uf="SP"`, `municipio="São Paulo"`
- `hash_registro` (MD5 para change detection)

## CLI

```bash
python -m scrapers.prefeitura_sp sync             # últimos 7 dias
python -m scrapers.prefeitura_sp sync --full       # 365 dias
python -m scrapers.prefeitura_sp sync --days 30    # últimos 30 dias
python -m scrapers.prefeitura_sp sync --modalidade 6  # só pregão eletrônico
python -m scrapers.prefeitura_sp search <keyword>
python -m scrapers.prefeitura_sp stats
python -m scrapers.prefeitura_sp export --format csv
```

## Decisões

1. **Python standalone** (não TS) — segue padrão dos scrapers mais recentes
2. **PNCP como fonte única** — API estruturada, dados ricos, tempo real
3. **Filtro geográfico + esfera** — captura todos os órgãos municipais automaticamente
4. **SQLite local** — independente do PostgreSQL do backend
