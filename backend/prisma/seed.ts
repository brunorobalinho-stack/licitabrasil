import { PrismaClient, Modalidade, Esfera, StatusLicitacao, TipoLicitacao } from '@prisma/client';
import bcrypt from 'bcryptjs';
import { createHash } from 'crypto';

const prisma = new PrismaClient();

function hash(str: string): string {
  return createHash('sha256').update(str).digest('hex');
}

async function main() {
  console.log('Seeding LicitaBrasil database…');

  // ── Demo user ──────────────────────────────────────────────────────────
  const senha = await bcrypt.hash('123456', 10);
  const user = await prisma.usuario.upsert({
    where: { email: 'demo@licitabrasil.com.br' },
    update: {},
    create: {
      email: 'demo@licitabrasil.com.br',
      nome: 'Usuário Demo',
      empresa: 'Empresa Demo LTDA',
      cnpj: '00.000.000/0001-00',
      senha,
    },
  });
  console.log(`  User: ${user.email}`);

  // ── Data sources ───────────────────────────────────────────────────────
  const fontes = [
    { nome: 'PNCP', url: 'https://pncp.gov.br', tipo: 'API', esfera: Esfera.FEDERAL, intervaloMinutos: 30 },
    { nome: 'QUERIDO_DIARIO', url: 'https://queridodiario.ok.org.br', tipo: 'API', esfera: Esfera.MUNICIPAL, intervaloMinutos: 360 },
    { nome: 'COMPRASNET', url: 'https://www.gov.br/compras', tipo: 'SCRAPING', esfera: Esfera.FEDERAL, intervaloMinutos: 60 },
    { nome: 'DOU', url: 'https://www.in.gov.br/web/dou', tipo: 'SCRAPING', esfera: Esfera.FEDERAL, intervaloMinutos: 120 },
    { nome: 'BEC_SP', url: 'https://www.bec.sp.gov.br', tipo: 'SCRAPING', esfera: Esfera.ESTADUAL, intervaloMinutos: 120 },
    { nome: 'LICITACOES_E', url: 'https://www.licitacoes-e.com.br', tipo: 'SCRAPING', esfera: Esfera.FEDERAL, intervaloMinutos: 60 },
  ];

  for (const f of fontes) {
    await prisma.fonteDados.upsert({
      where: { nome: f.nome },
      update: {},
      create: { ...f, ativo: true },
    });
  }
  console.log(`  Fontes: ${fontes.length}`);

  // ── Sample licitacoes ──────────────────────────────────────────────────
  const samples = [
    {
      numeroEdital: '001/2026',
      numeroProcesso: '23456.000123/2026-01',
      modalidade: Modalidade.PREGAO_ELETRONICO,
      tipo: TipoLicitacao.SERVICO,
      orgao: 'Ministério da Saúde',
      orgaoSigla: 'MS',
      esfera: Esfera.FEDERAL,
      uf: 'DF',
      municipio: 'Brasília',
      objeto: 'Contratação de serviços de limpeza e conservação predial para as unidades do Ministério da Saúde em Brasília/DF',
      valorEstimado: 2450000,
      dataPublicacao: new Date('2026-02-15'),
      dataAbertura: new Date('2026-03-15T10:00:00'),
      dataEncerramento: new Date('2026-03-15T18:00:00'),
      status: StatusLicitacao.ABERTA,
      fonteOrigem: 'PNCP',
      urlOrigem: 'https://pncp.gov.br/app/editais/00394544000121-1-000001-2026',
    },
    {
      numeroEdital: '045/2026',
      modalidade: Modalidade.PREGAO_ELETRONICO,
      tipo: TipoLicitacao.COMPRA,
      orgao: 'CBTU - Companhia Brasileira de Trens Urbanos',
      orgaoSigla: 'CBTU',
      esfera: Esfera.FEDERAL,
      uf: 'PE',
      municipio: 'Recife',
      objeto: 'Aquisição de material de informática: computadores, monitores, teclados e mouses para modernização do parque tecnológico',
      valorEstimado: 890000,
      dataPublicacao: new Date('2026-02-20'),
      dataAbertura: new Date('2026-03-10T09:00:00'),
      status: StatusLicitacao.ABERTA,
      fonteOrigem: 'PNCP',
      urlOrigem: 'https://pncp.gov.br/app/editais/example-cbtu',
    },
    {
      numeroEdital: '012/2026',
      modalidade: Modalidade.CONCORRENCIA_ELETRONICA,
      tipo: TipoLicitacao.OBRA,
      orgao: 'Prefeitura Municipal de São Paulo',
      orgaoSigla: 'PMSP',
      esfera: Esfera.MUNICIPAL,
      uf: 'SP',
      municipio: 'São Paulo',
      objeto: 'Reforma e ampliação da Escola Municipal Professor João da Silva, incluindo adequação de acessibilidade e instalações elétricas',
      valorEstimado: 5200000,
      dataPublicacao: new Date('2026-02-10'),
      dataAbertura: new Date('2026-03-25T14:00:00'),
      status: StatusLicitacao.PUBLICADA,
      fonteOrigem: 'QUERIDO_DIARIO',
      urlOrigem: 'https://queridodiario.ok.org.br/sp/3550308',
    },
    {
      numeroEdital: '008/2026',
      modalidade: Modalidade.DISPENSA,
      tipo: TipoLicitacao.COMPRA,
      orgao: 'Governo do Estado de Minas Gerais',
      orgaoSigla: 'MG',
      esfera: Esfera.ESTADUAL,
      uf: 'MG',
      municipio: 'Belo Horizonte',
      objeto: 'Aquisição emergencial de medicamentos e insumos hospitalares para a rede estadual de saúde',
      valorEstimado: 340000,
      dataPublicacao: new Date('2026-02-25'),
      dataAbertura: new Date('2026-03-05T08:00:00'),
      status: StatusLicitacao.ABERTA,
      fonteOrigem: 'COMPRASNET',
      urlOrigem: 'https://www.compras.mg.gov.br/example',
    },
    {
      numeroEdital: '003/2026',
      modalidade: Modalidade.PREGAO_ELETRONICO,
      tipo: TipoLicitacao.SERVICO,
      orgao: 'Tribunal Regional Federal da 4ª Região',
      orgaoSigla: 'TRF4',
      esfera: Esfera.FEDERAL,
      uf: 'RS',
      municipio: 'Porto Alegre',
      objeto: 'Contratação de empresa especializada em segurança patrimonial e vigilância para os prédios do TRF4',
      valorEstimado: 1800000,
      dataPublicacao: new Date('2026-02-18'),
      dataAbertura: new Date('2026-03-20T10:00:00'),
      dataEncerramento: new Date('2026-03-20T17:00:00'),
      status: StatusLicitacao.ABERTA,
      fonteOrigem: 'PNCP',
      urlOrigem: 'https://pncp.gov.br/app/editais/example-trf4',
    },
    {
      modalidade: Modalidade.TOMADA_DE_PRECOS,
      tipo: TipoLicitacao.SERVICO_ENGENHARIA,
      orgao: 'Prefeitura Municipal de Curitiba',
      orgaoSigla: 'PMC',
      esfera: Esfera.MUNICIPAL,
      uf: 'PR',
      municipio: 'Curitiba',
      objeto: 'Elaboração de projetos de engenharia para drenagem pluvial do bairro Cajuru, incluindo estudos hidrológicos e topográficos',
      valorEstimado: 750000,
      dataPublicacao: new Date('2026-02-22'),
      dataAbertura: new Date('2026-03-28T09:00:00'),
      status: StatusLicitacao.PUBLICADA,
      fonteOrigem: 'QUERIDO_DIARIO',
      urlOrigem: 'https://queridodiario.ok.org.br/pr/4106902',
    },
    {
      numeroEdital: '019/2026',
      modalidade: Modalidade.PREGAO_ELETRONICO,
      tipo: TipoLicitacao.SERVICO,
      orgao: 'Universidade Federal do Rio de Janeiro',
      orgaoSigla: 'UFRJ',
      esfera: Esfera.FEDERAL,
      uf: 'RJ',
      municipio: 'Rio de Janeiro',
      objeto: 'Contratação de serviços de telecomunicações, incluindo links de internet dedicados e telefonia IP para os campi da UFRJ',
      valorEstimado: 3200000,
      dataPublicacao: new Date('2026-02-12'),
      dataAbertura: new Date('2026-03-08T10:00:00'),
      status: StatusLicitacao.EM_ANDAMENTO,
      fonteOrigem: 'PNCP',
      urlOrigem: 'https://pncp.gov.br/app/editais/example-ufrj',
    },
    {
      modalidade: Modalidade.INEXIGIBILIDADE,
      tipo: TipoLicitacao.SERVICO,
      orgao: 'Governo do Estado da Bahia',
      orgaoSigla: 'BA',
      esfera: Esfera.ESTADUAL,
      uf: 'BA',
      municipio: 'Salvador',
      objeto: 'Contratação de empresa detentora de exclusividade para fornecimento de licenças de software de gestão hospitalar',
      valorEstimado: 1200000,
      dataPublicacao: new Date('2026-02-24'),
      status: StatusLicitacao.PUBLICADA,
      fonteOrigem: 'DOU',
      urlOrigem: 'https://www.in.gov.br/web/dou/-/example-ba',
    },
  ];

  for (const s of samples) {
    const hashConteudo = hash(
      `${s.numeroEdital ?? ''}|${s.orgao}|${s.objeto}|${s.dataPublicacao.toISOString()}`,
    );

    await prisma.licitacao.upsert({
      where: { hashConteudo },
      update: {},
      create: {
        ...s,
        objetoResumido: s.objeto.slice(0, 200),
        palavrasChave: s.objeto
          .toLowerCase()
          .split(/\s+/)
          .filter((w) => w.length > 3)
          .slice(0, 15),
        cnae: [],
        urlAnexos: [],
        hashConteudo,
      },
    });
  }
  console.log(`  Licitações: ${samples.length}`);

  // ── Demo alert ─────────────────────────────────────────────────────────
  await prisma.alerta.create({
    data: {
      usuarioId: user.id,
      palavrasChave: ['informática', 'tecnologia', 'software', 'TI'],
      modalidades: [Modalidade.PREGAO_ELETRONICO],
      esferas: [Esfera.FEDERAL, Esfera.ESTADUAL],
      estados: [],
      municipios: [],
      segmentos: ['Tecnologia da Informação'],
      frequencia: 'DIARIO',
      canalNotificacao: ['email'],
      ativo: true,
    },
  });
  console.log('  Demo alert created');

  console.log('Seed completed!');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
