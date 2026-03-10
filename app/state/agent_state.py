"""Agent State — the shared typed state object that flows through the entire agent pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict


# ── Sub-State Types ──


class SystemState(TypedDict, total=False):
    """System-level metadata for the current request lifecycle."""
    session_id: str
    request_id: str
    user_id: str
    timestamp: str
    current_stage: str  
    request_type: str   
    requires_confirmation: bool
    error: str


class UserRequest(TypedDict, total=False):
    """Captured and validated user request."""
    raw_input: str
    validated_input: str
    intent: str  # question | advice | planning | execution | unknown


class StructuredMemory(TypedDict, total=False):
    """Data from the structured (relational) database."""
    tasks: List[Dict[str, Any]]
    reminders: List[Dict[str, Any]]
    habits: List[Dict[str, Any]]
    contacts: List[Dict[str, Any]]
    calendar: List[Dict[str, Any]]
    preferences: List[Dict[str, Any]]
    goals: List[Dict[str, Any]]
    documents: List[Dict[str, Any]]


class VectorMemory(TypedDict, total=False):
    """Data from the vector (semantic) database."""
    notes: List[Dict[str, Any]]
    conversation_history: List[Dict[str, Any]]
    behavior_patterns: List[Dict[str, Any]]
    past_decisions: List[Dict[str, Any]]
    knowledge_chunks: List[Dict[str, Any]]


class MemoryContext(TypedDict, total=False):
    """Combined memory context assembled by the Retriever."""
    structured_memory: StructuredMemory
    vector_memory: VectorMemory
    retrieval_summary: str


class PlannerOutput(TypedDict, total=False):
    """Strategy produced by the Planner agent."""
    goal: str
    strategy: str
    reasoning_steps: List[str]
    decision: str  # answer | plan | action
    context_needed: List[str]
    tools_needed: List[str]
    output_format: str  # text | action_result


class TaskPlan(TypedDict, total=False):
    """Decomposed tasks from the Task Decomposer."""
    tasks: List[Dict[str, Any]]
    # Each task: { task_id, description, priority, estimated_time, status }


class ActionPlan(TypedDict, total=False):
    """Executable action instructions from the Action Planner."""
    actions: List[Dict[str, Any]]
    # Each action: { action_id, tool_name, parameters, requires_confirmation, status }


class ExecutionResult(TypedDict, total=False):
    """Results from the Executor agent."""
    tool_calls: List[Dict[str, Any]]
    # Each: { tool, parameters, status, result }
    execution_status: str  # pending | running | completed | failed
    generated_output: Any  # The final generated content


class LearningState(TypedDict, total=False):
    """Insights from the Learning/Behavior layer."""
    behavior_analysis: str
    patterns_detected: List[str]
    extracted_facts: List[Dict[str, Any]]
    preference_updates: List[Dict[str, Any]]


class ResponseState(TypedDict, total=False):
    """Final assembled response to the user."""
    final_output: str
    response_format: str  # text | action_result | confirmation_request
    structured_data: Any  # For structured outputs (tool results, etc.)


class LogEntry(TypedDict, total=False):
    """A single log entry in the agent trace."""
    timestamp: str
    agent: str
    event: str
    details: str


# ── Master Agent State ──


class AgentState(TypedDict, total=False):
    """The master state object that flows through the entire agent pipeline."""
    system: SystemState
    user_request: UserRequest
    memory_context: MemoryContext
    planner_output: PlannerOutput
    task_plan: TaskPlan
    action_plan: ActionPlan
    execution: ExecutionResult
    learning: LearningState
    response: ResponseState
    logs: List[LogEntry]


# ── Factory Function ──


def create_initial_state(
    user_input: str,
    user_id: str = "default_user",
    session_id: str = "",
) -> AgentState:
    """Create a fresh AgentState for a new user request."""
    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    return AgentState(
        system=SystemState(
            session_id=session_id or str(uuid.uuid4()),
            request_id=request_id,
            user_id=user_id,
            timestamp=now,
            current_stage="safety",
            request_type="",
            requires_confirmation=False,
            error="",
        ),
        user_request=UserRequest(
            raw_input=user_input,
            validated_input="",
            intent="unknown",
        ),
        memory_context=MemoryContext(
            structured_memory=StructuredMemory(
                tasks=[], reminders=[], habits=[], contacts=[],
                calendar=[], preferences=[], goals=[], documents=[],
            ),
            vector_memory=VectorMemory(
                notes=[], conversation_history=[],
                behavior_patterns=[], past_decisions=[],
                knowledge_chunks=[],
            ),
            retrieval_summary="",
        ),
        planner_output=PlannerOutput(
            goal="",
            strategy="",
            reasoning_steps=[],
            decision="",
            context_needed=[],
            tools_needed=[],
            output_format="text",
        ),
        task_plan=TaskPlan(tasks=[]),
        action_plan=ActionPlan(actions=[]),
        execution=ExecutionResult(
            tool_calls=[],
            execution_status="pending",
            generated_output=None,
        ),
        learning=LearningState(
            behavior_analysis="",
            patterns_detected=[],
            extracted_facts=[],
            preference_updates=[],
        ),
        response=ResponseState(
            final_output="",
            response_format="text",
            structured_data=None,
        ),
        logs=[
            LogEntry(
                timestamp=now,
                agent="system",
                event="state_initialized",
                details=f"New request from user {user_id}",
            )
        ],
    )


def add_log_entry(
    state: AgentState,
    agent: str,
    event: str,
    details: str = "",
) -> AgentState:
    """Append a log entry to the state's log list and return updated state."""
    entry = LogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent=agent,
        event=event,
        details=details,
    )
    logs = list(state.get("logs", []))
    logs.append(entry)
    return {**state, "logs": logs}