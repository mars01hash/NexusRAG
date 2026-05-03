# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Retrieval-Augmented Generation (RAG) API and web UI that answers questions **strictly from an uploaded knowledge base** — no general knowledge, no hallucinations. Configured by default for Gemini 3 Flash with automatic fallback to local HuggingFace embeddings when OpenAI quota is unavailable.

## Common Commands

```bash
# First-time setup
python setup_env.py          # Creates .env from template
pip install -r requirements.txt

# Rebuild the FAISS index after adding/changing documents in knowledge_data/
python ingest.py

# Run the API server (http://localhost:8000)
python app.py

# Docker (includes Redis)
docker-compose up -d
docker-compose logs -f api
docker-compose down
```

**Smoke-test the running server:**
```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "your question here", "session_id": "optional-uuid"}'
```

There is no automated test suite. Functional verification is done via the `/health` endpoint and manual `curl` calls. The Swagger UI at `/docs` is also available when the server is running.

## Architecture

### Pipeline

```
Document files (PDF/DOCX/TXT/MD in knowledge_data/)
  → ingest.py   — chunks text, creates embeddings, saves faiss_index.pkl
  → retriever.py — loads faiss_index.pkl, retrieves top-k chunks, calls LLM
  → app.py       — FastAPI server, session management, exposes /ask endpoint
  → templates/index.html + static/ — browser chat UI
```

### Key Design Decisions

**Two-phase embeddings:** `ingest.py` tries OpenAI embeddings first (`text-embedding-3-small`); if unavailable it falls back to `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2`). The same fallback order applies at query time in `retriever.py` — **both phases must use the same embedding model**, or the index will be incompatible. Re-run `ingest.py` whenever changing embedding providers.

**LLM provider selection:** Controlled by `PROVIDER` env var (`gemini` / `openai` / `deepseek`). The active provider is initialized lazily in `retriever.py:get_qa_chain()`. DeepSeek uses the OpenAI-compatible SDK but routes to a different base URL.

**Anti-hallucination:** The system prompt in `retriever.py` hard-codes 7 rules forcing answers to come only from retrieved context. Temperature is fixed at `0.0`. Do not relax these without understanding the tradeoff.

**Session storage:** Redis is the primary backend (TTL 24 h). `app.py` falls back silently to an in-memory dict if Redis is unreachable — useful for local dev, but sessions are lost on restart. Session history is stored per `session_id` (UUID) and included in the `/ask` response.

**FAISS index as a file:** `faiss_index.pkl` is a serialized pickle of the LangChain FAISS wrapper. It is not regenerated automatically — any change to `knowledge_data/` requires a manual `python ingest.py` run. The current index (~480 MB) is for the Bangladesh Constitution PDF.

### Configuration

All settings are in `config.py` as a Pydantic `BaseSettings` class. Env vars map directly to fields (case-insensitive). Key tunables:

| Variable | Default | Effect |
|---|---|---|
| `PROVIDER` | `gemini` | Which LLM to use |
| `TOP_K_RESULTS` | `3` | Chunks retrieved per query |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `100` | Only affect re-ingestion |
| `TEMPERATURE` | `0.0` | LLM randomness |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Server binding |

Copy `.env.sample` to `.env` and fill in at least one provider API key before running.

### Missing Dependency

`langchain-google-genai` is **not listed in `requirements.txt`** but is required when `PROVIDER=gemini`. Install it manually or add it to the file:
```bash
pip install langchain-google-genai
```
