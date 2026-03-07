# 🧠 JARVIS — AI Second Brain

> **Multi-agent AI Personal Knowledge Manager** built for the Microsoft Hackathon 2026.

JARVIS ingests your documents, understands your goals, and acts as a persistent second brain — answering questions, generating flashcards, creating study plans, tracking habits, and executing actions on your behalf.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      FastAPI Server                        │
│  /knowledge/query   /documents/upload   /auth/*   /health  │
└────────────────────────┬───────────────────────────────────┘
                         │
                  ┌──────▼──────┐
                  │  LangGraph  │   ← Declarative state-graph
                  │  Workflow   │
                  └──────┬──────┘
                         │
     ┌───────────────────┼───────────────────┐
     ▼                   ▼                   ▼
 ┌────────┐        ┌──────────┐        ┌──────────┐
 │Retriever│        │ Planner  │        │ Executor │
 │  Agent  │        │  Agent   │        │  Agent   │
 └────┬───┘        └────┬─────┘        └────┬─────┘
      │                  │                   │
      ▼                  ▼                   ▼
 ┌─────────┐      ┌───────────┐      ┌───────────┐
 │  Memory  │      │Task Decomp│      │  Toolbox  │
 │ Manager  │      │Action Plan│      │  (5 tools)│
 └─────────┘      └───────────┘      └───────────┘
      │
  ┌───┴───┐
  ▼       ▼
SQLite  Azure AI
 ORM    Search
```

### Pipeline (per request)

1. **Safety Check** — input validation, injection detection, rate limiting
2. **Retriever** — query expansion + hybrid vector/keyword search + structured DB
3. **Planner** — LLM-driven strategy: reasoning vs planning vs action
4. **Task Decomposer** — splits strategy into discrete tasks
5. **Action Planner** — maps tasks to tool calls with parameters
6. **Confirmation** — (placeholder for human-in-the-loop)
7. **Executor** — runs tools + generates output (answer / summary / flashcards / quiz / study plan)
8. **Learning** — tracks behaviour patterns and preferences
9. **Response** — saves conversation, returns structured result

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Azure OpenAI GPT-4o |
| Embeddings | Azure OpenAI text-embedding-3-small (1536 dims) |
| Vector DB | Azure AI Search (HNSW) with in-memory fallback |
| Relational DB | SQLAlchemy async + aiosqlite (SQLite) / asyncpg (Postgres) |
| Workflow | LangGraph StateGraph |
| API | FastAPI + Uvicorn |
| Auth | JWT (HS256) via python-jose |
| Document Parsing | PyMuPDF, python-docx, python-pptx |

---

## Quick Start

### 1. Clone & install

```bash
git clone <repo-url>
cd "microsoft hackathon 26'"
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Copy the example env file and fill in your Azure credentials:

```bash
cp .env.example .env
# Edit .env with your Azure keys
```

**Minimum required** for basic operation (without Azure):
- No env vars needed — the system falls back to in-memory vector search and local SQLite.

**Full Azure integration** — set these in `.env`:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-search-key

AZURE_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://your-doc-intel.cognitiveservices.azure.com/
AZURE_DOC_INTELLIGENCE_API_KEY=your-key

SECRET_KEY=change-me-in-production
DEBUG=true
```

### 3. Run

```bash
# API server (default — http://localhost:8000)
python main.py

# Interactive CLI mode
python main.py --cli
```

### 4. Try it

```bash
# Health check
curl http://localhost:8000/health

# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com", "password": "secret123"}'

# Query the knowledge base
curl -X POST http://localhost:8000/knowledge/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What should I study today?"}'

# Upload a document
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@notes.pdf"
```

---

## Project Structure

```
├── main.py                        # Entry point (server + CLI)
├── requirements.txt               # Python dependencies
├── api/
│   └── api_server.py              # FastAPI routes & middleware
├── app/
│   ├── agents/
│   │   ├── retriever/retriever.py # Context retrieval + query expansion
│   │   ├── planner/
│   │   │   ├── planner.py         # LLM strategy generation
│   │   │   ├── task_decomposer.py # Strategy → task list
│   │   │   └── action_planner.py  # Tasks → tool instructions
│   │   └── executor/executor.py   # Output generation + tool execution
│   ├── graph/workflow.py          # LangGraph StateGraph definition
│   ├── learning/behavior_analyzer.py
│   ├── memory/
│   │   ├── memory_manager.py      # Unified memory interface
│   │   ├── structured_db.py       # SQLAlchemy ORM (15 models)
│   │   └── vector_db.py           # Azure AI Search / in-memory fallback
│   ├── orchestrator/orchestrator.py
│   ├── safety/safety_check.py     # Input validation & rate limiting
│   ├── state/agent_state.py       # TypedDict state flowing through pipeline
│   ├── toolbox/toolbox.py         # Tool registry & dispatcher
│   ├── tools/                     # email, sms, whatsapp, reminder, habit_tracker
│   └── utils/
│       ├── config.py              # Pydantic settings loader
│       └── logger.py              # Structured JSON logging
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health + service status |
| `GET` | `/status` | Extended config status |
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Get JWT token |
| `POST` | `/knowledge/query` | **Core** — process any query through the agent pipeline |
| `POST` | `/documents/upload` | Upload & ingest a document |
| `GET` | `/documents` | List user documents |
| `GET` | `/documents/{id}` | Get document metadata |
| `DELETE` | `/documents/{id}` | Delete a document |
| `POST` | `/tasks` | Create a task |
| `GET` | `/tasks` | List tasks |
| `POST` | `/reminders` | Create a reminder |
| `GET` | `/reminders` | List reminders |
| `POST` | `/habits` | Create a habit |
| `GET` | `/habits` | List habits |
| `POST` | `/habits/{id}/log` | Log habit completion |
| `GET` | `/flashcards` | List flashcard sets |
| `GET` | `/flashcards/{id}` | Get flashcards in a set |
| `GET` | `/quizzes` | List quizzes |
| `GET` | `/study-plans` | List study plans |
| `GET` | `/conversations` | Conversation history |

---

## License

MIT
