import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { licitacoes } from '../services/api';
import type { Licitacao } from '../types';
import { MODALIDADE_LABELS, ESFERA_LABELS, STATUS_LABELS, STATUS_COLORS } from '../types';
import { formatCurrency, formatDateTime, daysUntilLabel } from '../lib/utils';
import {
  ArrowLeft, Building2, MapPin, Calendar, Clock, ExternalLink,
  FileText, Download, History, Tag,
} from 'lucide-react';

export function LicitacaoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [lic, setLic] = useState<Licitacao | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    licitacoes.get(id)
      .then(setLic)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error || !lic) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <p className="text-red-600">{error ?? 'Licitação não encontrada'}</p>
        <Link to="/" className="mt-4 inline-flex items-center gap-1 text-primary hover:underline">
          <ArrowLeft size={16} /> Voltar à busca
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      {/* Back */}
      <Link to="/" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft size={16} /> Voltar à busca
      </Link>

      {/* Header */}
      <div className="mb-6 rounded-xl border bg-white p-6 dark:border-gray-700 dark:bg-gray-900">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${STATUS_COLORS[lic.status]}`}>
            {STATUS_LABELS[lic.status]}
          </span>
          <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium dark:bg-gray-800">
            {MODALIDADE_LABELS[lic.modalidade]}
          </span>
          {lic.numeroEdital && (
            <span className="text-sm text-muted-foreground">Edital nº {lic.numeroEdital}</span>
          )}
        </div>

        <h1 className="mb-4 text-xl font-bold leading-snug">{lic.objeto}</h1>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <InfoRow icon={<Building2 size={16} />} label="Órgão" value={lic.orgao} />
          <InfoRow icon={<MapPin size={16} />} label="Local" value={`${[lic.municipio, lic.uf].filter(Boolean).join(', ')} (${ESFERA_LABELS[lic.esfera]})`} />
          <InfoRow icon={<Calendar size={16} />} label="Publicação" value={formatDateTime(lic.dataPublicacao)} />
          <InfoRow icon={<Calendar size={16} />} label="Abertura" value={formatDateTime(lic.dataAbertura)} />
          {lic.dataEncerramento && (
            <InfoRow icon={<Clock size={16} />} label="Encerramento" value={formatDateTime(lic.dataEncerramento)} />
          )}
          {lic.dataAbertura && (
            <InfoRow icon={<Clock size={16} />} label="Prazo" value={daysUntilLabel(lic.dataAbertura)} />
          )}
        </div>

        {/* Values */}
        {lic.valorEstimado && (
          <div className="mt-4 rounded-lg bg-green-50 p-4 dark:bg-green-950">
            <p className="text-sm text-muted-foreground">Valor Estimado</p>
            <p className="text-2xl font-bold text-green-700 dark:text-green-400">
              {formatCurrency(lic.valorEstimado)}
            </p>
          </div>
        )}

        {/* External links */}
        <div className="mt-4 flex flex-wrap gap-2">
          <a
            href={lic.urlOrigem}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 transition-colors"
          >
            <ExternalLink size={14} /> Ver na fonte original
          </a>
          {lic.urlEdital && (
            <a
              href={lic.urlEdital}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              <Download size={14} /> Baixar Edital
            </a>
          )}
        </div>
      </div>

      {/* Additional info */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Details */}
        <div className="rounded-xl border bg-white p-5 dark:border-gray-700 dark:bg-gray-900">
          <h2 className="mb-3 flex items-center gap-2 font-semibold">
            <Tag size={16} /> Informações Adicionais
          </h2>
          <dl className="space-y-2 text-sm">
            {lic.numeroProcesso && <DlRow label="Processo" value={lic.numeroProcesso} />}
            {lic.codigoUASG && <DlRow label="UASG" value={lic.codigoUASG} />}
            {lic.codigoPNCP && <DlRow label="Código PNCP" value={lic.codigoPNCP} />}
            {lic.criterioJulgamento && <DlRow label="Julgamento" value={lic.criterioJulgamento} />}
            {lic.natureza && <DlRow label="Natureza" value={lic.natureza} />}
            {lic.regime && <DlRow label="Regime" value={lic.regime} />}
            <DlRow label="Fonte" value={lic.fonteOrigem} />
          </dl>

          {lic.palavrasChave.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-sm font-medium text-muted-foreground">Palavras-chave</p>
              <div className="flex flex-wrap gap-1">
                {lic.palavrasChave.slice(0, 15).map((kw) => (
                  <span key={kw} className="rounded-full bg-gray-100 px-2 py-0.5 text-xs dark:bg-gray-800">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Documents & History */}
        <div className="space-y-6">
          {/* Documents */}
          {lic.documentos && lic.documentos.length > 0 && (
            <div className="rounded-xl border bg-white p-5 dark:border-gray-700 dark:bg-gray-900">
              <h2 className="mb-3 flex items-center gap-2 font-semibold">
                <FileText size={16} /> Documentos
              </h2>
              <ul className="space-y-2">
                {lic.documentos.map((doc) => (
                  <li key={doc.id}>
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-sm text-primary hover:underline"
                    >
                      <Download size={14} />
                      {doc.nome}
                      {doc.formato && <span className="text-xs text-muted-foreground">({doc.formato})</span>}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* History */}
          {lic.historico && lic.historico.length > 0 && (
            <div className="rounded-xl border bg-white p-5 dark:border-gray-700 dark:bg-gray-900">
              <h2 className="mb-3 flex items-center gap-2 font-semibold">
                <History size={16} /> Histórico
              </h2>
              <ul className="space-y-3">
                {lic.historico.map((h) => (
                  <li key={h.id} className="border-l-2 border-primary/30 pl-3">
                    <p className="text-sm font-medium">
                      {h.statusAnterior ? `${STATUS_LABELS[h.statusAnterior]} → ` : ''}
                      {STATUS_LABELS[h.statusNovo]}
                    </p>
                    {h.observacao && <p className="text-xs text-muted-foreground">{h.observacao}</p>}
                    <p className="text-xs text-muted-foreground">{formatDateTime(h.dataAlteracao)}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function InfoRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2 text-sm">
      <span className="mt-0.5 text-muted-foreground">{icon}</span>
      <div>
        <span className="text-muted-foreground">{label}: </span>
        <span className="font-medium">{value}</span>
      </div>
    </div>
  );
}

function DlRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
