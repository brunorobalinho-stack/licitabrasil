# Sistema de Auditoria Inteligente de Folhas de Pagamento — Design

**Data:** 2026-03-02
**Status:** Aprovado

## Visao Geral

Projeto separado para auditoria de folhas de pagamento de empresas terceirizadas em contratos publicos. Extrai dados de PDFs, aplica 13 regras de auditoria com gravidade classificada, e apresenta resultados em dashboard web.

## Decisoes Tecnicas

| Aspecto | Decisao |
|---|---|
| Projeto | Separado do LicitaBrasil (novo repositorio) |
| Stack | Express + Prisma 6 + PostgreSQL 16 + React 19 + Vite + Tailwind CSS v4 |
| Port backend | 3002 |
| PDF Parser | Python `pdfplumber` via `execFile()` do Node.js |
| Banco | PostgreSQL (database separado, mesma instancia) |
| Auth | Sem autenticacao no MVP |

## Arquitetura

```
auditor-folha/
├── backend/
│   ├── prisma/schema.prisma
│   ├── src/
│   │   ├── server.ts                    # Express (port 3002)
│   │   ├── config/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── upload.ts            # Upload de PDFs
│   │   │   │   ├── folhas.ts            # CRUD folhas de pagamento
│   │   │   │   ├── auditoria.ts         # Regras + flags
│   │   │   │   ├── contratos.ts         # CRUD contratos
│   │   │   │   ├── cct.ts               # CRUD CCT e pisos
│   │   │   │   ├── configuracoes.ts     # Config regras auditoria
│   │   │   │   └── dashboard.ts         # Dados resumo
│   │   │   └── services/
│   │   │       ├── pdf-parser.ts        # Extracao pdf-parse + regex
│   │   │       ├── rubrica-mapper.ts    # Mapeia rubricas do PDF -> campos padrao
│   │   │       └── audit-engine.ts      # Motor de regras de auditoria
│   │   └── lib/
│   └── uploads/                          # PDFs uploadados (gitignored)
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx         # Cards resumo + top flags
│   │   │   ├── UploadPage.tsx            # Upload + selecao mes/contrato
│   │   │   ├── FolhaPage.tsx             # Visualizacao dados extraidos
│   │   │   ├── AuditoriaPage.tsx         # Lista flags com filtros
│   │   │   └── ConfiguracoesPage.tsx     # Config regras auditoria
│   │   ├── components/
│   │   ├── stores/
│   │   └── services/
│   └── ...
└── docs/
```

### Fluxo Principal

1. Usuario faz upload de PDF(s) selecionando mes de referencia e contrato
2. Backend extrai dados via `pdf-parse` -> parser regex -> normalizacao de rubricas
3. Dados salvos no PostgreSQL (por funcionario/mes/contrato)
4. Motor de auditoria roda as 13 regras sobre os dados extraidos
5. Frontend exibe dados e flags com filtros por gravidade

## Modelo de Dados

### Contrato
```
id: cuid (PK)
codigo: string (unique) — Ex: "COMPESA-012"
nome: string — Ex: "Limpeza - Sede COMPESA"
cctId: string? (FK -> ConvencaoColetiva)
createdAt: datetime
```

### ConvencaoColetiva (CCT)
```
id: cuid (PK)
nome: string — Ex: "SINDIASSEIO-PE 2024/2025"
sindicato: string
vigenciaInicio: datetime
vigenciaFim: datetime
createdAt: datetime
```

### PisoCCT
```
id: cuid (PK)
cctId: string (FK -> ConvencaoColetiva)
cargo: string — Ex: "AUXILIAR DE LIMPEZA"
pisoSalarial: decimal
adicionalInsalubridade: decimal?
adicionalPericulosidade: decimal?
adicionalNoturno: decimal?
@@unique([cctId, cargo])
```

### FolhaPagamento
```
id: cuid (PK)
contratoId: string (FK -> Contrato)
mesReferencia: string — "2024-06"
arquivoPdf: string
status: enum PENDENTE | PROCESSANDO | CONCLUIDO | ERRO
totalProventos: decimal?
totalDescontos: decimal?
totalLiquido: decimal?
processadoEm: datetime?
createdAt: datetime
@@unique([contratoId, mesReferencia])
```

### FuncionarioFolha
```
id: cuid (PK)
folhaId: string (FK -> FolhaPagamento)
nome: string
cpf: string (indexed)
cargo: string
salarioBase: decimal
horasNormais: decimal (default 0)
horasExtras50: decimal (default 0)
horasExtras100: decimal (default 0)
adicionalNoturno: decimal (default 0)
adicionalInsalubridade: decimal (default 0)
adicionalPericulosidade: decimal (default 0)
faltasDias: int (default 0)
faltasDesconto: decimal (default 0)
atestadosDias: int (default 0)
dsrDesconto: decimal (default 0)
valeTransporte: decimal (default 0)
valeAlimentacao: decimal (default 0)
inss: decimal (default 0)
irrf: decimal (default 0)
outrosProventos: decimal (default 0)
outrosDescontos: decimal (default 0)
totalProventos: decimal
totalDescontos: decimal
liquido: decimal
observacoes: string?
```

### AuditFlag
```
id: cuid (PK)
folhaId: string (FK -> FolhaPagamento)
cpf: string? — null = flag da folha inteira
regra: string — "FALTAS_EXCESSIVAS", "HE_ACIMA_40H", etc.
gravidade: enum CRITICO | ALERTA | OPORTUNIDADE
descricao: string
valorAtual: decimal?
valorCorreto: decimal?
economiaPotencial: decimal?
acaoSugerida: string?
createdAt: datetime
```

### ConfiguracaoAuditoria
```
id: cuid (PK)
regra: string (unique)
ativo: boolean (default true)
parametros: json — { "limiteFaltas": 5, "limiteHE": 40, ... }
updatedAt: datetime
```

## Motor de Auditoria

Cada regra e uma funcao pura que recebe dados do funcionario, parametros configuraveis, e historico opcional.

### Regras Implementadas

#### CRITICO
1. **FALTAS_EXCESSIVAS** — Mais de N faltas sem justificativa (default: 5)
2. **HE_ACIMA_LIMITE** — Horas extras acima de N horas/mes (default: 40)
3. **NOTURNO_INDEVIDO** — Adicional noturno para cargo/posto diurno
4. **FUNCIONARIO_FANTASMA** — CPF sem registro de ponto/contrato/escala

#### ALERTA
5. **ATESTADOS_RECORRENTES** — Atestados em N+ meses consecutivos (default: 3)
6. **VARIACAO_FOLHA** — Folha subiu mais de N% sem justificativa (default: 8%)
7. **ACUMULO_ADICIONAIS** — Insalubridade + periculosidade simultaneos
8. **DSR_NAO_DESCONTADO** — Faltas sem desconto DSR correspondente
9. **HE_100_EXCESSIVA** — Horas extras 100% acima de N horas/mes (default: 16)

#### OPORTUNIDADE
10. **SALARIO_ACIMA_PISO** — Salario acima do piso CCT sem justificativa
11. **VT_ACIMA_MEDIA** — Vale-transporte acima da media do local
12. **OUTROS_PROVENTOS_ALTO** — Outros proventos acima de N% do salario base (default: 10%)
13. **BANCO_HORAS_NAO_USADO** — HE pagas quando contrato permite banco de horas

### Parametros Configuraveis

Cada regra tem parametros ajustaveis via UI:
- Limites numericos (faltas, horas, percentuais)
- Toggle ativo/inativo por regra
- Valores default restauraveis

## Frontend (MVP)

### 5 Paginas

1. **Dashboard** (`/`) — Cards resumo (contratos, folhas, flags, economia), top 5 flags criticas, ultimos uploads
2. **Upload** (`/upload`) — Dropzone PDFs, seletor mes/contrato, progress bar
3. **Folha** (`/folhas/:id`) — Tabela funcionarios com badges de flags
4. **Auditoria** (`/auditoria`) — Lista flags com filtros (gravidade, contrato, mes, regra)
5. **Configuracoes** (`/configuracoes`) — Toggle regras, ajuste parametros

## Fase 2 (Futuro)

- Comparativo mensal por contrato, rubrica e funcionario
- Exportacao Excel (abas por contrato, consolidada, flags, comparativo)
- Relatorio executivo PDF (2 paginas, foco em economia)
- Dashboard com graficos de evolucao (Recharts)
- Top offenders (ranking de funcionarios por custo HE, faltas, atestados)
