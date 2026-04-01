/**
 * Hook que gerencia os filtros de busca via URL usando nuqs.
 * Substitui o Zustand search-store + lógica manual de URL.
 *
 * Cada filtro é sincronizado automaticamente com a query string da URL,
 * permitindo compartilhamento de links, deep linking e navegação pelo
 * histórico do browser.
 */
import { useQueryStates } from 'nuqs';
import { useCallback, useMemo } from 'react';
import { filtrosLicitacaoParams } from '../lib/search-params';
import type { SearchFilters } from '../types';

/**
 * Opções de shallow routing — atualiza a URL sem causar navegação
 * no React Router (evita re-render da árvore inteira).
 */
const NUQS_OPTIONS = { history: 'push' as const, shallow: true };

export function useFiltrosUrl() {
  const [params, setParams] = useQueryStates(filtrosLicitacaoParams, NUQS_OPTIONS);

  /**
   * Converte os params do nuqs para o formato SearchFilters usado pela API.
   * Remove valores nulos (nuqs usa null para "ausente").
   */
  const filters: SearchFilters = useMemo(() => {
    const f: SearchFilters = {};
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== undefined && value !== '') {
        (f as any)[key] = value;
      }
    }
    return f;
  }, [params]);

  /**
   * Atualiza filtros parcialmente. Reseta a página para 1 ao mudar filtros.
   * Se o usuário digitar uma busca textual, muda ordenação para relevância.
   */
  const setFilters = useCallback(
    (newFilters: Partial<SearchFilters>) => {
      const updates: Record<string, any> = { ...newFilters, page: 1 };

      // Quando busca textual muda, ajusta ordenação automaticamente
      if (newFilters.q !== undefined) {
        updates.ordenarPor = newFilters.q ? 'relevancia' : 'dataPublicacao';
      }

      // nuqs usa null para remover da URL (diferente de undefined)
      for (const [key, value] of Object.entries(updates)) {
        if (value === undefined || value === '') {
          updates[key] = null;
        }
      }

      setParams(updates);
    },
    [setParams],
  );

  /** Limpa todos os filtros, voltando ao estado padrão */
  const resetFilters = useCallback(() => {
    // Seta tudo como null para limpar a URL
    const reset: Record<string, null> = {};
    for (const key of Object.keys(filtrosLicitacaoParams)) {
      reset[key] = null;
    }
    setParams(reset);
  }, [setParams]);

  /** Muda apenas a página (sem resetar para 1) */
  const setPage = useCallback(
    (page: number) => {
      setParams({ page });
    },
    [setParams],
  );

  return { filters, setFilters, resetFilters, setPage };
}
