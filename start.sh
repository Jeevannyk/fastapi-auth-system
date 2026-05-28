#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
# shellcheck source=/dev/null
. .venv/bin/activate

pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Wrote .env from .env.example. Edit SECRET_KEY before running in production."
fi

alembic upgrade head

exec uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
