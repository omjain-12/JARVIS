# JARVIS — AI Second Brain

> **Multi-agent AI Personal Assistant** built for the Microsoft Hackathon 2026.

JARVIS ingests your documents, understands your goals, and acts as a persistent second brain — answering questions, tracking habits, setting reminders, and executing actions on your behalf. Comes with a full assistant UI, voice input/output, and a chat API.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                  Frontend (Next.js + Tailwind)             │
│     Chat UI  •  Voice Input/Output  •  Dark Theme         │
└────────────────────────┬───────────────────────────────────┘
                         │  /chat  /voice-to-text  /text-to-voice
                         ▼
┌────────────────────────────────────────────────────────────┐
│                   Backend API (FastAPI)                     │
│  /chat  /confirm  /voice-*  │  /knowledge/query  /auth/*   │
│  (port 8001)                │  (port 8000)                  │
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
| Frontend | Next.js 14 + React 18 + TailwindCSS |
| Voice | Azure Speech SDK (STT + TTS) |
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

### Option A — Docker (recommended for demo)

```bash
cp .env.example .env
# Edit .env with your Azure keys
docker-compose up --build
```

Services:
- **Frontend UI**: http://localhost:3000
- **Backend API (chat/voice)**: http://localhost:8001
- **Core API (auth/docs/tasks)**: http://localhost:8000

### Option B — Local development

#### 1. Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Azure keys

# Start the core API server (port 8000)
python main.py

# In a second terminal — start the assistant backend (port 8001)
python -m uvicorn backend.api.server:app --reload --port 8001
```

#### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

### 3. Configuration

**Minimum required** (runs without Azure — in-memory vector search + local SQLite):
- No env vars needed.

**Full Azure integration** — set in `.env`:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o

AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-search-key

# Voice (optional)
AZURE_SPEECH_KEY=your-speech-key
AZURE_SPEECH_REGION=eastus
AZURE_TTS_VOICE=en-US-AndrewNeural
AZURE_TTS_STYLE=chat
AZURE_TTS_FORCE_MALE=true

# WhatsApp via Whapi (optional)
WHAPI_TOKEN=your-whapi-bearer-token
WHAPI_BASE_URL=https://gate.whapi.cloud/messages/text
# Used when user provides local 10-digit numbers (default is 91)
WHAPI_DEFAULT_COUNTRY_CODE=91
WHAPI_TIMEOUT_SECONDS=30
WHAPI_MAX_RETRIES=2

# SMS via Twilio (optional)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_FROM_NUMBER=+1234567890
TWILIO_MESSAGING_SERVICE_SID=
TWILIO_DEFAULT_COUNTRY_CODE=91
TWILIO_SIMULATE=false
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
├── docker-compose.yml             # Full stack (backend + frontend)
├── api/
│   └── api_server.py              # Core API — auth, documents, tasks, habits
├── backend/
│   ├── api/server.py              # Assistant API — /chat, /confirm, /voice-*
│   ├── services/
│   │   ├── agent_service.py       # Workflow wrapper
│   │   └── voice_service.py       # Azure Speech SDK (STT + TTS)
│   └── models/
│       └── request_models.py      # Pydantic request/response schemas
├── frontend/
│   ├── src/
│   │   ├── pages/index.tsx        # Main assistant page
│   │   ├── components/
│   │   │   ├── Header.tsx         # Voice toggle, connection status
│   │   │   ├── ChatWindow.tsx     # Scrollable message list
│   │   │   ├── ChatBubble.tsx     # User / assistant bubbles
│   │   │   ├── ChatInput.tsx      # Text input + mic + send
│   │   │   └── TypingIndicator.tsx
│   │   ├── services/api.ts        # Fetch wrappers for backend
│   │   ├── types/index.ts         # TypeScript types
│   │   └── styles/globals.css     # TailwindCSS + custom styles
│   ├── package.json
│   ├── tailwind.config.js
│   └── Dockerfile
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
│   │   ├── structured_db.py       # SQLAlchemy ORM
│   │   └── vector_db.py           # Azure AI Search / in-memory fallback
│   ├── safety/safety_check.py     # Input validation & rate limiting
│   ├── state/agent_state.py       # TypedDict state flowing through pipeline
│   ├── toolbox/toolbox.py         # Tool registry & dispatcher
│   ├── tools/                     # email, sms, whatsapp, reminder, habit_tracker
│   └── utils/
│       ├── azure_llm.py           # Central Azure OpenAI factory (singleton)
│       ├── azure_search.py        # Azure AI Search client
│       ├── config.py              # Pydantic settings loader
│       └── logger.py              # Structured JSON logging + App Insights
├── Dockerfile
└── .env.example
```

---

## API Endpoints

### Assistant API (port 8001)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Send a message to the agent pipeline |
| `POST` | `/confirm` | Confirm or reject a pending tool action |
| `POST` | `/voice-to-text` | Upload audio → transcribed text (Azure STT) |
| `POST` | `/text-to-voice` | Text → audio WAV response (Azure TTS) |
| `POST` | `/voice-to-voice` | Full pipeline: audio → agent → audio |
| `GET` | `/health` | Health check with voice availability |

### Core API (port 8000)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health + service status |
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Get JWT token |
| `POST` | `/knowledge/query` | Process any query through the agent pipeline |
| `POST` | `/documents/upload` | Upload & ingest a document |
| `GET` | `/documents` | List user documents |
| `POST` | `/tasks` | Create a task |
| `GET` | `/tasks` | List tasks |
| `POST` | `/reminders` | Create a reminder |
| `GET` | `/reminders` | List reminders |
| `POST` | `/habits` | Create a habit |
| `GET` | `/habits` | List habits |
| `POST` | `/habits/{id}/log` | Log habit completion |
| `GET` | `/conversations` | Conversation history |

---

## License

MIT
