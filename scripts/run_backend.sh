#!/usr/bin/env bash
# Run the Metrics Explorer backend in the project's Python venv.
set -e
cd "$(dirname "$0")/.."
if [[ ! -d venv ]]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi
echo "Activating venv and installing dependencies..."
source venv/bin/activate
pip install -q -r requirements.txt
echo "Starting backend (uvicorn)..."
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
