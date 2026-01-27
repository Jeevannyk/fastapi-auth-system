#!/bin/bash

echo "========================================"
echo "  FastAPI Auth System - Quick Start"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo ""

# Check if dependencies are installed
echo "Checking dependencies..."
if ! pip show fastapi > /dev/null 2>&1; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    echo ""
fi

# Initialize database if it doesn't exist
if [ ! -f "auth.db" ]; then
    echo "Initializing database..."
    python init_db.py
    echo ""
fi

echo "========================================"
echo "  Starting FastAPI Server..."
echo "========================================"
echo ""
echo "Server will be available at:"
echo "  - http://127.0.0.1:8000"
echo "  - http://localhost:8000"
echo ""
echo "API Documentation:"
echo "  - http://127.0.0.1:8000/docs"
echo ""
echo "Test Credentials:"
echo "  Email: test@example.com"
echo "  Access Key: password123"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"
echo ""

uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
