#!/bin/bash
# ==============================================================
#  AI Developer Agent — Quick Start Script
# ==============================================================

set -e

echo ""
echo "============================================================"
echo "  🤖 AI Developer Agent — Setup & Launch"
echo "============================================================"
echo ""

# 1. Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt
echo ""

# 2. Run ingestion pipeline
echo "🔄 Running ingestion pipeline..."
python backend/ingest.py
echo ""

# 3. Start the FastAPI server
echo "🚀 Starting server on http://localhost:8000 ..."
echo "   Open frontend/index.html in your browser to use the UI."
echo ""
uvicorn backend.main:app --reload --port 8000
