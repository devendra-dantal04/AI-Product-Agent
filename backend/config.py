"""
config.py
=========
Central configuration module. Loads environment variables from .env
and exposes constants and shared instances used across the backend.

When no valid GEMINI_API_KEY is set, the system falls back to
ChromaDB's built-in sentence-transformer embeddings (all-MiniLM-L6-v2)
which run locally and require no API key.
"""

import os
import sys
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from the project root (one level above backend/)
# ---------------------------------------------------------------------------
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_CODE = os.getenv("COLLECTION_CODE", "code_collection")
COLLECTION_DOCS = os.getenv("COLLECTION_DOCS", "docs_collection")

# ---------------------------------------------------------------------------
# Determine whether we can use Gemini or must fall back to local mode
# ---------------------------------------------------------------------------
USE_GEMINI = bool(GEMINI_API_KEY and GEMINI_API_KEY != "your_key_here")

# We intentionally use ChromaDB's built-in embeddings by default.
embeddings = None

if USE_GEMINI:
    print("✅ Using Gemini for LLM calls")
else:
    print(
        "\n⚠️  GEMINI_API_KEY / GOOGLE_API_KEY is not set — running in LOCAL MODE.\n"
        "   Using ChromaDB's built-in sentence-transformer embeddings.\n"
        "   The agent will use retrieval-only mode (no LLM calls).\n"
    )

# ---------------------------------------------------------------------------
# Quick sanity check when this module is run directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Config Loaded ===")
    print(f"  GEMINI_API_KEY     : {'***' + GEMINI_API_KEY[-4:] if len(GEMINI_API_KEY) > 4 else '(not set)'}")
    print(f"  USE_GEMINI         : {USE_GEMINI}")
    print(f"  CHROMA_PERSIST_DIR : {CHROMA_PERSIST_DIR}")
    print(f"  COLLECTION_CODE    : {COLLECTION_CODE}")
    print(f"  COLLECTION_DOCS    : {COLLECTION_DOCS}")
    if embeddings:
        print(f"  Embeddings model   : {embeddings.model}")
    else:
        print(f"  Embeddings         : ChromaDB default (all-MiniLM-L6-v2)")
