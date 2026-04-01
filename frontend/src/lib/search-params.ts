/**
 * Definição dos parsers nuqs para os filtros de busca de licitações.
 * Centraliza a tipagem e serialização dos parâmetros de URL.
 */
import {
  parseAsString,
  parseAsInteger,
  parseAsFloat,
  createSerializer,
} from 'nuqs';

/**
 * Parsers tipados para cada filtro de licitação.
 * Usado com useQueryStates() nos componentes de busca.
 */
export const filtrosLicitacaoParams = {
  // Texto de busca livre
  q: parseAsString,

  // Paginação
  page: parseAsInteger.withDefault(1),
  pageSize: parseAsInteger.withDefault(20),

  // Filtros de classificação
  esfera: parseAsString,
  uf: parseAsString,
  municipio: parseAsString,
  modalidade: parseAsString,
  tipo: parseAsString,
  status: parseAsString,
  segmento: parseAsString,
  orgao: parseAsString,
  fonteOrigem: parseAsString,
  codigoUASG: parseAsString,

  // Faixa de valor estimado
  valorMin: parseAsFloat,
  valorMax: parseAsFloat,

  // Datas (formato YYYY-MM-DD como string)
  dataPublicacaoInicio: parseAsString,
  dataPublicacaoFim: parseAsString,
  dataAberturaInicio: parseAsString,
  dataAberturaFim: parseAsString,

  // Ordenação
  ordenarPor: parseAsString.withDefault('dataPublicacao'),
  ordem: parseAsString.withDefault('desc'),
};

/**
 * Serializer para gerar query strings a partir dos filtros.
 * Útil para construir URLs programaticamente (ex: links compartilháveis).
 */
export const serializarFiltros = createSerializer(filtrosLicitacaoParams);
