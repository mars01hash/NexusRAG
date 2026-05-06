# NexusRAG

NexusRAG is a Retrieval-Augmented Generation (RAG) chatbot that answers questions **strictly from an uploaded knowledge base** — no hallucinations, no general knowledge. Supports PDF, DOCX, TXT, MD, and web URLs. Ships with a full chat UI, JWT authentication, conversation memory, and a live knowledge-base manager.

---

## Features

| Category | What's included |
|---|---|
| **Core RAG** | FAISS vector search, anti-hallucination system prompt, `temperature=0.0`, source citations, confidence scores |
| **Conversation memory** | Last 5 turns of each session are injected into the LLM prompt for multi-turn context |
| **Multi-format KB** | Ingest PDF, DOCX, TXT, MD from a folder **or** any public web URL |
| **Live KB management** | Upload files, delete files, fetch URLs, rebuild index — all from the UI or API, no restart needed |
| **Authentication** | JWT bearer tokens, two roles (`admin` / `user`), credentials stored in `data/users.json` |
| **Multi-provider LLM** | Google Gemini (default), OpenAI, DeepSeek — switch with one env var |
| **Embeddings fallback** | Tries OpenAI embeddings first; falls back to local HuggingFace (`paraphrase-multilingual-MiniLM-L12-v2`) automatically |
| **Session storage** | Redis (primary, 24 h TTL) with automatic in-memory fallback |
| **API docs** | Swagger UI at `/docs`, ReDoc at `/redoc` |
| **Logging** | Structured Python logging throughout; level controlled by `LOG_LEVEL` |
| **Docker** | `docker-compose.yml` includes the API and Redis |

---

## Architecture

```
Documents (PDF / DOCX / TXT / MD / Web URLs)
  │
  ▼
ingest.py — chunk → embed → FAISS index (data/faiss_index.pkl)
  │
  ▼
retriever.py — similarity search → inject context + history → LLM
  │
  ▼
app.py (FastAPI) — auth, sessions, REST endpoints
  │
  ├── /auth/login         POST  public
  ├── /ask                POST  authenticated
  ├── /files              GET   authenticated
  ├── /upload             POST  admin
  ├── /ingest-url         POST  admin
  ├── /reindex            POST  admin
  └── /docs               GET   public (Swagger)
  │
  ▼
templates/index.html + static/ — browser chat UI
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- An API key for at least one supported LLM provider (see table below)

### 1. Install

```bash
git clone <your-repo-url>
cd NexusRAG

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Gemini provider requires one extra package:
pip install langchain-google-genai
```

### 2. Configure

```bash
python setup_env.py   # creates .env from template
```

Edit `.env` and set at least one provider key:

```env
# LLM provider: gemini | openai | deepseek
PROVIDER=gemini
GEMINI_API_KEY=your_key_here

# Optional — leave blank to use local HuggingFace embeddings
OPENAI_API_KEY=

# Auth — change JWT_SECRET before any internet-facing deployment
JWT_SECRET=change-me-in-production
JWT_EXPIRY_HOURS=24

# Redis (optional — falls back to in-memory if unavailable)
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3. Add documents and build the index

```bash
# Drop files into knowledge_data/ then run:
python ingest.py
```

The index is saved to `data/faiss_index.pkl`. Re-run whenever you change the documents, **or** use the `/reindex` API / the Rebuild button in the UI.

### 4. Run

```bash
python app.py
# Server starts at http://localhost:8000
```

Open `http://localhost:8000` in your browser. You'll see the login screen.

**Default credentials**

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin — full access |
| `user` | `user123` | User — chat only |

Credentials are stored in `data/users.json` (created on first run). Edit that file to change passwords or add users; passwords must be bcrypt-hashed.

---

## Docker

```bash
docker-compose up -d        # starts API + Redis
docker-compose logs -f api  # tail logs
docker-compose down
```

---

## Deploy to Render

NexusRAG supports one-click deployment to [Render](https://render.com) using the included `render.yaml`. The FAISS index is **pre-built locally** and committed to the repo so the server starts instantly without any rebuild delay on Render.

### How it works

- The `data/faiss_index/` directory is committed to git and baked into the Docker image
- On startup, Render just runs `uvicorn` — no index building, no model loading delay
- The port opens in seconds, avoiding Render's "no open ports detected" timeout

### Steps

**1. Build the index locally**

```bash
pip install -r requirements.txt
python ingest.py
```

This generates `data/faiss_index/` from your files in `knowledge_data/`.

**2. Commit the index and push to GitHub**

```bash
git add data/faiss_index/ knowledge_data/
git commit -m "add pre-built faiss index and knowledge base"
git push
```

**3. Create a new Blueprint on Render**

- Go to [render.com](https://render.com) → **New** → **Blueprint**
- Connect your GitHub repository
- Render will detect `render.yaml` and provision:
  - A **web service** running the Docker container
  - A **free Redis** instance for session storage

**4. Set your API key**

In the Render dashboard → your `nexusrag` service → **Environment**:

| Key | Value |
|---|---|
| `GEMINI_API_KEY` | Your Google Gemini API key |

> If using a different provider, also set `PROVIDER=openai` or `PROVIDER=deepseek` and the corresponding key (`OPENAI_API_KEY` / `DEEPSEEK_API_KEY`).

**5. Deploy**

Click **Deploy**. Render builds the Docker image and starts the server. Your app will be live at `https://nexusrag.onrender.com` (or your custom domain).

### Environment Variables on Render

| Variable | Required | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Yes (if using Gemini) | Set manually in dashboard |
| `PROVIDER` | No | Defaults to `gemini` |
| `JWT_SECRET` | No | Auto-generated by Render |
| `REDIS_HOST` / `REDIS_PORT` | No | Auto-linked from Redis service |
| `OPENAI_API_KEY` | Only for OpenAI embeddings | Optional — falls back to HuggingFace |

### Updating the knowledge base

Add new files to `knowledge_data/`, rebuild the index locally, commit, and push. Render will redeploy automatically.

```bash
cp new-document.pdf knowledge_data/
python ingest.py
git add data/faiss_index/ knowledge_data/new-document.pdf
git commit -m "add new document to knowledge base"
git push
```

---

## Authentication

All endpoints except `/`, `/health`, `/api/health`, and `/auth/login` require a valid JWT.

**Login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Response:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "username": "admin",
  "role": "admin"
}
```

**Use the token on subsequent requests:**
```bash
curl -H "Authorization: Bearer <jwt>" http://localhost:8000/files
```

**Verify current user:**
```bash
curl -H "Authorization: Bearer <jwt>" http://localhost:8000/auth/me
```

---

## API Reference

### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | None | Get JWT token |
| `GET` | `/auth/me` | User | Current user info |

### Chat

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/ask` | User | Ask a question |
| `GET` | `/sessions/{id}` | User | Get session history |
| `DELETE` | `/sessions/{id}` | User | Delete a session |

**Ask request:**
```json
{
  "question": "What does article 7 say?",
  "session_id": "optional-uuid-for-multi-turn"
}
```

**Ask response:**
```json
{
  "answer": "Article 7 states that...",
  "session_id": "uuid",
  "sources": [
    { "content_preview": "...", "metadata": {} }
  ],
  "confidence": 0.85,
  "timestamp": "2025-05-03T10:00:00"
}
```

### Knowledge Base (admin only)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/files` | User | List indexed files |
| `POST` | `/upload` | Admin | Upload a document |
| `DELETE` | `/files/{filename}` | Admin | Delete a document |
| `POST` | `/ingest-url` | Admin | Fetch a web page into KB |
| `POST` | `/reindex` | Admin | Rebuild FAISS index |
| `GET` | `/reindex/status` | Admin | Check rebuild progress |

**Ingest a URL:**
```bash
curl -X POST http://localhost:8000/ingest-url \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/page"}'
```

After adding files or URLs, call `/reindex` to rebuild the index (or click **Rebuild Knowledge Base** in the sidebar).

### System

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Full health check (index + Redis) |
| `GET` | `/api/health` | None | Lightweight ping |
| `GET` | `/docs` | None | Swagger UI |
| `GET` | `/redoc` | None | ReDoc |

---

## Configuration Reference

All settings are in `config.py` as Pydantic `BaseSettings`; env vars override defaults.

| Variable | Default | Description |
|---|---|---|
| `PROVIDER` | `gemini` | LLM provider: `gemini` / `openai` / `deepseek` |
| `GEMINI_API_KEY` | — | Google Gemini key |
| `GEMINI_MODEL` | `gemini-3-flash-preview` | Gemini model ID |
| `OPENAI_API_KEY` | — | OpenAI key (also used for embeddings) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model ID |
| `DEEPSEEK_API_KEY` | — | DeepSeek key |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek model ID |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `TEMPERATURE` | `0.0` | LLM temperature (keep at 0 for factual answers) |
| `TOP_K_RESULTS` | `3` | Chunks retrieved per query |
| `CHUNK_SIZE` | `1000` | Characters per chunk (affects re-ingestion only) |
| `CHUNK_OVERLAP` | `100` | Overlap between chunks |
| `DATA_DIR` | `knowledge_data` | Folder scanned by `ingest.py` |
| `INDEX_FILE` | `data/faiss_index.pkl` | FAISS index path |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | — | Redis password (optional) |
| `JWT_SECRET` | `change-me-…` | Secret used to sign JWTs — **change this** |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRY_HOURS` | `24` | Token lifetime in hours |
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | Bind port |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Project Structure

```
NexusRAG/
├── app.py                  # FastAPI server — endpoints, auth, sessions
├── auth.py                 # JWT logic, user loading, role guards
├── retriever.py            # RAG chain, vector search, answer generation
├── ingest.py               # Document + URL ingestion, FAISS index builder
├── config.py               # Pydantic settings (reads .env)
├── setup_env.py            # First-run helper: creates .env from template
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # API + Redis stack
├── Dockerfile
├── .env.sample             # Environment variable template
├── templates/
│   └── index.html          # Chat UI (login modal, sidebar, chat)
├── static/
│   ├── style.css
│   └── script.js
├── knowledge_data/         # Drop source documents here
├── data/
│   ├── faiss_index.pkl     # Generated by ingest.py (not committed)
│   └── users.json          # User credentials (generated on first run)
├── files/
│   ├── images/             # Screenshots and diagrams
│   ├── DEPLOYMENT.md
│   ├── QUICKSTART.md
│   └── REDIS_SETUP.md
├── logs/                   # Runtime logs and output files
└── tests/                  # Manual test and utility scripts
```

---

## Security Notes

- **Change `JWT_SECRET`** before any internet-facing deployment. The default value is public.
- **CORS** is currently `allow_origins=["*"]`. Restrict this to your frontend origin in production.
- `data/users.json` stores bcrypt-hashed passwords and should not be committed (`data/` is in `.gitignore`).
- `data/faiss_index.pkl` is a pickle file — only load indexes you generated yourself.

---

## Troubleshooting

**Index not found on startup**
```bash
python ingest.py   # build the index first
```

**`langchain_google_genai` not found**
```bash
pip install langchain-google-genai
```

**Embeddings mismatch after switching providers**
The ingest and query phases must use the same embedding model. After changing the embedding source, always re-run `ingest.py`.

**Token expired in browser**
The page automatically redirects to the login screen on a 401. Re-login to continue.

**Redis not connecting**
The server falls back to in-memory session storage automatically. Sessions will be lost on restart but the chat still works.
