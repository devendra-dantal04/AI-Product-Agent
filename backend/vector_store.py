"""
vector_store.py
===============
Manages the ChromaDB persistent vector store — collection creation,
document insertion (with OpenAI embeddings), and similarity search.

When USE_OPENAI is False, ChromaDB's built-in default embedding function
(all-MiniLM-L6-v2 via sentence-transformers) is used instead — no API
key required.
"""

import chromadb
from chromadb.utils import embedding_functions
from backend.config import CHROMA_PERSIST_DIR

# ---------------------------------------------------------------------------
# Initialise the persistent ChromaDB client
# ---------------------------------------------------------------------------
print(f"[vector_store] Initialising ChromaDB client → persist_dir='{CHROMA_PERSIST_DIR}'")

chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

# ---------------------------------------------------------------------------
# Choose the embedding function
# ---------------------------------------------------------------------------
# Use ChromaDB's built-in default sentence-transformer model
_chroma_ef = embedding_functions.DefaultEmbeddingFunction()
print("[vector_store] ChromaDB client ready ✓ (local sentence-transformer embeddings)")


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def get_collection(name: str) -> chromadb.Collection:
    """
    Return an existing ChromaDB collection or create a new one.

    Args:
        name: The collection name (e.g. 'code_collection').

    Returns:
        A chromadb.Collection instance.
    """
    kwargs = {
        "name": name,
        "metadata": {"hnsw:space": "cosine"},  # use cosine similarity
    }
    if _chroma_ef is not None:
        kwargs["embedding_function"] = _chroma_ef

    collection = chroma_client.get_or_create_collection(**kwargs)
    print(f"[vector_store] Collection '{name}' ready — {collection.count()} existing documents")
    return collection


# ---------------------------------------------------------------------------
# Document ingestion
# ---------------------------------------------------------------------------

def add_documents(collection_name: str, documents: list[dict]) -> int:
    """
    Embed and store a batch of documents in the specified collection.

    Each document is a dict with the keys:
        - id   (str):   A unique identifier for the document.
        - text (str):   The content to embed and store.
        - metadata (dict): Arbitrary metadata attached to the document.

    Args:
        collection_name: Target ChromaDB collection name.
        documents:       List of document dicts.

    Returns:
        The number of documents successfully stored.
    """
    if not documents:
        print(f"[vector_store] add_documents('{collection_name}') — nothing to add (empty list)")
        return 0

    collection = get_collection(collection_name)

    # --- Prepare batches -----------------------------------------------
    ids = [doc["id"] for doc in documents]
    texts = [doc["text"] for doc in documents]
    metadatas = [doc.get("metadata", {}) for doc in documents]

    # --- Let ChromaDB handle embeddings with its default model ---------
    print(f"[vector_store] Embedding {len(texts)} document(s) for '{collection_name}' locally …")
    collection.upsert(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
    )

    print(f"[vector_store] Stored {len(ids)} document(s) in '{collection_name}' ✓")
    return len(ids)


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------

def search_documents(
    collection_name: str,
    query: str,
    n_results: int = 3,
) -> list[dict]:
    """
    Embed a query and perform similarity search against a ChromaDB
    collection.

    Args:
        collection_name: The collection to search.
        query:           The natural-language query string.
        n_results:       Maximum number of results to return (default 3).

    Returns:
        A list of dicts sorted by relevance (best first), each containing:
            - text     (str):   The stored document text.
            - metadata (dict):  Associated metadata.
            - score    (float): Cosine-distance score (lower = more similar).
    """
    collection = get_collection(collection_name)

    if collection.count() == 0:
        print(f"[vector_store] Collection '{collection_name}' is empty — returning no results")
        return []

    # --- Build query arguments -----------------------------------------
    print(f"[vector_store] Searching '{collection_name}' for: \"{query[:80]}…\"")

    query_kwargs = {
        "n_results": min(n_results, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }

    # Let ChromaDB embed the query with its default function
    query_kwargs["query_texts"] = [query]

    # --- Query ChromaDB ------------------------------------------------
    results = collection.query(**query_kwargs)

    # --- Format output --------------------------------------------------
    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "text": doc,
            "metadata": meta,
            "score": round(dist, 6),
        })

    # Already sorted by ChromaDB (ascending distance = best match first)
    print(f"[vector_store] Returning {len(output)} result(s) — best score = {output[0]['score'] if output else 'N/A'}")
    return output


# ---------------------------------------------------------------------------
# Quick manual test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n=== Vector Store Smoke Test ===\n")

    test_docs = [
        {
            "id": "test-001",
            "text": "The handle_oauth_callback function processes the OAuth redirect.",
            "metadata": {"source": "test", "type": "code"},
        },
        {
            "id": "test-002",
            "text": "Configure SSO by providing the tenant ID and metadata URL.",
            "metadata": {"source": "test", "type": "docs"},
        },
    ]

    added = add_documents("_test_collection", test_docs)
    print(f"\nAdded {added} test document(s).\n")

    hits = search_documents("_test_collection", "How does OAuth callback work?")
    for i, hit in enumerate(hits, 1):
        print(f"  [{i}] score={hit['score']}  meta={hit['metadata']}")
        print(f"      {hit['text'][:100]}")

    # Clean up test collection
    chroma_client.delete_collection("_test_collection")
    print("\nTest collection deleted. Smoke test passed ✓")
