"""
agent.py
========
Configures and exposes a LangChain tool-calling agent powered by
GPT-4o when an OpenAI key is available.

When no API key is set, a local retrieval-only agent is used that
searches the vector store and returns formatted results — no LLM
calls required.
"""

from backend.config import GEMINI_API_KEY, GEMINI_MODEL, USE_GEMINI, COLLECTION_CODE, COLLECTION_DOCS
from backend import vector_store

# ---------------------------------------------------------------------------
# Agent setup — choose between Gemini and local mode
# ---------------------------------------------------------------------------

if USE_GEMINI:
    # ── Full LangChain agent with Gemini ──────────────────────────────
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain.agents import create_agent
    from backend.tools import tools

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0,
        google_api_key=GEMINI_API_KEY,
    )

    SYSTEM_PROMPT = """\
You are an expert AI Developer Agent for a software company.
You help new developers, interns, and support engineers understand \
the codebase and debug issues.

You have access to two tools:
- search_documentation: for setup guides, config steps, how-to docs, error fixes
- search_code: for function explanations, code logic, debugging, implementation details

Rules:
- Always use a tool before answering — never answer from memory alone
- For setup/config questions → use search_documentation
- For code/function/debug questions → use search_code
- If the question needs both (e.g. "why is OAuth failing") → use BOTH tools
- Always mention the source file or doc in your answer

Response format (STRICT):
- Use Markdown.
- Start with a short direct answer.
- Then include a "## Evidence" section with bullet points.
- If code is relevant, include a "## Code" section with fenced code blocks.
- End with a "## Sources" section containing a Markdown list of source file paths or doc names.
"""

    # langchain>=1.x exposes `create_agent()` which returns a compiled state graph.
    # We use it for tool-calling behavior.
    agent_executor = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        debug=True,
    )
    print("✅ Agent mode: Gemini (full LangChain agent)")

else:
    # ── Local retrieval-only agent (no LLM calls) ─────────────────────
    agent_executor = None
    print("✅ Agent mode: Local retrieval (no Gemini key needed)")


# ---------------------------------------------------------------------------
# Local retrieval agent — used when no Gemini key is available
# ---------------------------------------------------------------------------

def _local_ask(question: str) -> dict:
    """
    A lightweight retrieval-only agent that searches both the code and
    documentation collections and formats the results into a readable
    answer — no LLM required.
    """
    print(f"\n🤖 [LOCAL] Agent processing: {question}")

    code_results = vector_store.search_documents(COLLECTION_CODE, question, n_results=3)
    doc_results = vector_store.search_documents(COLLECTION_DOCS, question, n_results=3)

    sections = []
    sources = []

    # --- Documentation results ---
    if doc_results:
        sections.append("**📄 Documentation**\n")
        for i, r in enumerate(doc_results, 1):
            source = r["metadata"].get("source", "unknown")
            text = r["text"].strip()
            sections.append(f"**Result {i}**\n")
            sections.append(f"Source: `{source}`\n")
            sections.append(f"{text}\n")
            if source not in sources:
                sources.append(source)

    # --- Code results ---
    if code_results:
        sections.append("**💻 Code**\n")
        for i, r in enumerate(code_results, 1):
            func_name = r["metadata"].get("function", "unknown")
            file_path = r["metadata"].get("file", "unknown")
            line = r["metadata"].get("line", "?")
            text = r["text"].strip()
            sections.append(f"**Result {i}: `{func_name}()`**\n")
            sections.append(f"File: `{file_path}` (Line {line})\n")
            sections.append(f"```python\n{text}\n```\n")
            source_ref = f"{file_path}:{func_name}()"
            if source_ref not in sources:
                sources.append(source_ref)

    if not sections:
        answer = (
            "I couldn't find any relevant results in the indexed codebase or "
            "documentation. Please make sure you've run the ingestion pipeline:\n\n"
            "```bash\npython backend/ingest.py\n```"
        )
    else:
        answer = "\n".join(sections).strip()

    print(f"✅ [LOCAL] Agent answered ({len(answer)} chars)")
    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "debug": {
            "doc_results": doc_results,
            "code_results": code_results,
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ask(question: str) -> dict:
    """
    Send a question to the AI Developer Agent and return the answer.

    Args:
        question: A natural-language question about code or documentation.

    Returns:
        A dict with keys:
            - question (str): The original question.
            - answer   (str): The agent's response.
        On failure the dict contains an 'error' key instead of 'answer'.
    """
    print(f"\n🤖 Agent processing: {question}")

    # Use local retrieval if no Gemini key
    if not USE_GEMINI:
        return _local_ask(question)

    try:
        # `create_agent()` expects the standard messages payload.
        result = agent_executor.invoke({"messages": [("user", question)]})

        answer = ""
        if isinstance(result, dict):
            # Common output shape: {"messages": [...]} where the last message is the assistant.
            messages = result.get("messages")
            if isinstance(messages, list) and messages:
                last = messages[-1]
                answer = getattr(last, "content", "") or ""
            else:
                answer = result.get("output", "") or ""

        if not isinstance(answer, str):
            if isinstance(answer, list):
                parts = []
                for item in answer:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                    elif isinstance(item, str):
                        parts.append(item)
                answer = "\n\n".join(parts).strip() if parts else str(answer)
            elif isinstance(answer, dict) and isinstance(answer.get("text"), str):
                answer = answer["text"]
            else:
                answer = str(answer)

        print(f"✅ Agent answered ({len(answer)} chars)")
        return {"question": question, "answer": answer}

    except Exception as exc:
        message = str(exc)
        if "NOT_FOUND" in message and "models/" in message:
            message = (
                f"{message}\n\n"
                "Tip: set GEMINI_MODEL in .env to a model available for your API key/project. "
                "The Gemini API error suggests calling ListModels to see supported model IDs."
            )
        print(f"❌ Agent error: {message}")
        return {"question": question, "error": message}


# ---------------------------------------------------------------------------
# Quick manual test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    test_question = "What does the handle_oauth_callback function do?"
    response = ask(test_question)

    print("\n" + "=" * 60)
    if "answer" in response:
        print(response["answer"])
    else:
        print(f"Error: {response['error']}")
    print("=" * 60)
