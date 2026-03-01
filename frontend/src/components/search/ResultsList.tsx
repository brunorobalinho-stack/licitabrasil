import { useSearchStore } from '../../stores/search-store';
import { LicitacaoCard } from './LicitacaoCard';
import { ChevronLeft, ChevronRight, FileSearch } from 'lucide-react';

export function ResultsList() {
  const { results, pagination, loading, error, setPage } = useSearchStore();

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="mt-4 text-sm">Buscando licitações…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-900 dark:bg-red-950">
        <p className="text-red-700 dark:text-red-400">{error}</p>
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
    <div>
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
          <LicitacaoCard key={l.id} licitacao={l} />
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
