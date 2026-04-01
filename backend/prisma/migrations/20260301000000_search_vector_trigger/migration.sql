-- =============================================================================
-- Full-text search: trigger to populate searchVector on INSERT/UPDATE
-- =============================================================================

-- Function that builds a weighted tsvector from multiple fields
CREATE OR REPLACE FUNCTION licitacao_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW."searchVector" :=
    setweight(to_tsvector('portuguese', coalesce(NEW.objeto, '')), 'A') ||
    setweight(to_tsvector('portuguese', coalesce(NEW.orgao, '')), 'B') ||
    setweight(to_tsvector('portuguese', coalesce(array_to_string(NEW."palavrasChave", ' '), '')), 'B') ||
    setweight(to_tsvector('portuguese', coalesce(NEW.municipio, '') || ' ' || coalesce(NEW.uf, '')), 'C') ||
    setweight(to_tsvector('portuguese', coalesce(NEW."numeroEdital", '') || ' ' || coalesce(NEW."codigoPNCP", '')), 'D');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on INSERT and UPDATE
CREATE TRIGGER trg_licitacao_search_vector
  BEFORE INSERT OR UPDATE ON "Licitacao"
  FOR EACH ROW
  EXECUTE FUNCTION licitacao_search_vector_update();

-- Backfill all existing rows
UPDATE "Licitacao" SET
  "searchVector" =
    setweight(to_tsvector('portuguese', coalesce(objeto, '')), 'A') ||
    setweight(to_tsvector('portuguese', coalesce(orgao, '')), 'B') ||
    setweight(to_tsvector('portuguese', coalesce(array_to_string("palavrasChave", ' '), '')), 'B') ||
    setweight(to_tsvector('portuguese', coalesce(municipio, '') || ' ' || coalesce(uf, '')), 'C') ||
    setweight(to_tsvector('portuguese', coalesce("numeroEdital", '') || ' ' || coalesce("codigoPNCP", '')), 'D');
