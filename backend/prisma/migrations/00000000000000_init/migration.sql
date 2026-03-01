-- =============================================================================
-- LicitaBrasil - Initial Migration
-- Creates all tables, enums, indexes, extensions, and tsvector trigger
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- Enums
-- =============================================================================

CREATE TYPE "Modalidade" AS ENUM (
  'PREGAO_ELETRONICO',
  'PREGAO_PRESENCIAL',
  'CONCORRENCIA',
  'CONCORRENCIA_ELETRONICA',
  'TOMADA_DE_PRECOS',
  'CONVITE',
  'CONCURSO',
  'LEILAO',
  'DIALOGO_COMPETITIVO',
  'DISPENSA',
  'INEXIGIBILIDADE',
  'CREDENCIAMENTO',
  'RDC',
  'OUTRA'
);

CREATE TYPE "Esfera" AS ENUM (
  'FEDERAL',
  'ESTADUAL',
  'MUNICIPAL'
);

CREATE TYPE "StatusLicitacao" AS ENUM (
  'PUBLICADA',
  'ABERTA',
  'EM_ANDAMENTO',
  'SUSPENSA',
  'ADIADA',
  'ENCERRADA',
  'ANULADA',
  'REVOGADA',
  'DESERTA',
  'FRACASSADA',
  'HOMOLOGADA',
  'ADJUDICADA'
);

CREATE TYPE "TipoLicitacao" AS ENUM (
  'COMPRA',
  'SERVICO',
  'OBRA',
  'SERVICO_ENGENHARIA',
  'ALIENACAO',
  'CONCESSAO',
  'PERMISSAO',
  'LOCACAO',
  'OUTRO'
);

CREATE TYPE "FrequenciaAlerta" AS ENUM (
  'TEMPO_REAL',
  'DIARIO',
  'SEMANAL'
);

-- =============================================================================
-- Tables
-- =============================================================================

-- Licitacao (core table)
CREATE TABLE "Licitacao" (
    "id" TEXT NOT NULL,
    "numeroEdital" TEXT,
    "numeroProcesso" TEXT,
    "codigoUASG" TEXT,
    "codigoPNCP" TEXT,
    "modalidade" "Modalidade" NOT NULL,
    "tipo" "TipoLicitacao" NOT NULL,
    "natureza" TEXT,
    "regime" TEXT,
    "criterioJulgamento" TEXT,
    "orgao" TEXT NOT NULL,
    "orgaoSigla" TEXT,
    "esfera" "Esfera" NOT NULL,
    "uf" TEXT,
    "municipio" TEXT,
    "objeto" TEXT NOT NULL,
    "objetoResumido" TEXT,
    "valorEstimado" DECIMAL(65,30),
    "valorMinimo" DECIMAL(65,30),
    "valorMaximo" DECIMAL(65,30),
    "dataPublicacao" TIMESTAMP(3) NOT NULL,
    "dataAbertura" TIMESTAMP(3),
    "dataEncerramento" TIMESTAMP(3),
    "dataResultado" TIMESTAMP(3),
    "segmento" TEXT,
    "cnae" TEXT[],
    "palavrasChave" TEXT[],
    "urlEdital" TEXT,
    "urlAnexos" TEXT[],
    "status" "StatusLicitacao" NOT NULL,
    "situacao" TEXT,
    "fonteOrigem" TEXT NOT NULL,
    "urlOrigem" TEXT NOT NULL,
    "hashConteudo" TEXT NOT NULL,
    "searchVector" tsvector,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizadoEm" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Licitacao_pkey" PRIMARY KEY ("id")
);

-- ItemLicitacao
CREATE TABLE "ItemLicitacao" (
    "id" TEXT NOT NULL,
    "licitacaoId" TEXT NOT NULL,
    "numero" INTEGER NOT NULL,
    "descricao" TEXT NOT NULL,
    "quantidade" DECIMAL(65,30),
    "unidade" TEXT,
    "valorUnitario" DECIMAL(65,30),
    "valorTotal" DECIMAL(65,30),
    "codigoCatalogo" TEXT,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ItemLicitacao_pkey" PRIMARY KEY ("id")
);

-- Documento
CREATE TABLE "Documento" (
    "id" TEXT NOT NULL,
    "licitacaoId" TEXT NOT NULL,
    "tipo" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "tamanho" INTEGER,
    "formato" TEXT,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Documento_pkey" PRIMARY KEY ("id")
);

-- HistoricoStatus
CREATE TABLE "HistoricoStatus" (
    "id" TEXT NOT NULL,
    "licitacaoId" TEXT NOT NULL,
    "statusAnterior" "StatusLicitacao",
    "statusNovo" "StatusLicitacao" NOT NULL,
    "observacao" TEXT,
    "dataAlteracao" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "HistoricoStatus_pkey" PRIMARY KEY ("id")
);

-- Usuario
CREATE TABLE "Usuario" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "empresa" TEXT,
    "cnpj" TEXT,
    "senha" TEXT NOT NULL,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizadoEm" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Usuario_pkey" PRIMARY KEY ("id")
);

-- Alerta
CREATE TABLE "Alerta" (
    "id" TEXT NOT NULL,
    "usuarioId" TEXT NOT NULL,
    "palavrasChave" TEXT[],
    "modalidades" "Modalidade"[],
    "esferas" "Esfera"[],
    "estados" TEXT[],
    "municipios" TEXT[],
    "segmentos" TEXT[],
    "valorMinimo" DECIMAL(65,30),
    "valorMaximo" DECIMAL(65,30),
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "frequencia" "FrequenciaAlerta" NOT NULL,
    "canalNotificacao" TEXT[],
    "ultimoEnvio" TIMESTAMP(3),
    "totalEnviados" INTEGER NOT NULL DEFAULT 0,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Alerta_pkey" PRIMARY KEY ("id")
);

-- AlertaMatch
CREATE TABLE "AlertaMatch" (
    "id" TEXT NOT NULL,
    "alertaId" TEXT NOT NULL,
    "licitacaoId" TEXT NOT NULL,
    "enviadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AlertaMatch_pkey" PRIMARY KEY ("id")
);

-- Favorito
CREATE TABLE "Favorito" (
    "id" TEXT NOT NULL,
    "usuarioId" TEXT NOT NULL,
    "licitacaoId" TEXT NOT NULL,
    "notas" TEXT,
    "tags" TEXT[],
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Favorito_pkey" PRIMARY KEY ("id")
);

-- BuscaSalva
CREATE TABLE "BuscaSalva" (
    "id" TEXT NOT NULL,
    "usuarioId" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "filtros" JSONB NOT NULL,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "BuscaSalva_pkey" PRIMARY KEY ("id")
);

-- FonteDados
CREATE TABLE "FonteDados" (
    "id" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "tipo" TEXT NOT NULL,
    "esfera" "Esfera" NOT NULL,
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "ultimaColeta" TIMESTAMP(3),
    "ultimoSucesso" TIMESTAMP(3),
    "ultimaFalha" TIMESTAMP(3),
    "totalColetados" INTEGER NOT NULL DEFAULT 0,
    "totalErros" INTEGER NOT NULL DEFAULT 0,
    "intervaloMinutos" INTEGER NOT NULL DEFAULT 30,
    "configuracao" JSONB,
    "criadoEm" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizadoEm" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "FonteDados_pkey" PRIMARY KEY ("id")
);

-- =============================================================================
-- Unique constraints
-- =============================================================================

CREATE UNIQUE INDEX "Licitacao_codigoPNCP_key" ON "Licitacao"("codigoPNCP");
CREATE UNIQUE INDEX "Licitacao_hashConteudo_key" ON "Licitacao"("hashConteudo");
CREATE UNIQUE INDEX "Usuario_email_key" ON "Usuario"("email");
CREATE UNIQUE INDEX "AlertaMatch_alertaId_licitacaoId_key" ON "AlertaMatch"("alertaId", "licitacaoId");
CREATE UNIQUE INDEX "Favorito_usuarioId_licitacaoId_key" ON "Favorito"("usuarioId", "licitacaoId");
CREATE UNIQUE INDEX "FonteDados_nome_key" ON "FonteDados"("nome");

-- =============================================================================
-- Indexes
-- =============================================================================

CREATE INDEX "Licitacao_searchVector_idx" ON "Licitacao" USING GIN ("searchVector");
CREATE INDEX "Licitacao_esfera_uf_status_idx" ON "Licitacao"("esfera", "uf", "status");
CREATE INDEX "Licitacao_modalidade_dataAbertura_idx" ON "Licitacao"("modalidade", "dataAbertura");
CREATE INDEX "Licitacao_segmento_idx" ON "Licitacao"("segmento");
CREATE INDEX "Licitacao_dataPublicacao_idx" ON "Licitacao"("dataPublicacao");
CREATE INDEX "Licitacao_fonteOrigem_idx" ON "Licitacao"("fonteOrigem");

CREATE INDEX "ItemLicitacao_licitacaoId_idx" ON "ItemLicitacao"("licitacaoId");
CREATE INDEX "Documento_licitacaoId_idx" ON "Documento"("licitacaoId");
CREATE INDEX "HistoricoStatus_licitacaoId_idx" ON "HistoricoStatus"("licitacaoId");
CREATE INDEX "Alerta_usuarioId_idx" ON "Alerta"("usuarioId");
CREATE INDEX "Alerta_ativo_frequencia_idx" ON "Alerta"("ativo", "frequencia");
CREATE INDEX "AlertaMatch_alertaId_idx" ON "AlertaMatch"("alertaId");
CREATE INDEX "AlertaMatch_licitacaoId_idx" ON "AlertaMatch"("licitacaoId");
CREATE INDEX "Favorito_usuarioId_idx" ON "Favorito"("usuarioId");
CREATE INDEX "Favorito_licitacaoId_idx" ON "Favorito"("licitacaoId");
CREATE INDEX "BuscaSalva_usuarioId_idx" ON "BuscaSalva"("usuarioId");

-- =============================================================================
-- Foreign keys
-- =============================================================================

ALTER TABLE "ItemLicitacao" ADD CONSTRAINT "ItemLicitacao_licitacaoId_fkey"
    FOREIGN KEY ("licitacaoId") REFERENCES "Licitacao"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "Documento" ADD CONSTRAINT "Documento_licitacaoId_fkey"
    FOREIGN KEY ("licitacaoId") REFERENCES "Licitacao"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "HistoricoStatus" ADD CONSTRAINT "HistoricoStatus_licitacaoId_fkey"
    FOREIGN KEY ("licitacaoId") REFERENCES "Licitacao"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "Alerta" ADD CONSTRAINT "Alerta_usuarioId_fkey"
    FOREIGN KEY ("usuarioId") REFERENCES "Usuario"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "AlertaMatch" ADD CONSTRAINT "AlertaMatch_alertaId_fkey"
    FOREIGN KEY ("alertaId") REFERENCES "Alerta"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "AlertaMatch" ADD CONSTRAINT "AlertaMatch_licitacaoId_fkey"
    FOREIGN KEY ("licitacaoId") REFERENCES "Licitacao"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "Favorito" ADD CONSTRAINT "Favorito_usuarioId_fkey"
    FOREIGN KEY ("usuarioId") REFERENCES "Usuario"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "Favorito" ADD CONSTRAINT "Favorito_licitacaoId_fkey"
    FOREIGN KEY ("licitacaoId") REFERENCES "Licitacao"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "BuscaSalva" ADD CONSTRAINT "BuscaSalva_usuarioId_fkey"
    FOREIGN KEY ("usuarioId") REFERENCES "Usuario"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- =============================================================================
-- Full-text search: tsvector trigger
-- Automatically populates searchVector on INSERT/UPDATE using Portuguese config
-- Combines: objeto (weight A), orgao (weight B), palavrasChave (weight C)
-- =============================================================================

CREATE OR REPLACE FUNCTION licitacao_search_vector_trigger() RETURNS trigger AS $$
BEGIN
  NEW."searchVector" :=
    setweight(to_tsvector('portuguese', COALESCE(NEW."objeto", '')), 'A') ||
    setweight(to_tsvector('portuguese', COALESCE(NEW."orgao", '')), 'B') ||
    setweight(to_tsvector('portuguese', COALESCE(array_to_string(NEW."palavrasChave", ' '), '')), 'C') ||
    setweight(to_tsvector('portuguese', COALESCE(NEW."objetoResumido", '')), 'D');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER licitacao_search_vector_update
  BEFORE INSERT OR UPDATE ON "Licitacao"
  FOR EACH ROW
  EXECUTE FUNCTION licitacao_search_vector_trigger();

-- Populate searchVector for any existing rows
UPDATE "Licitacao" SET "atualizadoEm" = "atualizadoEm" WHERE "searchVector" IS NULL;
