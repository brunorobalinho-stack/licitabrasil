-- CreateIndex
CREATE INDEX "Licitacao_status_dataAbertura_idx" ON "Licitacao"("status", "dataAbertura");

-- CreateIndex
CREATE INDEX "Licitacao_dataEncerramento_idx" ON "Licitacao"("dataEncerramento");

-- CreateIndex
CREATE INDEX "Licitacao_criadoEm_idx" ON "Licitacao"("criadoEm");

-- CreateIndex
CREATE INDEX "Licitacao_status_idx" ON "Licitacao"("status");
