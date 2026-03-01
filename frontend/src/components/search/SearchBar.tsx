import { useState, useCallback } from 'react';
import { Search, X } from 'lucide-react';
import { useSearchStore } from '../../stores/search-store';

export function SearchBar() {
  const { filters, setFilters, search, loading } = useSearchStore();
  const [query, setQuery] = useState(filters.q ?? '');

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setFilters({ q: query || undefined });
      search();
    },
    [query, setFilters, search],
  );

  const handleClear = () => {
    setQuery('');
    setFilters({ q: undefined });
    search();
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="relative flex items-center">
        <Search className="absolute left-4 text-muted-foreground" size={20} />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar licitações... (ex: material informática, serviço limpeza, obra reforma)"
          className="w-full rounded-xl border border-gray-200 bg-white py-4 pl-12 pr-28 text-base shadow-sm transition-shadow focus:border-primary focus:shadow-md focus:outline-none dark:border-gray-700 dark:bg-gray-900"
        />
        <div className="absolute right-2 flex items-center gap-1">
          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="rounded-lg p-2 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X size={18} />
            </button>
          )}
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Buscando…' : 'Buscar'}
          </button>
        </div>
      </div>
    </form>
  );
}
