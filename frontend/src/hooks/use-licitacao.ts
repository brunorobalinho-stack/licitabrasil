import { useQuery } from '@tanstack/react-query';
import { licitacoes } from '../services/api';

export function useLicitacao(id: string | undefined) {
  return useQuery({
    queryKey: ['licitacao', id],
    queryFn: () => licitacoes.get(id!),
    enabled: !!id,
    staleTime: 10 * 60 * 1000, // 10 min — detalhe muda pouco
  });
}
