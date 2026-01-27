@echo off
echo ========================================
echo   FastAPI Auth System - Quick Start
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Check if dependencies are installed
echo Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    echo.
)

REM Initialize database if it doesn't exist
if not exist "auth.db" (
    echo Initializing database...
    python init_db.py
    echo.
)

echo ========================================
echo   Starting FastAPI Server...
echo ========================================
echo.
echo Server will be available at:
echo   - http://127.0.0.1:8000
echo   - http://localhost:8000
echo.
echo API Documentation:
echo   - http://127.0.0.1:8000/docs
echo.
echo Test Credentials:
echo   Email: test@example.com
echo   Password: password123
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
