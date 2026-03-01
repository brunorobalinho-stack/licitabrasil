// ── Enums (mirror backend) ──────────────────────────────────────────────

export type Modalidade =
  | 'PREGAO_ELETRONICO' | 'PREGAO_PRESENCIAL'
  | 'CONCORRENCIA' | 'CONCORRENCIA_ELETRONICA'
  | 'TOMADA_DE_PRECOS' | 'CONVITE' | 'CONCURSO' | 'LEILAO'
  | 'DIALOGO_COMPETITIVO' | 'DISPENSA' | 'INEXIGIBILIDADE'
  | 'CREDENCIAMENTO' | 'RDC' | 'OUTRA';

export type Esfera = 'FEDERAL' | 'ESTADUAL' | 'MUNICIPAL';

export type StatusLicitacao =
  | 'PUBLICADA' | 'ABERTA' | 'EM_ANDAMENTO'
  | 'SUSPENSA' | 'ADIADA' | 'ENCERRADA'
  | 'ANULADA' | 'REVOGADA' | 'DESERTA'
  | 'FRACASSADA' | 'HOMOLOGADA' | 'ADJUDICADA';

export type TipoLicitacao =
  | 'COMPRA' | 'SERVICO' | 'OBRA' | 'SERVICO_ENGENHARIA'
  | 'ALIENACAO' | 'CONCESSAO' | 'PERMISSAO' | 'LOCACAO' | 'OUTRO';

// ── Models ──────────────────────────────────────────────────────────────

export interface Licitacao {
  id: string;
  numeroEdital: string | null;
  numeroProcesso: string | null;
  codigoUASG: string | null;
  codigoPNCP: string | null;
  modalidade: Modalidade;
  tipo: TipoLicitacao;
  natureza: string | null;
  regime: string | null;
  criterioJulgamento: string | null;
  orgao: string;
  orgaoSigla: string | null;
  esfera: Esfera;
  uf: string | null;
  municipio: string | null;
  objeto: string;
  objetoResumido: string | null;
  valorEstimado: string | null; // Decimal comes as string from API
  valorMinimo: string | null;
  valorMaximo: string | null;
  dataPublicacao: string;
  dataAbertura: string | null;
  dataEncerramento: string | null;
  dataResultado: string | null;
  segmento: string | null;
  cnae: string[];
  palavrasChave: string[];
  urlEdital: string | null;
  urlAnexos: string[];
  status: StatusLicitacao;
  situacao: string | null;
  fonteOrigem: string;
  urlOrigem: string;
  criadoEm: string;
  atualizadoEm: string;
  itens?: ItemLicitacao[];
  documentos?: Documento[];
  historico?: HistoricoStatus[];
}

export interface ItemLicitacao {
  id: string;
  numero: number;
  descricao: string;
  quantidade: string | null;
  unidade: string | null;
  valorUnitario: string | null;
  valorTotal: string | null;
  codigoCatalogo: string | null;
}

export interface Documento {
  id: string;
  tipo: string;
  nome: string;
  url: string;
  tamanho: number | null;
  formato: string | null;
}

export interface HistoricoStatus {
  id: string;
  statusAnterior: StatusLicitacao | null;
  statusNovo: StatusLicitacao;
  observacao: string | null;
  dataAlteracao: string;
}

export interface FonteDados {
  id: string;
  nome: string;
  url: string;
  tipo: string;
  esfera: Esfera;
  ativo: boolean;
  ultimaColeta: string | null;
  ultimoSucesso: string | null;
  ultimaFalha: string | null;
  totalColetados: number;
  totalErros: number;
  intervaloMinutos: number;
  healthy?: boolean;
}

export interface Usuario {
  id: string;
  email: string;
  nome: string;
  empresa: string | null;
  cnpj: string | null;
}

// ── API response types ──────────────────────────────────────────────────

export interface Pagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

export interface DashboardResumo {
  novasHoje: number;
  abertasEstaSemana: number;
  encerradasEstaSemana: number;
  volumeTotalAbertas: number;
}

export interface EstatisticaPorEstado {
  uf: string;
  count: number;
}

export interface EstatisticaPorModalidade {
  modalidade: Modalidade;
  count: number;
}

export interface Tendencia {
  date: string;
  count: number;
}

// ── Search filters ──────────────────────────────────────────────────────

export interface SearchFilters {
  q?: string;
  page?: number;
  pageSize?: number;
  esfera?: Esfera;
  uf?: string;
  municipio?: string;
  modalidade?: Modalidade;
  tipo?: TipoLicitacao;
  status?: StatusLicitacao;
  segmento?: string;
  orgao?: string;
  valorMin?: number;
  valorMax?: number;
  dataPublicacaoInicio?: string;
  dataPublicacaoFim?: string;
  dataAberturaInicio?: string;
  dataAberturaFim?: string;
  fonteOrigem?: string;
  ordenarPor?: 'dataPublicacao' | 'dataAbertura' | 'valorEstimado' | 'relevancia';
  ordem?: 'asc' | 'desc';
}

// ── Label maps ──────────────────────────────────────────────────────────

export const MODALIDADE_LABELS: Record<Modalidade, string> = {
  PREGAO_ELETRONICO: 'Pregão Eletrônico',
  PREGAO_PRESENCIAL: 'Pregão Presencial',
  CONCORRENCIA: 'Concorrência',
  CONCORRENCIA_ELETRONICA: 'Concorrência Eletrônica',
  TOMADA_DE_PRECOS: 'Tomada de Preços',
  CONVITE: 'Convite',
  CONCURSO: 'Concurso',
  LEILAO: 'Leilão',
  DIALOGO_COMPETITIVO: 'Diálogo Competitivo',
  DISPENSA: 'Dispensa',
  INEXIGIBILIDADE: 'Inexigibilidade',
  CREDENCIAMENTO: 'Credenciamento',
  RDC: 'RDC',
  OUTRA: 'Outra',
};

export const ESFERA_LABELS: Record<Esfera, string> = {
  FEDERAL: 'Federal',
  ESTADUAL: 'Estadual',
  MUNICIPAL: 'Municipal',
};

export const STATUS_LABELS: Record<StatusLicitacao, string> = {
  PUBLICADA: 'Publicada',
  ABERTA: 'Aberta',
  EM_ANDAMENTO: 'Em Andamento',
  SUSPENSA: 'Suspensa',
  ADIADA: 'Adiada',
  ENCERRADA: 'Encerrada',
  ANULADA: 'Anulada',
  REVOGADA: 'Revogada',
  DESERTA: 'Deserta',
  FRACASSADA: 'Fracassada',
  HOMOLOGADA: 'Homologada',
  ADJUDICADA: 'Adjudicada',
};

export const STATUS_COLORS: Record<StatusLicitacao, string> = {
  PUBLICADA: 'bg-blue-100 text-blue-800',
  ABERTA: 'bg-green-100 text-green-800',
  EM_ANDAMENTO: 'bg-yellow-100 text-yellow-800',
  SUSPENSA: 'bg-orange-100 text-orange-800',
  ADIADA: 'bg-orange-100 text-orange-800',
  ENCERRADA: 'bg-gray-100 text-gray-800',
  ANULADA: 'bg-red-100 text-red-800',
  REVOGADA: 'bg-red-100 text-red-800',
  DESERTA: 'bg-gray-100 text-gray-600',
  FRACASSADA: 'bg-red-50 text-red-700',
  HOMOLOGADA: 'bg-emerald-100 text-emerald-800',
  ADJUDICADA: 'bg-emerald-100 text-emerald-800',
};

export const UF_LIST = [
  'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
  'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO',
] as const;

export const UF_NAMES: Record<string, string> = {
  AC: 'Acre', AL: 'Alagoas', AP: 'Amapá', AM: 'Amazonas', BA: 'Bahia',
  CE: 'Ceará', DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás',
  MA: 'Maranhão', MT: 'Mato Grosso', MS: 'Mato Grosso do Sul',
  MG: 'Minas Gerais', PA: 'Pará', PB: 'Paraíba', PR: 'Paraná',
  PE: 'Pernambuco', PI: 'Piauí', RJ: 'Rio de Janeiro',
  RN: 'Rio Grande do Norte', RS: 'Rio Grande do Sul', RO: 'Rondônia',
  RR: 'Roraima', SC: 'Santa Catarina', SP: 'São Paulo', SE: 'Sergipe',
  TO: 'Tocantins',
};
