#!/usr/bin/env bash
set -euo pipefail

HA_HOST="${HA_HOST:-homeassistant.local}"
HA_USER="${HA_USER:-root}"
HA_PORT="${HA_PORT:-22}"
REMOTE_ADDONS_DIR="${REMOTE_ADDONS_DIR:-/addons}"
ADDON_SLUG="${ADDON_SLUG:-training_log}"
REMOTE_DIR="${REMOTE_ADDONS_DIR}/${ADDON_SLUG}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

SSH_TARGET="${HA_USER}@${HA_HOST}"
SSH_CMD=(ssh -p "${HA_PORT}" "${SSH_TARGET}")

EXCLUDES=(
  --exclude .git
  --exclude .venv
  --exclude venv
  --exclude __pycache__
  --exclude .pytest_cache
  --exclude .env
  --exclude data
  --exclude '*.db'
  --exclude '*.db-shm'
  --exclude '*.db-wal'
)

echo "Deploying Training Log Home Assistant app"
echo "Source: ${PROJECT_DIR}"
echo "Target: ${SSH_TARGET}:${REMOTE_DIR}"

"${SSH_CMD[@]}" "mkdir -p '${REMOTE_DIR}'"

if command -v rsync >/dev/null 2>&1; then
  rsync -av --delete \
    -e "ssh -p ${HA_PORT}" \
    "${EXCLUDES[@]}" \
    "${PROJECT_DIR}/" \
    "${SSH_TARGET}:${REMOTE_DIR}/"
else
  echo "rsync is not installed locally; falling back to tar over ssh"
  (
    cd "${PROJECT_DIR}"
    tar \
      --exclude='.git' \
      --exclude='.venv' \
      --exclude='venv' \
      --exclude='__pycache__' \
      --exclude='.pytest_cache' \
      --exclude='.env' \
      --exclude='data' \
      --exclude='*.db' \
      --exclude='*.db-shm' \
      --exclude='*.db-wal' \
      -czf - .
  ) | "${SSH_CMD[@]}" "rm -rf '${REMOTE_DIR}'/* && mkdir -p '${REMOTE_DIR}' && tar -xzf - -C '${REMOTE_DIR}'"
fi

"${SSH_CMD[@]}" "chmod +x '${REMOTE_DIR}/run.sh' '${REMOTE_DIR}/scripts/deploy-ha-addon.sh' 2>/dev/null || true"

"${SSH_CMD[@]}" "if command -v ha >/dev/null 2>&1; then ha addons reload >/dev/null 2>&1 || ha supervisor reload >/dev/null 2>&1 || true; fi"

cat <<EOF

Deploy finished.

Next steps in Home Assistant:
1. Settings -> Apps -> App store
2. Open menu -> Check for updates / reload local apps
3. Open Local apps
4. Install or rebuild "Training Log"
5. Start it and open Web UI
