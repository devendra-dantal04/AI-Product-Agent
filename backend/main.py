"""
main.py
=======
FastAPI server that exposes the AI Developer Agent over HTTP.
Provides endpoints for asking questions, running ingestion,
and checking system health.

Start with:
    uvicorn backend.main:app --reload
"""

import time
import os
import sys
from contextlib import asynccontextmanager

# Ensure project root is on the path when running via uvicorn
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import agent, vector_store, ingest
from backend.config import COLLECTION_CODE, COLLECTION_DOCS, CHROMA_PERSIST_DIR, USE_GEMINI


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown logic
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────
    mode = "Gemini" if USE_GEMINI else "Local (no API key needed)"
    print(f"\n🚀 AI Developer Agent running on http://localhost:8000")
    print(f"   Mode: {mode}\n")

    # Check if the vector DB has been populated
    if not os.path.isdir(CHROMA_PERSIST_DIR):
        print(
            "⚠️  No vector DB found. Run:  python backend/ingest.py first\n"
            f"   Expected directory: {os.path.abspath(CHROMA_PERSIST_DIR)}\n"
        )
    else:
        print(f"✅ ChromaDB directory found: {os.path.abspath(CHROMA_PERSIST_DIR)}")

    yield  # ← app is running

    # ── Shutdown ──────────────────────────────────────────────────
    print("\n🛑 AI Developer Agent shutting down\n")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Developer Agent",
    description="RAG-powered agent for exploring code and documentation",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow all origins for frontend development
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response logging middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000)
    print(
        f"📡 {request.method} {request.url.path} → {response.status_code}  ({duration_ms}ms)"
    )
    return response


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str


class IngestRequest(BaseModel):
    type: str       # "code" or "docs"
    filepath: str


# ---------------------------------------------------------------------------
# 1. GET / — root status
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "running", "message": "AI Developer Agent API"}


# ---------------------------------------------------------------------------
# 2. POST /ask — send a question to the agent
# ---------------------------------------------------------------------------
@app.post("/ask")
async def ask_question(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    result = agent.ask(req.question)

    if "error" in result:
        return JSONResponse(
            status_code=500,
            content={
                "error": result["error"],
                "status": "error",
            },
        )

    response = {
        "question": result.get("question", req.question),
        "answer": result.get("answer", ""),
        "status": "success",
    }

    if isinstance(result.get("sources"), list):
        response["sources"] = result["sources"]

    return response


# ---------------------------------------------------------------------------
# 3. GET /health — system health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    try:
        code_col = vector_store.get_collection(COLLECTION_CODE)
        docs_col = vector_store.get_collection(COLLECTION_DOCS)

        return {
            "status": "healthy",
            "collections": [
                {"name": COLLECTION_CODE, "documents": code_col.count()},
                {"name": COLLECTION_DOCS, "documents": docs_col.count()},
            ],
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(exc)},
        )


# ---------------------------------------------------------------------------
# 4. POST /ingest — trigger ingestion for a file
# ---------------------------------------------------------------------------
@app.post("/ingest")
async def ingest_file(req: IngestRequest):
    filepath = req.filepath

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

    try:
        if req.type == "code":
            count = ingest.ingest_code(filepath)
        elif req.type == "docs":
            count = ingest.ingest_docs(filepath)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid type '{req.type}'. Must be 'code' or 'docs'.",
            )

        return {
            "status": "success",
            "message": f"Ingested {count} chunks from {filepath}",
            "type": req.type,
            "chunks": count,
        }

    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(exc)},
        )
