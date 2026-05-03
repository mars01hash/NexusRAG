"""
FastAPI backend for RAG AI Decision Assistant
Provides REST API endpoints for question-answering with session management
"""
import asyncio
import json
import logging
import re
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

# Set ProactorEventLoop on Windows for subprocess support
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from auth import TokenUser, authenticate_user, create_access_token, get_current_user, require_admin
from config import settings
from retriever import get_answer

# Redis import with fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis not available. Install with: pip install redis")

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="NexusRAG API",
    description="NexusRAG — High-performance AI assistant powered by custom knowledge",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Redis / session storage ──────────────────────────────────────────────────

_redis_client = None
_redis_unavailable = False
_fallback_sessions: Dict[str, Dict] = {}
SESSION_TTL = 86400  # 24 hours


def get_redis_client():
    global _redis_client, _redis_unavailable
    if not REDIS_AVAILABLE or _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password if settings.redis_password else None,
            ssl=settings.redis_ssl,
            decode_responses=settings.redis_decode_responses,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client.ping()
        logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Using in-memory storage.")
        _redis_client = None
        _redis_unavailable = True
        return None


def get_session(session_id: str) -> Optional[Dict]:
    rc = get_redis_client()
    if rc:
        try:
            data = rc.get(f"session:{session_id}")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Redis read error: {e}")
    return _fallback_sessions.get(session_id)


def save_session(session_id: str, session_data: Dict) -> None:
    rc = get_redis_client()
    if rc:
        try:
            rc.setex(f"session:{session_id}", SESSION_TTL, json.dumps(session_data))
            return
        except Exception as e:
            logger.error(f"Redis write error: {e}")
    _fallback_sessions[session_id] = session_data


def delete_session(session_id: str) -> bool:
    rc = get_redis_client()
    if rc:
        try:
            return rc.delete(f"session:{session_id}") > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
    if session_id in _fallback_sessions:
        del _fallback_sessions[session_id]
        return True
    return False


# ── Pydantic models ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str


class QueryRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="User identifier")
    question: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, description="Session identifier")


class QueryResponse(BaseModel):
    answer: str
    session_id: str
    sources: list
    confidence: float
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    message: str
    timestamp: str


class IngestUrlRequest(BaseModel):
    url: str = Field(..., description="HTTP/HTTPS URL to fetch and add to the knowledge base")


# ── Auth endpoints ───────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=LoginResponse, tags=["auth"])
async def login(body: LoginRequest):
    """Authenticate and receive a JWT bearer token."""
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(user["username"], user["role"])
    logger.info(f"User '{user['username']}' logged in")
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        username=user["username"],
        role=user["role"],
    )


@app.get("/auth/me", tags=["auth"])
async def me(current_user: TokenUser = Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    return {"username": current_user.username, "role": current_user.role}


# ── Public endpoints ─────────────────────────────────────────────────────────

@app.get("/")
async def home():
    return FileResponse("templates/index.html")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        from retriever import load_vector_store
        load_vector_store()
        rc = get_redis_client()
        if rc:
            try:
                rc.ping()
                redis_status = "connected"
            except Exception as e:
                redis_status = f"disconnected: {e} (using fallback)"
        else:
            redis_status = "not configured (using in-memory)"
        return {
            "status": "healthy",
            "message": f"System is operational. Knowledge base loaded. Redis: {redis_status}",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"System not ready: {e}")


@app.get("/api/health", response_model=HealthResponse)
async def health_check_api():
    return {
        "status": "healthy",
        "message": "RAG AI Decision Assistant API is running",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Authenticated endpoints ──────────────────────────────────────────────────

def _get_or_create_session(session_id: Optional[str]) -> str:
    if session_id:
        if get_session(session_id):
            return session_id
    new_id = str(uuid.uuid4())
    save_session(new_id, {"created_at": datetime.utcnow().isoformat(), "messages": []})
    return new_id


@app.post("/ask", response_model=QueryResponse)
async def ask(
    query: QueryRequest,
    current_user: TokenUser = Depends(get_current_user),
):
    """Ask a question; answers come exclusively from the knowledge base."""
    if not query.question.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty")

    session_id = _get_or_create_session(query.session_id)

    session_data = get_session(session_id) or {
        "created_at": datetime.utcnow().isoformat(),
        "messages": [],
    }
    chat_history = session_data.get("messages", [])

    logger.info(f"User '{current_user.username}' | session {session_id} | question: {query.question[:80]}")
    result = get_answer(
        query.question,
        chat_history=chat_history,
        user_id=current_user.username,
    )

    session_data["messages"].append({
        "question": query.question,
        "answer": result["answer"],
        "timestamp": datetime.utcnow().isoformat(),
    })
    session_data["updated_at"] = datetime.utcnow().isoformat()
    save_session(session_id, session_data)

    return QueryResponse(
        answer=result["answer"],
        session_id=session_id,
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/sessions/{session_id}")
async def get_session_endpoint(
    session_id: str,
    _: TokenUser = Depends(get_current_user),
):
    data = get_session(session_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return data


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(
    session_id: str,
    _: TokenUser = Depends(get_current_user),
):
    if delete_session(session_id):
        return {"message": "Session deleted successfully"}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@app.get("/files")
async def list_files(_: TokenUser = Depends(get_current_user)):
    data_dir = Path(settings.data_dir)
    files = []
    if data_dir.exists():
        for f in sorted(data_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file() and f.suffix.lower() in _ALLOWED_EXTS:
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "type": f.suffix.lower().lstrip("."),
                })
    return {"files": files}


# ── Admin-only endpoints ─────────────────────────────────────────────────────

_ALLOWED_EXTS = {".pdf", ".docx", ".txt", ".md"}


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    _: TokenUser = Depends(require_admin),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported type '{ext}'. Allowed: PDF, DOCX, TXT, MD")
    if "/" in file.filename or "\\" in file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    dest = Path(settings.data_dir) / file.filename
    content = await file.read()
    dest.write_bytes(content)
    logger.info(f"Admin uploaded {file.filename} ({len(content):,} bytes)")
    return {"filename": file.filename, "size": len(content)}


@app.delete("/files/{filename}")
async def delete_file(
    filename: str,
    _: TokenUser = Depends(require_admin),
):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = Path(settings.data_dir) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    path.unlink()
    logger.info(f"Admin deleted {filename}")
    return {"message": f"{filename} deleted"}


@app.post("/ingest-url")
async def ingest_url(
    body: IngestUrlRequest,
    _: TokenUser = Depends(require_admin),
):
    """Fetch a web page, save its text to the knowledge base, and mark KB as stale."""
    from ingest import fetch_url_text

    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    try:
        text = fetch_url_text(body.url)
    except Exception as e:
        logger.error(f"URL ingest failed for {body.url}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")

    # Derive a safe filename from the URL
    slug = re.sub(r"[^\w.-]", "_", body.url.split("//")[-1])[:80]
    filename = f"web_{slug}.txt"
    dest = Path(settings.data_dir) / filename
    dest.write_text(text, encoding="utf-8")
    logger.info(f"Saved URL content as {filename} ({len(text):,} chars)")
    return {"filename": filename, "size": len(text)}


_reindex_state: Dict = {"status": "idle", "message": ""}


@app.get("/reindex/status")
async def reindex_status(_: TokenUser = Depends(require_admin)):
    return _reindex_state


@app.post("/reindex")
async def trigger_reindex(_: TokenUser = Depends(require_admin)):
    global _reindex_state
    if _reindex_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Reindex already in progress")
    _reindex_state = {"status": "running", "message": "Rebuilding knowledge base…"}
    asyncio.create_task(_run_reindex())
    return {"message": "Reindex started"}


async def _run_reindex():
    global _reindex_state
    try:
        # Pre-emptively clear state to reduce chance of file locks on Windows
        import retriever
        retriever._vector_store = None
        retriever._qa_chain = None

        import subprocess
        
        def run_ingestion_process():
            # Run ingest.py as a synchronous process
            return subprocess.run(
                [sys.executable, "ingest.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(Path(__file__).parent),
                text=False # Get raw bytes to handle with errors='replace' later
            )

        # Run the synchronous process in a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_ingestion_process)
        
        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode
        
        if returncode == 0:
            # Final clear to ensure fresh load on next query
            retriever._vector_store = None
            retriever._qa_chain = None
            
            _reindex_state = {"status": "done", "message": "Knowledge base rebuilt successfully"}
            logger.info("Reindex completed and retriever state cleared")
        else:
            # Use errors='replace' to avoid UnicodeDecodeError if ingest.py outputs weird chars
            decoded_stderr = stderr.decode('utf-8', errors='replace') if stderr else "No stderr output"
            error_msg = decoded_stderr[:400]
            _reindex_state = {"status": "error", "message": error_msg}
            logger.error(f"Reindex failed: {decoded_stderr}")
            
            # Write full error to a log file for debugging
            with open("reindex_error.log", "w", encoding="utf-8") as f:
                f.write(f"Timestamp: {datetime.utcnow().isoformat()}\n")
                f.write(f"Return Code: {returncode}\n")
                f.write(f"Stderr:\n{decoded_stderr}\n")
                f.write(f"Stdout:\n{stdout.decode('utf-8', errors='replace') if stdout else ''}\n")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        error_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
        _reindex_state = {"status": "error", "message": error_msg}
        logger.error(f"Reindex exception: {error_msg}\n{tb}")
        
        with open("reindex_error.log", "a", encoding="utf-8") as f:
            f.write(f"Timestamp: {datetime.utcnow().isoformat()}\n")
            f.write(f"Exception: {error_msg}\n")
            f.write(f"Traceback:\n{tb}\n")


if __name__ == "__main__":
    import uvicorn
    # Use reload_excludes to prevent uvicorn from restarting when we modify data/knowledge_data
    # On Windows, we exclude the entire directories to avoid file system event collisions
    uvicorn.run(
        "app:app", 
        host=settings.api_host, 
        port=settings.api_port, 
        reload=True,
        reload_excludes=["knowledge_data/*", "data/*", "*.log", "*.faiss", "*.pkl"]
    )
