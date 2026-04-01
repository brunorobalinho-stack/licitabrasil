import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { favoritos } from '../services/api';
import { useFavoritesStore } from '../stores/favorites-store';
import type { Licitacao, PaginatedResponse } from '../types';

interface FavoritoItem {
  id: string;
  licitacaoId: string;
  licitacao: Licitacao;
  notas: string | null;
  tags: string[];
}

export function useFavoritosList(page: number) {
  return useQuery({
    queryKey: ['favoritos', page],
    queryFn: () => favoritos.list(page, 20) as Promise<PaginatedResponse<FavoritoItem>>,
    staleTime: 60 * 1000, // 1 min
  });
}

export function useRemoveFavorito() {
  const queryClient = useQueryClient();
  const toggle = useFavoritesStore((s) => s.toggle);

  return useMutation({
    mutationFn: async (item: FavoritoItem) => {
      await toggle(item.licitacaoId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['favoritos'] });
    },
  });
}
