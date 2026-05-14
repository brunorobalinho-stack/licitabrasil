/**
 * Data fix do finding H1 (PR #2): normaliza todos os emails de Usuario para
 * trim + lowercase, alinhando o banco com o `emailField` do auth.ts.
 *
 * Seguro por construcao: detecta colisoes ANTES de escrever qualquer coisa.
 * Se duas contas so diferem por caixa/espaco (ex.: "Joao@x.com" e
 * "joao@x.com"), o `UPDATE ... SET email = LOWER(TRIM(email))` direto
 * quebraria a unique constraint de email no meio da transacao -- e qual
 * linha falha primeiro e nao-deterministico. Aqui o script recusa rodar e
 * imprime cada colisao com dados suficientes (id, criadoEm, contagem de
 * favoritos/alertas/buscas) para um humano decidir qual conta manter.
 * Nenhuma linha e tocada enquanto houver colisao.
 *
 * Substitui o trecho de SQL manual que vinha na descricao do PR #2.
 *
 * Uso:
 *   npm run prisma:normalize-emails -- --dry-run   # so relata, nao escreve
 *   npm run prisma:normalize-emails                # aplica se nao houver colisao
 */
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

/** Mesma normalizacao do `emailField` em src/api/routes/auth.ts. */
const normalize = (email: string): string => email.trim().toLowerCase();

async function main(): Promise<void> {
  const dryRun = process.argv.includes('--dry-run');
  console.log(`Normalizando emails de Usuario${dryRun ? ' (dry-run)' : ''}…`);

  const usuarios = await prisma.usuario.findMany({
    select: {
      id: true,
      email: true,
      criadoEm: true,
      _count: { select: { favoritos: true, alertas: true, buscasSalvas: true } },
    },
  });
  console.log(`  ${usuarios.length} usuario(s) no banco.`);

  // Agrupa por email normalizado para enxergar colisoes.
  const grupos = new Map<string, typeof usuarios>();
  for (const u of usuarios) {
    const chave = normalize(u.email);
    const grupo = grupos.get(chave) ?? [];
    grupo.push(u);
    grupos.set(chave, grupo);
  }

  // Colisao = email normalizado compartilhado por 2+ contas distintas.
  const colisoes = [...grupos.entries()].filter(([, grupo]) => grupo.length > 1);

  if (colisoes.length > 0) {
    console.error(`\n  ABORTADO: ${colisoes.length} colisao(oes) de email detectada(s).`);
    console.error('  Resolva manualmente qual conta manter antes de rodar de novo.\n');
    for (const [chave, grupo] of colisoes) {
      console.error(`  "${chave}" -- ${grupo.length} contas:`);
      for (const u of grupo) {
        const c = u._count;
        console.error(
          `    - id=${u.id}  email="${u.email}"  criadoEm=${u.criadoEm.toISOString()}` +
            `  favoritos=${c.favoritos} alertas=${c.alertas} buscas=${c.buscasSalvas}`,
        );
      }
    }
    process.exitCode = 1;
    return;
  }

  // Sem colisao: so as linhas onde a normalizacao muda algo de fato.
  const aMudar = usuarios.filter((u) => u.email !== normalize(u.email));
  if (aMudar.length === 0) {
    console.log('  Nada a fazer: todos os emails ja estao normalizados.');
    return;
  }
  console.log(`  ${aMudar.length} email(s) a normalizar:`);
  for (const u of aMudar) {
    console.log(`    "${u.email}" -> "${normalize(u.email)}"`);
  }

  if (dryRun) {
    console.log('\n  dry-run: nenhuma linha foi alterada.');
    return;
  }

  // Tudo numa transacao: ou normaliza todos, ou nenhum.
  await prisma.$transaction(
    aMudar.map((u) =>
      prisma.usuario.update({
        where: { id: u.id },
        data: { email: normalize(u.email) },
      }),
    ),
  );
  console.log(`\n  OK: ${aMudar.length} email(s) normalizado(s).`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
