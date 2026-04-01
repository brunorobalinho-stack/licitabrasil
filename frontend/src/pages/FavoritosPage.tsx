import { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { Star, Trash2, ArrowLeft } from 'lucide-react';
import { useAuthStore } from '../stores/auth-store';
import { LicitacaoCard } from '../components/search/LicitacaoCard';
import { useFavoritosList, useRemoveFavorito } from '../hooks/use-favoritos';

export function FavoritosPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const authLoading = useAuthStore((s) => s.loading);
  const [page, setPage] = useState(1);

  const { data, isLoading } = useFavoritosList(page);
  const removeMutation = useRemoveFavorito();

  const items = data?.data ?? [];
  const pagination = data?.pagination ?? null;

  if (authLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <Link to="/" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft size={16} /> Voltar à busca
      </Link>

      <div className="mb-6 flex items-center gap-2">
        <Star size={24} className="fill-yellow-400 text-yellow-400" />
        <h1 className="text-2xl font-bold">Meus Favoritos</h1>
        {pagination && (
          <span className="ml-2 text-sm text-muted-foreground">
            ({pagination.total} {pagination.total === 1 ? 'item' : 'itens'})
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border bg-white p-10 text-center dark:border-gray-700 dark:bg-gray-900">
          <Star size={48} className="mx-auto mb-4 text-gray-300 dark:text-gray-600" />
          <p className="text-lg font-medium text-muted-foreground">Nenhum favorito ainda</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Use a estrela nos resultados de busca para salvar licitações aqui.
          </p>
          <Link
            to="/"
            className="mt-4 inline-flex rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 transition-colors"
          >
            Buscar licitações
          </Link>
        </div>
      ) : (
        <>
          <div className="space-y-4">
            {items.map((item) => (
              <div key={item.id} className="relative">
                <LicitacaoCard licitacao={item.licitacao} isAuthenticated={true} isFavorite={true} />
                <button
                  onClick={() => removeMutation.mutate(item)}
                  className="absolute top-3 right-3 rounded-md p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
                  aria-label="Remover dos favoritos"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {pagination && pagination.totalPages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Anterior
              </button>
              <span className="text-sm text-muted-foreground">
                {page} / {pagination.totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
                disabled={page === pagination.totalPages}
                className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Próxima
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
