#!/usr/bin/env bash
set -euo pipefail

uvicorn backend.src.api.main:create_app --factory \
    --host 0.0.0.0 --port 8000 --workers "${API_WORKERS:-1}" &

streamlit run ui/app.py \
    --server.port 8501 --server.address 0.0.0.0 \
    --server.headless true &

wait -n
exit $?
