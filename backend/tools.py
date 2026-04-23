"""
tools.py
========
LangChain tools that the AI agent can invoke to retrieve relevant
documentation or code snippets from the ChromaDB vector store.
"""

from langchain_core.tools import tool

from backend.config import COLLECTION_CODE, COLLECTION_DOCS
from backend import vector_store


# ---------------------------------------------------------------------------
# Tool 1 — Documentation search
# ---------------------------------------------------------------------------

@tool
def search_documentation(query: str) -> str:
    """
    Use this tool to answer questions about setup, configuration, how-to guides,
    prerequisites, error fixes, OAuth scopes, redirect URIs, and any process
    documentation. Input should be a plain English search query.
    """
    print(f"🔍 Documentation tool called with: {query}")

    results = vector_store.search_documents(COLLECTION_DOCS, query, n_results=3)

    if not results:
        return "No documentation found for this query."

    # Format each result into a readable block
    formatted = "📄 Documentation Results:\n\n"
    for r in results:
        source = r["metadata"].get("source", "unknown")
        text = r["text"]
        formatted += f"Source: {source}\n{text}\n---\n"

    return formatted


# ---------------------------------------------------------------------------
# Tool 2 — Code search
# ---------------------------------------------------------------------------

@tool
def search_code(query: str) -> str:
    """
    Use this tool to answer questions about specific functions, code logic,
    debugging, what a function does, how a feature is implemented,
    call chains, or any question that requires looking at actual code.
    Input should be a plain English search query.
    """
    print(f"🔍 Code tool called with: {query}")

    results = vector_store.search_documents(COLLECTION_CODE, query, n_results=3)

    if not results:
        return "No code found for this query."

    # Format each result into a readable block
    formatted = "💻 Code Results:\n\n"
    for r in results:
        func_name = r["metadata"].get("function", "unknown")
        file_path = r["metadata"].get("file", "unknown")
        line = r["metadata"].get("line", "?")
        text = r["text"]
        formatted += f"Function: {func_name}\nFile: {file_path} (Line {line})\n{text}\n---\n"

    return formatted


# ---------------------------------------------------------------------------
# Export the tool list for the agent
# ---------------------------------------------------------------------------
tools = [search_documentation, search_code]
