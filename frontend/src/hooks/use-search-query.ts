import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { useFiltrosUrl } from './use-filtros-url';
import { licitacoes } from '../services/api';

export function useSearchQuery() {
  const { filters } = useFiltrosUrl();

  return useQuery({
    queryKey: ['search', filters],
    queryFn: () => licitacoes.list(filters),
    placeholderData: keepPreviousData, // mantém resultado anterior enquanto carrega novo
    staleTime: 2 * 60 * 1000, // 2 min — busca muda mais frequentemente
  });
}
