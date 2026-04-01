import { useQuery } from '@tanstack/react-query';
import { Activity, CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import { fontes } from '../services/api';
import type { FonteDados } from '../types';

export function ScraperStatusPage() {
  const { data, isLoading, error, refetch } = useQuery<FonteDados[]>({
    queryKey: ['fontes-status'],
    queryFn: fontes.status,
    refetchInterval: 30_000,
  });

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold">Status das Fontes</h1>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <RefreshCw size={14} /> Atualizar
        </button>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 text-sm">
          Erro ao carregar status das fontes. Verifique suas permissões.
        </div>
      )}

      {data && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm dark:bg-gray-900 dark:border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 dark:bg-gray-800/50">
                <th className="px-4 py-3 text-left font-medium">Fonte</th>
                <th className="px-4 py-3 text-left font-medium">Esfera</th>
                <th className="px-4 py-3 text-center font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Coletados</th>
                <th className="px-4 py-3 text-right font-medium">Erros</th>
                <th className="px-4 py-3 text-left font-medium">Último Sucesso</th>
              </tr>
            </thead>
            <tbody className="divide-y dark:divide-gray-800">
              {data.map((f) => (
                <tr key={f.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30">
                  <td className="px-4 py-3 font-medium">{f.nome}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs dark:bg-gray-800">
                      {f.esfera}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {f.healthy ? (
                      <CheckCircle className="mx-auto h-5 w-5 text-green-500" />
                    ) : (
                      <XCircle className="mx-auto h-5 w-5 text-red-500" />
                    )}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{f.totalColetados.toLocaleString('pt-BR')}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-red-600">{f.totalErros}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {f.ultimoSucesso ? new Date(f.ultimoSucesso).toLocaleString('pt-BR') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
