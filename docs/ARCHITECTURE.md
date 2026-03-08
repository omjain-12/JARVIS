# JARVIS Architecture

## System Pipeline

```
User Request
    │
    ▼
┌──────────────┐
│  Safety Check │  ── Block harmful / invalid input
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Retriever   │  ── Fetch context from memory (vector + structured)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    Planner    │  ── Classify request → decision (answer | plan | action)
└──────┬───────┘
       │
       ├── answer ──────────────────────────┐
       │                                    ▼
       ├── plan ──► [Decompose] ──────► [Executor] ──► [Respond]
       │                                  |
       └── action ──► [Decompose]         |
                          │               |
                      [Action Plan]       |
                          │               |
                       [Confirm] ---------
                          │
                      [Executor]
                          │
                       [Learn]
                          │
                       [Respond]
```

## Agent Responsibilities

| Agent | Role |
|---|---|
| **Safety Check** | Validates input length, detects harmful content. Blocks or passes. |
| **Retriever** | Queries vector DB (Azure AI Search or local) and structured DB. Assembles ranked context. Does NOT reason. |
| **Planner** | Classifies intent, produces strategy with `decision` (answer / plan / action). Does NOT execute. |
| **Task Decomposer** | Breaks planner strategy into ordered, atomic tasks. |
| **Action Planner** | Converts tasks into tool call instructions with parameters. Sets `requires_confirmation`. |
| **Confirm** | Gates execution — ensures user confirmation before side-effect actions. |
| **Executor** | Generates text responses (LLM) or executes tool calls (Toolbox). Formats output. |
| **Behavior Analyzer** | Tracks habit patterns, reminder success, frequent actions. Lightweight learning. |
| **Respond** | Saves conversation history, marks processing complete. |

## Conditional Routing (LangGraph)

The workflow uses `StateGraph` with conditional edges:

- **After Safety**: `safe` → Retrieve, `blocked` → Respond
- **After Plan**: `answer` → Execute, `plan` → Decompose → Execute, `action` → Decompose → Action Plan → Confirm → Execute → Learn → Respond

This avoids running unnecessary nodes (e.g., action planning for simple questions).

## Azure Architecture

```
┌─────────────────────────────────────────┐
│              JARVIS API (FastAPI)        │
│                                         │
│  ┌──────────┐  ┌──────────────────────┐ │
│  │ LangGraph│  │  Toolbox             │ │
│  │ Workflow │  │  (email, SMS, habits,│ │
│  │          │  │   reminders, etc.)   │ │
│  └────┬─────┘  └──────────────────────┘ │
└───────┼─────────────────────────────────┘
        │
        ├──► Azure OpenAI (GPT-4o + embeddings)
        │
        ├──► Azure AI Search (vector knowledge retrieval)
        │      ↕ USE_AZURE_VECTOR=true: Azure AI Search
        │      ↕ USE_AZURE_VECTOR=false: local in-memory fallback
        │
        ├──► Azure Blob Storage (document storage)
        │
        ├──► Azure Document Intelligence (PDF/DOCX extraction)
        │
        ├──► SQLite / PostgreSQL (structured data: tasks, habits, reminders)
        │
        └──► Azure Application Insights (optional telemetry)
               ↕ APPLICATIONINSIGHTS_CONNECTION_STRING
               ↕ Logs: planner decisions, tool executions, latency, errors
```

## Key Configuration Flags

| Variable | Purpose |
|---|---|
| `USE_AZURE_VECTOR` | `true` = Azure AI Search, `false` = local keyword search |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Enables Azure Monitor log export |
| `AZURE_OPENAI_ENDPOINT` / `API_KEY` | Required for LLM calls |
| `AZURE_SEARCH_ENDPOINT` / `API_KEY` | Required when `USE_AZURE_VECTOR=true` |

## Tool Registry

All tools are registered through `Toolbox.register_defaults()` at startup.
The executor calls tools exclusively through `Toolbox.execute(tool_name, params)`.
No direct tool function calls exist outside the Toolbox.

Registered tools: `email_tool`, `sms_tool`, `whatsapp_tool`, `reminder_tool`, `habit_tracker_tool`.
