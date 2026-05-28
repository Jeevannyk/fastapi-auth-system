@echo off
setlocal

if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat

pip install -q -r requirements.txt

if not exist ".env" (
    copy /Y .env.example .env >nul
    echo Wrote .env from .env.example. Edit SECRET_KEY before running in production.
)

alembic upgrade head
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
