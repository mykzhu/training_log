#!/usr/bin/env sh
set -eu

export DB_PATH="${DB_PATH:-/data/training.db}"
export PORT="${PORT:-8000}"

mkdir -p "$(dirname "${DB_PATH}")"

echo "Starting Training Log"
echo "Database path: ${DB_PATH}"
echo "Listening on 0.0.0.0:${PORT}"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
