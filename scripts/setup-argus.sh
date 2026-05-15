#!/usr/bin/env bash
# scripts/setup-argus.sh
#
# Bootstrap completo do monitoramento Argus no LicitaBrasil:
#   1. Garante .venv e dependências
#   2. Faz primeira sincronização dos scrapers que funcionam
#   3. Instala launchd plist (agendamento diário)
#   4. Cria diretórios de log
#
# Uso:
#   chmod +x scripts/setup-argus.sh
#   ./scripts/setup-argus.sh           # bootstrap completo
#   ./scripts/setup-argus.sh --sync    # só ressincroniza (sem mexer launchd)
#   ./scripts/setup-argus.sh --launchd # só (re)instala launchd
#   ./scripts/setup-argus.sh --unload  # desinstala o launchd

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PROJECT_ROOT}/.venv"
PY="${VENV}/bin/python"
LICITABRASIL="${VENV}/bin/licitabrasil"
LOG_DIR="${HOME}/Library/Logs/licitabrasil"
PLIST_NAME="com.argus.licitabrasil"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_NAME}.plist"
PLIST_SOURCE="${PROJECT_ROOT}/scripts/${PLIST_NAME}.plist"

ACTION="${1:-all}"

# ── helpers ──

log() {
  echo "[$(date '+%H:%M:%S')] $*"
}

ensure_venv() {
  if [[ ! -x "${PY}" ]]; then
    log "Criando .venv em ${VENV}"
    python3 -m venv "${VENV}"
  fi
  log "Atualizando pip e instalando licitabrasil em modo editável..."
  "${VENV}/bin/pip" install --quiet --upgrade pip
  "${VENV}/bin/pip" install --quiet -e "${PROJECT_ROOT}"
}

ensure_log_dir() {
  mkdir -p "${LOG_DIR}"
  log "Diretório de logs: ${LOG_DIR}"
}

run_initial_sync() {
  log "Iniciando primeira sincronização dos scrapers ativos..."
  # Lista enabled, exclui os que precisam de Playwright (peintegrado) ou estão disabled (fiemg)
  for scraper in cbtu jfpe maceio central-natal portalcompras-ce prefeitura-sp; do
    log "→ ${scraper}"
    if ! "${LICITABRASIL}" scrape run "${scraper}" 2>&1 | tee -a "${LOG_DIR}/setup.log"; then
      log "⚠ ${scraper} falhou — seguindo"
    fi
  done
  log "Sync inicial finalizada. Estatísticas:"
  "${LICITABRASIL}" scrape stats
}

install_launchd() {
  if [[ ! -f "${PLIST_SOURCE}" ]]; then
    log "ERRO: plist não encontrado em ${PLIST_SOURCE}"
    exit 1
  fi

  log "Renderizando plist com paths do usuário..."
  mkdir -p "${HOME}/Library/LaunchAgents"
  sed \
    -e "s|@@PROJECT_ROOT@@|${PROJECT_ROOT}|g" \
    -e "s|@@LICITABRASIL@@|${LICITABRASIL}|g" \
    -e "s|@@LOG_DIR@@|${LOG_DIR}|g" \
    -e "s|@@HOME@@|${HOME}|g" \
    "${PLIST_SOURCE}" > "${PLIST_PATH}"

  # Descarrega versão anterior (se existir) antes de subir nova
  launchctl unload "${PLIST_PATH}" 2>/dev/null || true
  launchctl load -w "${PLIST_PATH}"
  log "✓ launchd carregado: ${PLIST_PATH}"
  log "  Próximas execuções: dias úteis às 06:00 (scrape) e 07:33 (briefing)"
}

uninstall_launchd() {
  if [[ -f "${PLIST_PATH}" ]]; then
    launchctl unload "${PLIST_PATH}" 2>/dev/null || true
    rm -f "${PLIST_PATH}"
    log "✓ launchd desinstalado"
  else
    log "Nada para desinstalar (plist não encontrado em ${PLIST_PATH})"
  fi
}

# ── dispatch ──

case "${ACTION}" in
  all)
    ensure_venv
    ensure_log_dir
    run_initial_sync
    install_launchd
    log "✅ Setup completo. Logs em ${LOG_DIR}"
    ;;
  --sync)
    ensure_venv
    ensure_log_dir
    run_initial_sync
    ;;
  --launchd)
    ensure_log_dir
    install_launchd
    ;;
  --unload)
    uninstall_launchd
    ;;
  -h|--help|help)
    grep '^#' "$0" | head -25 | sed 's/^# \?//'
    ;;
  *)
    echo "Ação desconhecida: ${ACTION}. Use --help."
    exit 1
    ;;
esac
