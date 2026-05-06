#!/bin/bash
set -e

mkdir -p data

echo "Building FAISS index..."
python ingest.py

echo "Starting server on port ${PORT:-8000}..."
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}"
