"""
ingest.py
=========
Ingestion pipeline that reads sample code and documentation files,
splits them into meaningful chunks, and stores the embeddings in
ChromaDB via the vector_store module.

Usage:
    python backend/ingest.py
"""

import os
import sys

# Ensure the project root is on sys.path so `backend.*` imports resolve
# when running this script directly (python backend/ingest.py).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.config import COLLECTION_CODE, COLLECTION_DOCS
from backend import code_parser, vector_store


# ---------------------------------------------------------------------------
# Documentation ingestion
# ---------------------------------------------------------------------------

def ingest_docs(filepath: str) -> int:
    """
    Read a Markdown documentation file, split it into paragraph-level
    chunks, and store them in the docs ChromaDB collection.

    Args:
        filepath: Path to a .md file.

    Returns:
        The number of chunks stored.
    """
    filepath = os.path.normpath(filepath)
    print(f"\n{'='*60}")
    print(f"  📄 Ingesting documentation: {filepath}")
    print(f"{'='*60}")

    # Read the raw markdown content
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into chunks on double newlines (paragraph boundaries)
    raw_chunks = content.split("\n\n")

    # Filter out tiny fragments (headings-only, blank lines, etc.)
    chunks = [chunk.strip() for chunk in raw_chunks if len(chunk.strip()) >= 20]

    print(f"[ingest] Raw paragraphs: {len(raw_chunks)} → usable chunks: {len(chunks)}")

    # Build document dicts for the vector store
    documents = []
    for i, chunk in enumerate(chunks):
        doc = {
            "id": f"doc_{i}",
            "text": chunk,
            "metadata": {
                "source": filepath,
                "type": "documentation",
            },
        }
        documents.append(doc)
        # Show a short preview of each chunk
        preview = chunk.replace("\n", " ")[:80]
        print(f"[ingest]   chunk doc_{i}: \"{preview}…\"")

    # Store in ChromaDB
    stored = vector_store.add_documents(COLLECTION_DOCS, documents)
    print(f"[ingest] ✅ Stored {stored} documentation chunk(s) in '{COLLECTION_DOCS}'")
    return stored


# ---------------------------------------------------------------------------
# Code ingestion
# ---------------------------------------------------------------------------

def ingest_code(filepath: str) -> int:
    """
    Parse a Python source file into function-level chunks and store
    them in the code ChromaDB collection.

    Args:
        filepath: Path to a .py file.

    Returns:
        The number of function chunks stored.
    """
    filepath = os.path.normpath(filepath)
    print(f"\n{'='*60}")
    print(f"  🐍 Ingesting code: {filepath}")
    print(f"{'='*60}")

    # Parse the file into function metadata dicts
    functions = code_parser.parse_file(filepath)

    if not functions:
        print("[ingest] No functions found — nothing to ingest.")
        return 0

    # Build embeddable text and document dicts
    documents = []
    for func in functions:
        chunk_text = code_parser.build_chunk_text(func)
        doc = {
            "id": f"code_{func['name']}",
            "text": chunk_text,
            "metadata": {
                "file": filepath,
                "function": func["name"],
                "line": func["start_line"],
                "type": "code",
            },
        }
        documents.append(doc)
        print(f"[ingest]   function: {func['name']}()  (line {func['start_line']})")

    # Store in ChromaDB
    stored = vector_store.add_documents(COLLECTION_CODE, documents)
    print(f"[ingest] ✅ Stored {stored} code chunk(s) in '{COLLECTION_CODE}'")
    return stored


# ---------------------------------------------------------------------------
# Main — run the full ingestion pipeline
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🚀 AI Developer Agent — Ingestion Pipeline")
    print("=" * 60)

    # Resolve paths relative to the project root
    project_root = os.path.join(os.path.dirname(__file__), "..")
    docs_path = os.path.join(project_root, "sample_data", "sample_docs.md")
    code_path = os.path.join(project_root, "sample_data", "sample_code.py")

    # 1. Ingest documentation
    doc_count = ingest_docs(docs_path)

    # 2. Ingest code
    code_count = ingest_code(code_path)

    # 3. Summary
    print("\n" + "=" * 60)
    print(f"  ✅ Ingestion complete — {doc_count} doc chunks, {code_count} code chunks indexed successfully")
    print("=" * 60 + "\n")
