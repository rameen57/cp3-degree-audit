#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

if ! .venv/bin/python -c "import streamlit, rdflib, mcp, google.genai, dotenv" >/dev/null 2>&1; then
    echo "Installing requirements. This happens only on the first run..."
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
    cp .env.example .env
fi

exec .venv/bin/python -m streamlit run app/app.py "$@"
