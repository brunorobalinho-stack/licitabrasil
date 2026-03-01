import { Link } from 'react-router-dom';
import { Building2, MapPin, Calendar, Clock, ExternalLink } from 'lucide-react';
import type { Licitacao } from '../../types';
import { MODALIDADE_LABELS, ESFERA_LABELS, STATUS_LABELS, STATUS_COLORS } from '../../types';
import { formatCurrency, formatDateTime, daysUntilLabel } from '../../lib/utils';

interface Props {
  licitacao: Licitacao;
}

export function LicitacaoCard({ licitacao }: Props) {
  const l = licitacao;
  const deadlineLabel = daysUntilLabel(l.dataAbertura);

  return (
    <article className="group rounded-xl border bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-primary/30 dark:border-gray-700 dark:bg-gray-900">
      {/* Top row: Status + Modalidade + Edital */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_COLORS[l.status]}`}>
          {STATUS_LABELS[l.status]}
        </span>
        <span className="text-xs font-medium text-muted-foreground">
          {MODALIDADE_LABELS[l.modalidade]}
        </span>
        {l.numeroEdital && (
          <span className="text-xs text-muted-foreground">
            nº {l.numeroEdital}
          </span>
        )}
      </div>

      {/* Object description */}
      <Link to={`/licitacao/${l.id}`} className="block">
        <h3 className="mb-2 font-semibold leading-snug text-gray-900 group-hover:text-primary transition-colors dark:text-gray-100 line-clamp-2">
          {l.objeto}
        </h3>
      </Link>

      {/* Meta info */}
      <div className="mb-3 space-y-1 text-sm text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <Building2 size={14} />
          <span className="truncate">{l.orgao}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <MapPin size={14} />
          <span>
            {[l.municipio, l.uf].filter(Boolean).join(', ') || 'Não informado'}
            {' '}
            <span className="text-xs">({ESFERA_LABELS[l.esfera]})</span>
          </span>
        </div>
      </div>

      {/* Value + Dates */}
      <div className="mb-4 flex flex-wrap items-center gap-4 text-sm">
        {l.valorEstimado && (
          <span className="font-semibold text-green-700 dark:text-green-400">
            {formatCurrency(l.valorEstimado)}
          </span>
        )}
        {l.dataAbertura && (
          <span className="flex items-center gap-1 text-muted-foreground">
            <Calendar size={14} />
            Abertura: {formatDateTime(l.dataAbertura)}
          </span>
        )}
        {deadlineLabel && (
          <span className="flex items-center gap-1 text-orange-600 dark:text-orange-400 font-medium">
            <Clock size={14} />
            {deadlineLabel}
          </span>
        )}
      </div>

      {/* Footer: source + actions */}
      <div className="flex items-center justify-between border-t pt-3 dark:border-gray-700">
        <span className="text-xs text-muted-foreground">
          Fonte: {l.fonteOrigem}
        </span>
        <div className="flex items-center gap-2">
          <Link
            to={`/licitacao/${l.id}`}
            className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            Detalhes
          </Link>
          {l.urlEdital && (
            <a
              href={l.urlEdital}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              <ExternalLink size={12} className="inline mr-1" />Edital
            </a>
          )}
          <a
            href={l.urlOrigem}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
          >
            <ExternalLink size={12} className="inline mr-1" />Fonte
          </a>
        </div>
      </div>
    </article>
  );
}
