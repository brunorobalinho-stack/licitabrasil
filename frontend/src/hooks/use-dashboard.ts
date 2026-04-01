import { useQuery } from '@tanstack/react-query';
import { dashboard } from '../services/api';

export function useDashboardResumo() {
  return useQuery({
    queryKey: ['dashboard', 'resumo'],
    queryFn: dashboard.resumo,
  });
}

export function useDashboardPorEstado() {
  return useQuery({
    queryKey: ['dashboard', 'por-estado'],
    queryFn: dashboard.porEstado,
  });
}

export function useDashboardPorModalidade() {
  return useQuery({
    queryKey: ['dashboard', 'por-modalidade'],
    queryFn: dashboard.porModalidade,
  });
}

export function useDashboardTendencias() {
  return useQuery({
    queryKey: ['dashboard', 'tendencias'],
    queryFn: dashboard.tendencias,
  });
}
