import { useEffect, useState } from 'react';
import { SearchBar } from '../components/search/SearchBar';
import { FilterPanel } from '../components/search/FilterPanel';
import { ResultsList } from '../components/search/ResultsList';
import { useSearchStore } from '../stores/search-store';
import { SlidersHorizontal, X } from 'lucide-react';

export function SearchPage() {
  const { search, pagination } = useSearchStore();
  const [showFilters, setShowFilters] = useState(true);

  // Initial load
  useEffect(() => {
    search();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      {/* Hero search */}
      <div className="mb-8 text-center">
        <h1 className="mb-2 text-3xl font-bold">
          Encontre Licitações em Todo o Brasil
        </h1>
        <p className="mb-6 text-muted-foreground">
          Pesquisa unificada em {pagination ? pagination.total.toLocaleString('pt-BR') + '+' : 'milhares de'} licitações de fontes federais, estaduais e municipais
        </p>
        <div className="mx-auto max-w-3xl">
          <SearchBar />
        </div>
      </div>

      {/* Toggle filters button (mobile) */}
      <button
        onClick={() => setShowFilters(!showFilters)}
        className="mb-4 flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium lg:hidden"
      >
        {showFilters ? <X size={16} /> : <SlidersHorizontal size={16} />}
        {showFilters ? 'Ocultar filtros' : 'Mostrar filtros'}
      </button>

      {/* Content area */}
      <div className="flex gap-6">
        {/* Sidebar filters */}
        {showFilters && (
          <div className="hidden w-72 shrink-0 lg:block">
            <FilterPanel />
          </div>
        )}

        {/* Mobile filters */}
        {showFilters && (
          <div className="mb-4 w-full lg:hidden">
            <FilterPanel />
          </div>
        )}

        {/* Results */}
        <div className="min-w-0 flex-1">
          <ResultsList />
        </div>
      </div>
    </div>
  );
}
