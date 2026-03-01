import { useSearchStore } from '../../stores/search-store';
import {
  MODALIDADE_LABELS, ESFERA_LABELS, STATUS_LABELS,
  UF_LIST, UF_NAMES,
  type Esfera, type Modalidade, type StatusLicitacao,
} from '../../types';
import { Filter, RotateCcw } from 'lucide-react';

export function FilterPanel() {
  const { filters, setFilters, resetFilters, search } = useSearchStore();

  const apply = () => search();

  return (
    <aside className="w-full space-y-6 rounded-xl border bg-white p-5 dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-semibold text-lg">
          <Filter size={18} /> Filtros
        </h2>
        <button
          onClick={() => { resetFilters(); search(); }}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
        >
          <RotateCcw size={14} /> Limpar
        </button>
      </div>

      {/* Esfera */}
      <FilterSection title="📍 Esfera">
        <div className="flex flex-wrap gap-2">
          {(Object.keys(ESFERA_LABELS) as Esfera[]).map((e) => (
            <ChipToggle
              key={e}
              label={ESFERA_LABELS[e]}
              active={filters.esfera === e}
              onClick={() => { setFilters({ esfera: filters.esfera === e ? undefined : e }); apply(); }}
            />
          ))}
        </div>
      </FilterSection>

      {/* UF */}
      <FilterSection title="🗺️ Estado">
        <select
          value={filters.uf ?? ''}
          onChange={(e) => { setFilters({ uf: e.target.value || undefined }); apply(); }}
          className="w-full rounded-lg border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
        >
          <option value="">Todos os estados</option>
          {UF_LIST.map((uf) => (
            <option key={uf} value={uf}>{uf} - {UF_NAMES[uf]}</option>
          ))}
        </select>
      </FilterSection>

      {/* Modalidade */}
      <FilterSection title="📋 Modalidade">
        <select
          value={filters.modalidade ?? ''}
          onChange={(e) => { setFilters({ modalidade: (e.target.value || undefined) as Modalidade | undefined }); apply(); }}
          className="w-full rounded-lg border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
        >
          <option value="">Todas</option>
          {(Object.keys(MODALIDADE_LABELS) as Modalidade[]).map((m) => (
            <option key={m} value={m}>{MODALIDADE_LABELS[m]}</option>
          ))}
        </select>
      </FilterSection>

      {/* Status */}
      <FilterSection title="📊 Status">
        <select
          value={filters.status ?? ''}
          onChange={(e) => { setFilters({ status: (e.target.value || undefined) as StatusLicitacao | undefined }); apply(); }}
          className="w-full rounded-lg border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
        >
          <option value="">Todos</option>
          {(Object.keys(STATUS_LABELS) as StatusLicitacao[]).map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
          ))}
        </select>
      </FilterSection>

      {/* Valor */}
      <FilterSection title="💰 Valor Estimado">
        <div className="flex gap-2">
          <input
            type="number"
            placeholder="Mínimo"
            value={filters.valorMin ?? ''}
            onChange={(e) => setFilters({ valorMin: e.target.value ? Number(e.target.value) : undefined })}
            onBlur={apply}
            className="w-1/2 rounded-lg border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
          />
          <input
            type="number"
            placeholder="Máximo"
            value={filters.valorMax ?? ''}
            onChange={(e) => setFilters({ valorMax: e.target.value ? Number(e.target.value) : undefined })}
            onBlur={apply}
            className="w-1/2 rounded-lg border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
          />
        </div>
      </FilterSection>

      {/* Datas */}
      <FilterSection title="📅 Data de Publicação">
        <div className="flex gap-2">
          <input
            type="date"
            value={filters.dataPublicacaoInicio ?? ''}
            onChange={(e) => { setFilters({ dataPublicacaoInicio: e.target.value || undefined }); apply(); }}
            className="w-1/2 rounded-lg border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
          />
          <input
            type="date"
            value={filters.dataPublicacaoFim ?? ''}
            onChange={(e) => { setFilters({ dataPublicacaoFim: e.target.value || undefined }); apply(); }}
            className="w-1/2 rounded-lg border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
          />
        </div>
      </FilterSection>

      {/* Ordenação */}
      <FilterSection title="🔃 Ordenar por">
        <select
          value={filters.ordenarPor ?? 'dataPublicacao'}
          onChange={(e) => { setFilters({ ordenarPor: e.target.value as SearchFilters['ordenarPor'] }); apply(); }}
          className="w-full rounded-lg border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
        >
          <option value="dataPublicacao">Mais recentes</option>
          <option value="dataAbertura">Próxima abertura</option>
          <option value="valorEstimado">Maior valor</option>
        </select>
      </FilterSection>
    </aside>
  );
}

// ── Small sub-components ────────────────────────────────────────────────

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
      {children}
    </div>
  );
}

function ChipToggle({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
        active
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-gray-200 hover:border-gray-300 dark:border-gray-600'
      }`}
    >
      {label}
    </button>
  );
}

type SearchFilters = import('../../types').SearchFilters;
