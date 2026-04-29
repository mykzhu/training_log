#!/usr/bin/env bash
set -euo pipefail

HA_HOST="${HA_HOST:-192.168.88.88}"
HA_USER="${HA_USER:-root}"
HA_PORT="${HA_PORT:-2222}"
HA_TARGET="${HA_TARGET:-/addons/training_log}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SSH_OPTS=(-p "${HA_PORT}")

if [[ -n "${SSH_KEY:-}" ]]; then
  if [[ ! -f "${SSH_KEY}" ]]; then
    echo "ERROR: SSH_KEY must point to a private key file, not a directory."
    echo "Example: SSH_KEY=~/.ssh/ha_training"
    echo "Or omit SSH_KEY if you use password login."
    exit 1
  fi
  SSH_OPTS+=(-i "${SSH_KEY}")
fi

echo "Deploying Training Log Home Assistant app"
echo "Source: ${PROJECT_ROOT}"
echo "Target: ${HA_USER}@${HA_HOST}:${HA_TARGET}"

cd "${PROJECT_ROOT}"

tar \
  --exclude='./.git' \
  --exclude='./.venv' \
  --exclude='./venv' \
  --exclude='./__pycache__' \
  --exclude='*/__pycache__' \
  --exclude='./.pytest_cache' \
  --exclude='./node_modules' \
  --exclude='./data' \
  --exclude='./.env' \
  --exclude='./*.patch' \
  --exclude='./*.rej' \
  -czf - . | ssh "${SSH_OPTS[@]}" "${HA_USER}@${HA_HOST}" "
    set -e
    rm -rf '${HA_TARGET}'
    mkdir -p '${HA_TARGET}'
    tar -xzf - -C '${HA_TARGET}'
  "

echo "Done."
echo "Now open Home Assistant:"
echo "Settings -> Add-ons / Apps -> Add-on Store -> Local add-ons -> Training Log"
