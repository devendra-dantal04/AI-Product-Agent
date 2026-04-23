# 🤖 AI Developer Agent

An intelligent AI-powered developer assistant that ingests your Python codebase and documentation (e.g., Confluence pages), stores them as vector embeddings in ChromaDB, and lets you ask natural-language questions about your code and docs through a sleek chat UI. Built with **FastAPI**, **LangChain**, **ChromaDB**, and **OpenAI**, the agent uses retrieval-augmented generation (RAG) to provide accurate, context-aware answers — from explaining functions and tracing logic to summarizing setup guides.

---

## 📁 Project Structure

```
project/
├── backend/
│   ├── main.py              # FastAPI server
│   ├── agent.py             # LangChain agent
│   ├── tools.py             # Code tool + Docs tool
│   ├── ingest.py            # Ingestion pipeline
│   ├── code_parser.py       # AST parsing with ast module
│   ├── vector_store.py      # ChromaDB setup and search
│   └── config.py            # All config/env vars
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── sample_data/
│   ├── sample_code.py       # Dummy Python file with 4-5 functions
│   └── sample_docs.md       # Fake Confluence setup guide (~200 words)
├── .env                     # Environment variables (not committed)
├── requirements.txt
└── README.md
```

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** The `ast` module is part of Python's standard library and does not require installation.

### 2. Configure Environment Variables

Copy or rename the `.env` file and add your OpenAI API key:

```
OPENAI_API_KEY=your_key_here
CHROMA_PERSIST_DIR=./chroma_db
COLLECTION_CODE=code_collection
COLLECTION_DOCS=docs_collection
```

### 3. Run the Ingestion Pipeline

Parse and embed your sample code and documentation into ChromaDB:

```bash
python backend/ingest.py
```

This will:
- Parse `sample_data/sample_code.py` using the `ast` module to extract function-level chunks.
- Read `sample_data/sample_docs.md` and split it into document chunks.
- Store all embeddings in ChromaDB under their respective collections.

### 4. Start the Backend Server

```bash
uvicorn backend.main:app --reload
```

The API will be available at [http://localhost:8000](http://localhost:8000).

### 5. Open the Frontend UI

Open `frontend/index.html` directly in your browser (no build step required):

```bash
# On Windows
start frontend/index.html

# On macOS
open frontend/index.html

# On Linux
xdg-open frontend/index.html
```

---

## 💬 Example Questions to Ask

Once the server is running and the UI is open, try asking:

| Category | Example Question |
|---|---|
| **Code Explanation** | *"What does the `calculate_average` function do?"* |
| **Function Listing** | *"List all functions in the sample code."* |
| **Logic Tracing** | *"How does error handling work in the data processing functions?"* |
| **Documentation** | *"Summarize the Confluence setup guide."* |
| **Setup Help** | *"What are the prerequisites mentioned in the docs?"* |
| **Cross-Reference** | *"Which functions relate to the setup steps in the documentation?"* |

---

## 🛠 Tech Stack

| Component | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| AI / LLM | OpenAI (via LangChain) |
| Embeddings & RAG | LangChain + ChromaDB |
| Code Parsing | Python `ast` module |
| Frontend | Vanilla HTML / CSS / JS |

---

## 📝 License

This project is for educational and demonstration purposes.
