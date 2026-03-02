#!/usr/bin/env bash
set -euo pipefail

RELOAD_FLAG=""
WORKERS="${API_WORKERS:-1}"
if [ "${DEBUG:-false}" = "true" ] || [ "${DEBUG:-false}" = "True" ]; then
    RELOAD_FLAG="--reload --reload-dir /app/backend --reload-dir /app/ui"
    WORKERS=1
fi

uvicorn backend.src.api.main:create_app --factory \
    --host 0.0.0.0 --port 8000 --workers "$WORKERS" $RELOAD_FLAG &

streamlit run ui/app.py \
    --server.port 8501 --server.address 0.0.0.0 \
    --server.headless true &

wait -n
exit $?
