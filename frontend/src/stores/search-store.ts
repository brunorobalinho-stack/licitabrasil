import { create } from 'zustand';
import type { SearchFilters } from '../types';

interface SearchState {
  filters: SearchFilters;
  setFilters: (filters: Partial<SearchFilters>) => void;
  resetFilters: () => void;
  setPage: (page: number) => void;
  loadFromUrl: () => void;
}

const DEFAULT_FILTERS: SearchFilters = {
  page: 1,
  pageSize: 20,
  ordenarPor: 'dataPublicacao',
  ordem: 'desc',
};

const URL_KEYS = ['q', 'esfera', 'uf', 'modalidade', 'status', 'codigoUASG', 'valorMin', 'valorMax', 'dataPublicacaoInicio', 'dataPublicacaoFim', 'ordenarPor', 'page'] as const;

function filtersToUrl(filters: SearchFilters) {
  const params = new URLSearchParams();
  for (const key of URL_KEYS) {
    const val = filters[key as keyof SearchFilters];
    if (val !== undefined && val !== null && val !== '') {
      if (key === 'page' && val === 1) continue;
      if (key === 'ordenarPor' && val === 'dataPublicacao') continue;
      params.set(key, String(val));
    }
  }
  const qs = params.toString();
  const url = qs ? `?${qs}` : window.location.pathname;
  window.history.replaceState(null, '', url);
}

function filtersFromUrl(): Partial<SearchFilters> {
  const params = new URLSearchParams(window.location.search);
  const parsed: Partial<SearchFilters> = {};
  for (const key of URL_KEYS) {
    const val = params.get(key);
    if (val === null) continue;
    if (key === 'page' || key === 'valorMin' || key === 'valorMax') {
      (parsed as any)[key] = Number(val);
    } else {
      (parsed as any)[key] = val;
    }
  }
  return parsed;
}

export const useSearchStore = create<SearchState>((set) => ({
  filters: { ...DEFAULT_FILTERS },

  loadFromUrl() {
    const fromUrl = filtersFromUrl();
    if (Object.keys(fromUrl).length > 0) {
      set({ filters: { ...DEFAULT_FILTERS, ...fromUrl } });
    }
  },

  setFilters(newFilters) {
    set((s) => {
      const merged = { ...s.filters, ...newFilters, page: 1 };
      if (newFilters.q !== undefined) {
        merged.ordenarPor = newFilters.q ? 'relevancia' : 'dataPublicacao';
      }
      filtersToUrl(merged);
      return { filters: merged };
    });
  },

  resetFilters() {
    set({ filters: { ...DEFAULT_FILTERS } });
    filtersToUrl(DEFAULT_FILTERS);
  },

  setPage(page) {
    set((s) => {
      const filters = { ...s.filters, page };
      filtersToUrl(filters);
      return { filters };
    });
  },
}));
