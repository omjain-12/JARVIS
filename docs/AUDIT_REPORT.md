# JARVIS Codebase — Deep Architectural Audit Report

**Date:** 2025-01-26  
**Scope:** Full codebase — 23 source files, ~5,800 lines

---

## Executive Summary

The audit uncovered **4 critical bugs**, **5 dead-code clusters**, **2 redundant subsystems**, and **3 architectural gaps**. All issues are catalogued below with severity, location, and recommended fix. The cleanup section at the end tracks which issues have been resolved in this pass.

---

## 1. CRITICAL BUGS

### BUG-1 · `store_document_chunks()` call uses wrong parameter names & types
- **File:** `api/api_server.py` (upload_document endpoint)
- **Severity:** Runtime crash on document upload
- **Issue:**
  - Passes `filename=` but `MemoryManager.store_document_chunks()` expects `source_filename=`
  - Passes `chunks` as `List[str]` (from `_chunk_text()`) but the method expects `List[Dict[str, Any]]` with a `"content"` key
- **Fix:** Rename kwarg to `source_filename`, wrap strings as `[{"content": c} for c in chunks]`

### BUG-2 · `create_task` priority type mismatch
- **File:** `api/api_server.py` → `TaskCreateRequest`
- **Severity:** Potential DB error
- **Issue:** `priority` field is `str = "medium"` but `structured_db.create_task()` expects `int` (0/1/2)
- **Fix:** Change to `int = 0` or add mapping

### BUG-3 · `create_habit` passes unsupported `target_count`
- **File:** `api/api_server.py` → `create_habit` endpoint
- **Severity:** Runtime TypeError
- **Issue:** `HabitCreateRequest.target_count` is passed to `structured_db.create_habit(**kwargs)`, but that method has no `target_count` parameter
- **Fix:** Remove `target_count` from the API call, or only pass supported kwargs

### BUG-4 · `create_reminder` passes `remind_at` as raw string
- **File:** `api/api_server.py` → `create_reminder` endpoint
- **Severity:** Potential TypeError
- **Issue:** `body.remind_at` is a raw ISO string, but `structured_db.create_reminder()` expects a `datetime` object
- **Fix:** Parse ISO string to datetime before passing

---

## 2. DEAD CODE

### DEAD-1 · `app/orchestrator/` — entire module is dead
- **Files:** `orchestrator.py` (~276 lines), `__init__.py`
- **Reason:** Superseded by `app/graph/workflow.py` (LangGraph). No file in the codebase imports `from app.orchestrator`.
- **Action:** Delete directory

### DEAD-2 · Flashcard / Quiz / Study Plan legacy code
- **Files affected:**
  - `app/memory/structured_db.py` — 6 ORM models (`FlashcardSet`, `Flashcard`, `Quiz`, `QuizQuestion`, `StudyPlan`, + User relationships), 7 CRUD methods
  - `app/memory/memory_manager.py` — 7 passthrough methods (`save_flashcard_set`, `get_flashcard_sets`, `get_flashcards`, `save_quiz`, `get_quizzes`, `save_study_plan`, `get_study_plans`)
- **Reason:** Educational features were removed in Session 2. No agent, tool, or API endpoint calls these methods.
- **Action:** Remove ORM models, CRUD methods, passthrough methods, and User relationships

### DEAD-3 · `get_llm()` LangChain factory — never called
- **File:** `app/utils/azure_llm.py`
- **Reason:** All agents import and use `get_openai_client()`. Nothing calls `get_llm()`.
- **Dependency impact:** `langchain-openai>=0.1.0` in `requirements.txt` is ONLY needed for this dead function (LangGraph itself doesn't require it).
- **Action:** Remove function. Keep `langchain-openai` dependency since LangGraph may use it implicitly.

### DEAD-4 · `store_memory()` / `store_behavior_pattern()` — never called
- **File:** `app/memory/memory_manager.py`
- **Reason:** Added in Session 4 as unified API, but no agent, tool, or workflow node ever calls them.
- **Action:** Keep for now — they're correctly implemented and useful. Mark as "API available, not yet wired."

### DEAD-5 · `use_azure_vector` config flag — superseded
- **File:** `app/utils/config.py`, `.env.example`
- **Reason:** Retriever now exclusively uses `use_azure_search`. `use_azure_vector` is never read.
- **Action:** Remove from `AppConfig` and `.env.example`

---

## 3. REDUNDANT / DUAL SYSTEMS

### DUAL-1 · Two telemetry pipelines
| Aspect | `logger.py` | `telemetry.py` |
|---|---|---|
| Env var | `APPLICATIONINSIGHTS_CONNECTION_STRING` | `APPINSIGHTS_CONNECTION_STRING` |
| SDK | `azure-monitor-opentelemetry-exporter` (OpenTelemetry) | `opencensus-ext-azure` (Opencensus) |
| Attachment point | `logging.getLogger("jarvis")` | `logging.getLogger("jarvis")` |
| Used by | All modules via `get_logger()` | `main.py`, `planner.py`, `executor.py` |

- **Issue:** Both attach handlers to the same logger tree. Logs are sent to App Insights **twice** if both env vars are set.
- **Action:** Keep `logger.py` (OpenTelemetry is the modern standard). Remove `telemetry.py`. Update `main.py`, `planner.py`, `executor.py` to drop `tlog` imports. Remove `opencensus-ext-azure` from `requirements.txt`. Consolidate env vars to `APPLICATIONINSIGHTS_CONNECTION_STRING`.

### DUAL-2 · Duplicate environment variables in `.env.example`
| Canonical | Duplicate (unused) |
|---|---|
| `AZURE_OPENAI_API_KEY` | `AZURE_OPENAI_KEY` |
| `AZURE_SEARCH_API_KEY` | `AZURE_SEARCH_KEY` |
| `AZURE_SEARCH_INDEX_NAME` | `AZURE_SEARCH_INDEX` |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | `AZURE_OPENAI_DEPLOYMENT` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `APPINSIGHTS_CONNECTION_STRING` |
| `USE_AZURE_SEARCH` | `USE_AZURE_VECTOR` |

- **Action:** Remove duplicates from `.env.example`, keep only the canonical ones used by `config.py`

---

## 4. ARCHITECTURAL GAPS

### GAP-1 · Learning results never persisted
- **File:** `app/learning/behavior_analyzer.py`
- **Issue:** `analyze()` writes patterns to `state["learning"]` (in-memory dict). These are returned in the response metadata but **never saved to the database**. Next conversation starts with zero behavioral context.
- **Impact:** All personalization patterns are ephemeral.
- **Recommendation:** After `analyze()`, wire the workflow's `_node_learn` to call `memory.store_behavior_pattern()` for each detected pattern (the method already exists).

### GAP-2 · `context_needed` written but never read
- **File:** `app/state/agent_state.py` (PlannerOutput), `app/agents/planner/planner.py`
- **Issue:** Planner populates `context_needed` list, but no downstream node reads or acts on it (e.g., retriever doesn't use it for a second retrieval pass).
- **Impact:** Low — cosmetic unused field. No runtime harm.
- **Recommendation:** Leave as-is; useful if iterative retrieval is added later.

### GAP-3 · Telemetry gap in retriever
- **File:** `app/agents/retriever/retriever.py`
- **Issue:** Planner and executor log to the telemetry logger (`tlog`), but retriever does not.
- **Impact:** Retrieval operations are not surfaced in Application Insights event stream.
- **Recommendation:** Resolved by DUAL-1 fix — once telemetry.py is removed, all modules use `logger.py` uniformly.

---

## 5. WORKFLOW GRAPH VALIDATION

The LangGraph in `workflow.py` was validated against the architecture diagram:

| Path | Route | Nodes traversed | Status |
|---|---|---|---|
| Simple answer | `safety → retrieve → plan(answer) → execute → respond` | 5 | **Correct** |
| Multi-step plan | `safety → retrieve → plan(plan) → decompose → execute → respond` | 6 | **Correct** |
| Action (tool use) | `safety → retrieve → plan(action) → decompose → action_plan → confirm → execute → learn → respond` | 9 | **Correct** |
| Safety blocked | `safety(error) → respond` | 2 | **Correct** |

All routing functions (`_route_after_safety`, `_route_after_plan`, `_route_after_decompose`, `_route_after_execute`) return correct branch keys. No orphan nodes or unreachable states.

---

## 6. AZURE INTEGRATION VERIFICATION

| Component | Integrated? | Details |
|---|---|---|
| `azure_llm.py` — `get_openai_client()` | **Yes** | Used by all 5 agents (planner, executor, retriever, task_decomposer, action_planner) |
| `azure_llm.py` — `get_llm()` | **No** | Never called. Dead code. |
| `azure_search.py` — `azure_search()` | **Yes** | Called by `retriever.py` when `settings.app.use_azure_search` is true |
| `telemetry.py` — `configure_telemetry()` | **Yes** | Called in `main.py` at startup |
| `telemetry.py` — `get_telemetry_logger()` | **Yes** | Used by `planner.py` and `executor.py` |
| `config.py` — `AzureBlobConfig` | **Partial** | Config exists. `blob_url` stored in Document model but no upload-to-blob code exists. |
| `config.py` — `AzureDocIntelligenceConfig` | **Partial** | Config exists. `_extract_text()` in api_server.py uses PyMuPDF/python-docx, not Doc Intelligence. |

---

## 7. MEMORY SYSTEM VERIFICATION

| Method | Defined in | Called by | Status |
|---|---|---|---|
| `get_user_context()` | `memory_manager.py` | — | Defined, not called (agents use `assemble_context` via retriever) |
| `assemble_context()` | `memory_manager.py` | `retriever.py` | **Active** |
| `store_memory()` | `memory_manager.py` | — | Defined, **never called** |
| `store_behavior_pattern()` | `memory_manager.py` | — | Defined, **never called** |
| `save_conversation()` | `memory_manager.py` → `structured_db.py` | `workflow._node_respond` | **Active** |
| Flashcard/Quiz/StudyPlan methods | `memory_manager.py` → `structured_db.py` | — | **Dead code** |

---

## 8. CLEANUP ACTIONS APPLIED

All items marked [DONE] have been applied in this audit pass:

- [DONE] BUG-1: Fix `store_document_chunks()` call in api_server.py
- [DONE] BUG-2: Fix `create_task` priority type
- [DONE] BUG-3: Remove `target_count` from habit creation
- [DONE] BUG-4: Parse `remind_at` string to datetime
- [DONE] DEAD-1: Delete `app/orchestrator/` directory
- [DONE] DEAD-2: Remove flashcard/quiz/study_plan dead code from memory_manager.py and structured_db.py
- [DONE] DEAD-3: Remove `get_llm()` from azure_llm.py  
- [DONE] DEAD-5: Remove `use_azure_vector` from config
- [DONE] DUAL-1: Remove telemetry.py, consolidate to logger.py only
- [DONE] DUAL-2: Clean up duplicate env vars in .env.example
- [DONE] Remove `opencensus-ext-azure` from requirements.txt

### Deferred (not applied):
- DEAD-4: `store_memory()` / `store_behavior_pattern()` kept — correctly implemented, useful API
- GAP-1: Wiring learning persistence — requires design decision on what/when to persist
- GAP-2: `context_needed` — kept for future iterative retrieval
