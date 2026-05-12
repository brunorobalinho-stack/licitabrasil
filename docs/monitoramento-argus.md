# Monitor de Prazos — Integração Argus / Claude

Este doc descreve como conectar a scheduled task `monitor-prazos-licitacao`
do Claude ao LicitaBrasil, consolidando licitações do SQLite local com
prazos jurídicos e contratos vindos do Gmail.

## Fluxo recomendado

```
┌─────────────────────────────┐
│ cron / scheduled task diária│
└──────────────┬──────────────┘
               │
   ┌───────────┼────────────────┐
   ▼                            ▼
1. SCRAPING                  2. MONITOR
licitabrasil scrape all      licitabrasil monitor briefing
   --tag cliente-argus          --argus --dias 7 --saida out.md
   │                            │
   ▼                            ▼
data/*/*.db (SQLite)         briefing.md → Claude
                             cruzar com Gmail (jurídico)
                             criar eventos no Calendar
```

## Comandos

### 1) Atualizar dados dos portais Argus
```bash
cd ~/Projects/licitabrasil
source .venv/bin/activate

# Roda só os 3 scrapers da Argus: CBTU, FIEMG, PE-Integrado
licitabrasil scrape all --tag cliente-argus

# Ou um por vez
licitabrasil scrape run peintegrado sync --max-pages 10
licitabrasil scrape run fiemg sync
licitabrasil scrape run cbtu
```

### 2) Health-check dos portais
```bash
licitabrasil scrape status              # todos
licitabrasil scrape status --tag cliente-argus
```

### 3) Estatísticas locais
```bash
licitabrasil scrape stats               # contagem por scraper
licitabrasil scrape list                # metadados
```

### 4) Gerar briefing de prazos
```bash
# Markdown bonito (consumido pela scheduled task)
licitabrasil monitor briefing --argus --dias 7 --saida /tmp/briefing.md

# Tabela rich no terminal
licitabrasil monitor prazos --argus --dias 7

# JSON pra integração programática
licitabrasil monitor prazos --argus --dias 7 --formato json
```

## Atualizando a scheduled task do Claude

A scheduled task `monitor-prazos-licitacao` deve, **antes** de ler Gmail,
chamar o pipeline acima. SKILL.md atualizada:

```markdown
## Passos

### 0. Atualizar dados locais (LicitaBrasil)
Executar (via bash):
```
cd ~/Projects/licitabrasil && source .venv/bin/activate && \
  licitabrasil scrape all --tag cliente-argus && \
  licitabrasil monitor briefing --argus --dias 7 --saida /tmp/argus-briefing.md
```

### 1. Ler o briefing gerado
Ler /tmp/argus-briefing.md — contém prazos de PE-Integrado, FIEMG e CBTU.

### 2. Buscar emails com prazos (apenas jurídico / contratos)
[mesmas keywords de antes]

### 3. Cruzar e classificar
Combinar prazos do briefing + emails. Manter classificação CRITICO/ATENCAO/PLANEJAMENTO.

### 4-5. Verificar calendário, gerar relatório, sugerir ações
[idêntico ao anterior]
```

## Cron sugerido (Mac / launchd)

```bash
# 6h da manhã todo dia útil — scraping + monitor antes do briefing do Claude
0 6 * * 1-5 cd ~/Projects/licitabrasil && \
  /Users/brunorobalinho/Projects/licitabrasil/.venv/bin/licitabrasil scrape all \
    --tag cliente-argus >> ~/Library/Logs/licitabrasil-scrape.log 2>&1

# 7h da manhã — gerar briefing pra Claude consumir no horário dele (7:33)
33 7 * * 1-5 cd ~/Projects/licitabrasil && \
  /Users/brunorobalinho/Projects/licitabrasil/.venv/bin/licitabrasil monitor briefing \
    --argus --dias 7 --saida /tmp/argus-briefing.md \
    >> ~/Library/Logs/licitabrasil-monitor.log 2>&1
```

## Scrapers disponíveis

| Nome              | Esfera     | UF | Tag                 |
|-------------------|------------|----|---------------------|
| `cbtu`            | federal    | —  | cliente-argus       |
| `fiemg`           | agregador  | MG | cliente-argus       |
| `peintegrado`     | estadual   | PE | cliente-argus       |
| `jfpe`            | federal    | PE | judiciario          |
| `maceio`          | municipal  | AL | municipio           |
| `central-natal`   | municipal  | RN | municipio           |
| `portalcompras-ce`| estadual   | CE | estado              |
| `prefeitura-sp`   | municipal  | SP | municipio           |

## Resultados do probe (12/05/2026)

### PE-Integrado ✅ paths corrigidos, parser ajustado
O domínio `peintegrado.pe.gov.br` está no ar e respondeu. Achados:

- Os paths originais (`/internet/consultaProcessos.seam`) **não existem** — o portal usa **ASP.NET WebForms**, não JSF.
- Paths reais (já gravados em `config.py`):
  - `/Portal/Pages/LicitacoesEmAndamento.aspx` — pregões, concorrências
  - `/Portal/Pages/DispensaLicitacoes.aspx` — compras diretas (CCD)
  - `/Portal/Pages/LicitacoesEncerradas.aspx`
- Tabela usa `id=exibirDados` (dispensa) ou classe `small-fonts-table` (andamento) com 17–18 colunas. Schema já mapeado no parser.
- **Limitação conhecida**: a página vem com `<tbody>` vazio. Os dados só carregam após postback ASP.NET (`__doPostBack` em controles `ctl00$ConteudoCentral$...`). O ViewState já é capturado e replicado, mas o controle exato pra disparar listagem completa ainda precisa de mais probe (provavelmente um filtro ou botão "Pesquisar").
- **Fallback recomendado**: até descobrir o postback certo, alimentar o scraper com a lista de processos extraída dos e-mails de `sistema@peintegrado.pe.gov.br` (Gmail) e usar o scraper só pra buscar detalhes de cada um. Função pronta em `models.py`: `extract_processos(text)`.
- **Ou usar Playwright** (já dependência no `backend/`) pra renderizar a página com JS executado.

### FIEMG ❌ não testado (sandbox sem DNS)
O sandbox isolado bloqueou o DNS de `licitacoes.compras.fiemg.com.br`. O scraper estrutural existe (`config.py`, `models.py`, `client.py`, `parser.py`, `storage.py`, `cli.py`), mas não foi validado contra HTML real.

**Faltam:**
1. Rodar `python -m licitabrasil.scrapers.agregadores.fiemg probe --save /tmp/fiemg.html` no Mac do Bruno (com rede normal).
2. Mandar o `/tmp/fiemg.html` pra ajuste dos seletores no `parser.py`.
3. Confirmar URL de listagem (chutei `/portal/processos-em-andamento` — pode ser diferente).

## Próximos passos sugeridos

1. **Validar PE-Integrado / FIEMG** via `probe` (HTML real pode diferir
   dos seletores apostados):
   ```bash
   python -m licitabrasil.scrapers.estadual.peintegrado probe --save /tmp/pe.html
   python -m licitabrasil.scrapers.agregadores.fiemg probe --save /tmp/fiemg.html
   ```
   Inspecionar HTML e ajustar `parser.py` se necessário.

2. **Rodar `sync` real** dos 3 scrapers Argus:
   ```bash
   licitabrasil scrape all --tag cliente-argus
   ```

3. **Apontar a scheduled task** do Claude pra o comando
   `licitabrasil monitor briefing` (ver SKILL.md acima).
