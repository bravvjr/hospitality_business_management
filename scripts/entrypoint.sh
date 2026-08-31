#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

echo "[entrypoint] Starting application..."
exec "$@"
