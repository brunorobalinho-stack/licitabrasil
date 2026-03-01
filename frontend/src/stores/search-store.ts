import { create } from 'zustand';
import type { Licitacao, Pagination, SearchFilters } from '../types';
import { licitacoes } from '../services/api';

interface SearchState {
  results: Licitacao[];
  pagination: Pagination | null;
  filters: SearchFilters;
  loading: boolean;
  error: string | null;
  setFilters: (filters: Partial<SearchFilters>) => void;
  resetFilters: () => void;
  search: () => Promise<void>;
  setPage: (page: number) => void;
}

const DEFAULT_FILTERS: SearchFilters = {
  page: 1,
  pageSize: 20,
  ordenarPor: 'dataPublicacao',
  ordem: 'desc',
};

export const useSearchStore = create<SearchState>((set, get) => ({
  results: [],
  pagination: null,
  filters: { ...DEFAULT_FILTERS },
  loading: false,
  error: null,

  setFilters(newFilters) {
    set((s) => ({ filters: { ...s.filters, ...newFilters, page: 1 } }));
  },

  resetFilters() {
    set({ filters: { ...DEFAULT_FILTERS } });
  },

  async search() {
    const { filters } = get();
    set({ loading: true, error: null });
    try {
      const res = await licitacoes.list(filters);
      set({ results: res.data, pagination: res.pagination, loading: false });
    } catch (err) {
      set({ error: (err as Error).message, loading: false });
    }
  },

  setPage(page) {
    set((s) => ({ filters: { ...s.filters, page } }));
    get().search();
  },
}));
