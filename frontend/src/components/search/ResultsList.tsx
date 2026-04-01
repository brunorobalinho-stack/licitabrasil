import { useFiltrosUrl } from '../../hooks/use-filtros-url';
import { useAuthStore } from '../../stores/auth-store';
import { useFavoritesStore } from '../../stores/favorites-store';
import { useSearchQuery } from '../../hooks/use-search-query';
import { LicitacaoCard } from './LicitacaoCard';
import { ChevronLeft, ChevronRight, FileSearch } from 'lucide-react';

export function ResultsList() {
  const { data, isLoading, isPlaceholderData, error } = useSearchQuery();
  const { setPage } = useFiltrosUrl();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const favoriteIds = useFavoritesStore((s) => s.ids);

  const results = data?.data ?? [];
  const pagination = data?.pagination ?? null;
  const highlights = data?.highlights ?? {};

  if (isLoading && !isPlaceholderData) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-900 dark:bg-red-950">
        <p className="text-red-700 dark:text-red-400">{error.message}</p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <FileSearch size={48} className="mb-4 opacity-50" />
        <h3 className="text-lg font-medium">Nenhuma licitação encontrada</h3>
        <p className="text-sm">Tente ajustar os filtros ou termos de busca</p>
      </div>
    );
  }

  return (
    <div className={isPlaceholderData ? 'opacity-60 transition-opacity' : ''}>
      {/* Result count */}
      {pagination && (
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            <strong>{pagination.total.toLocaleString('pt-BR')}</strong> licitações encontradas
          </p>
          <p className="text-sm text-muted-foreground">
            Página {pagination.page} de {pagination.totalPages}
          </p>
        </div>
      )}

      {/* Cards */}
      <div className="space-y-4">
        {results.map((l) => (
          <LicitacaoCard
            key={l.id}
            licitacao={l}
            highlight={highlights[l.id]}
            isAuthenticated={isAuthenticated}
            isFavorite={l.id in favoriteIds}
          />
        ))}
      </div>

      {/* Pagination */}
      {pagination && pagination.totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-2">
          <button
            disabled={pagination.page <= 1}
            onClick={() => setPage(pagination.page - 1)}
            className="flex items-center gap-1 rounded-lg border px-3 py-2 text-sm disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            <ChevronLeft size={16} /> Anterior
          </button>

          {generatePageNumbers(pagination.page, pagination.totalPages).map((p, i) =>
            p === '...' ? (
              <span key={`dots-${i}`} className="px-2 text-muted-foreground">…</span>
            ) : (
              <button
                key={p}
                onClick={() => setPage(p as number)}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  p === pagination.page
                    ? 'bg-primary text-white'
                    : 'border hover:bg-gray-50 dark:hover:bg-gray-800'
                }`}
              >
                {p}
              </button>
            ),
          )}

          <button
            disabled={pagination.page >= pagination.totalPages}
            onClick={() => setPage(pagination.page + 1)}
            className="flex items-center gap-1 rounded-lg border px-3 py-2 text-sm disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            Próxima <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border bg-white p-5 dark:border-gray-700 dark:bg-gray-900 animate-pulse">
      <div className="mb-3 flex gap-2">
        <div className="h-5 w-20 rounded-full bg-gray-200 dark:bg-gray-700" />
        <div className="h-5 w-28 rounded-full bg-gray-200 dark:bg-gray-700" />
      </div>
      <div className="mb-2 h-5 w-4/5 rounded bg-gray-200 dark:bg-gray-700" />
      <div className="mb-4 h-5 w-3/5 rounded bg-gray-200 dark:bg-gray-700" />
      <div className="mb-3 space-y-2">
        <div className="h-4 w-48 rounded bg-gray-100 dark:bg-gray-800" />
        <div className="h-4 w-36 rounded bg-gray-100 dark:bg-gray-800" />
      </div>
      <div className="mb-4 flex gap-4">
        <div className="h-4 w-24 rounded bg-gray-100 dark:bg-gray-800" />
        <div className="h-4 w-32 rounded bg-gray-100 dark:bg-gray-800" />
      </div>
      <div className="flex items-center justify-between border-t pt-3 dark:border-gray-700">
        <div className="h-3 w-20 rounded bg-gray-100 dark:bg-gray-800" />
        <div className="flex gap-2">
          <div className="h-7 w-16 rounded-lg bg-gray-100 dark:bg-gray-800" />
          <div className="h-7 w-16 rounded-lg bg-gray-100 dark:bg-gray-800" />
        </div>
      </div>
    </div>
  );
}

function generatePageNumbers(current: number, total: number): (number | string)[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | string)[] = [1];
  if (current > 3) pages.push('...');
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) {
    pages.push(p);
  }
  if (current < total - 2) pages.push('...');
  pages.push(total);
  return pages;
}
