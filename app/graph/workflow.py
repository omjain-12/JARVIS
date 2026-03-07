"""
LangGraph Workflow — the declarative state-graph that drives request processing.

This module defines a LangGraph StateGraph where:
- Each NODE wraps an async agent function (safety, retriever, planner, …).
- EDGES encode the pipeline order and conditional routing.
- The compiled graph is exposed via `build_workflow()` for use by the API layer.

The graph mirrors the sequential pipeline in the Orchestrator but adds:
- Conditional branching (e.g. short-circuit on safety failure).
- Potential for parallel fan-out in future iterations.
- Visual graph inspection via LangGraph Studio.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph

from app.agents.executor.executor import ExecutorAgent
from app.agents.planner.action_planner import ActionPlanner
from app.agents.planner.planner import PlannerAgent
from app.agents.planner.task_decomposer import TaskDecomposer
from app.agents.retriever.retriever import RetrieverAgent
from app.learning.behavior_analyzer import BehaviorAnalyzer
from app.memory.memory_manager import MemoryManager
from app.safety.safety_check import run_safety_check
from app.state.agent_state import AgentState, add_log_entry, create_initial_state
from app.toolbox.toolbox import Toolbox
from app.tools.habit_tracker_tool import set_memory_manager as set_habit_mm
from app.tools.reminder_tool import set_memory_manager as set_reminder_mm
from app.utils.logger import get_logger

logger = get_logger("workflow")


# ═══════════════════════════════════════════════════════════════════════════════
# Node names
# ═══════════════════════════════════════════════════════════════════════════════
SAFETY = "safety_check"
RETRIEVE = "retrieve"
PLAN = "plan"
DECOMPOSE = "decompose"
ACTION_PLAN = "action_plan"
CONFIRM = "confirm"
EXECUTE = "execute"
LEARN = "learn"
RESPOND = "respond"


# ═══════════════════════════════════════════════════════════════════════════════
# JarvisWorkflow — wrapper that builds and holds the compiled LangGraph
# ═══════════════════════════════════════════════════════════════════════════════


class JarvisWorkflow:
    """
    Encapsulates the full LangGraph-based JARVIS pipeline.

    Usage::

        wf = JarvisWorkflow()
        await wf.initialize()
        result = await wf.run("What should I study today?", user_id="u1")
    """

    def __init__(self) -> None:
        # Core systems
        self.memory = MemoryManager()
        self.toolbox = Toolbox()

        # Agents — populated during initialize()
        self.retriever: Optional[RetrieverAgent] = None
        self.planner: Optional[PlannerAgent] = None
        self.task_decomposer: Optional[TaskDecomposer] = None
        self.action_planner: Optional[ActionPlanner] = None
        self.executor: Optional[ExecutorAgent] = None
        self.behavior_analyzer: Optional[BehaviorAnalyzer] = None

        # The compiled LangGraph application
        self._app = None
        self._initialized = False

    # ── Initialization ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize memory, tools, agents, and compile the graph."""
        logger.info("Initializing JarvisWorkflow …", event_type="workflow_init")

        # Memory
        await self.memory.initialize()

        # Toolbox
        self.toolbox.register_defaults()
        set_reminder_mm(self.memory)
        set_habit_mm(self.memory)

        tools_desc = self.toolbox.get_tools_description()

        # Agents
        self.retriever = RetrieverAgent(self.memory)
        self.planner = PlannerAgent(tools_description=tools_desc)
        self.task_decomposer = TaskDecomposer()
        self.action_planner = ActionPlanner(tools_description=tools_desc)
        self.executor = ExecutorAgent(self.memory, self.toolbox)
        self.behavior_analyzer = BehaviorAnalyzer()

        # Build & compile the graph
        self._app = self._build_graph()
        self._initialized = True

        logger.info("JarvisWorkflow initialized and graph compiled", event_type="workflow_ready")

    # ── Graph Construction ──────────────────────────────────────────────────

    def _build_graph(self):
        """
        Construct the LangGraph StateGraph and return the compiled app.

        Graph topology::

            START
              │
              ▼
            [safety_check] ──(error)──▶ [respond] ──▶ END
              │ (ok)
              ▼
            [retrieve]
              │
              ▼
            [plan]
              │
              ▼
            [decompose]
              │
              ▼
            [action_plan]
              │
              ▼
            [confirm]
              │
              ▼
            [execute]
              │
              ▼
            [learn]
              │
              ▼
            [respond] ──▶ END
        """
        graph = StateGraph(dict)  # Use plain dict for flexible TypedDict compat

        # ── Register nodes ───────────────────────────────────────────────
        graph.add_node(SAFETY, self._node_safety)
        graph.add_node(RETRIEVE, self._node_retrieve)
        graph.add_node(PLAN, self._node_plan)
        graph.add_node(DECOMPOSE, self._node_decompose)
        graph.add_node(ACTION_PLAN, self._node_action_plan)
        graph.add_node(CONFIRM, self._node_confirm)
        graph.add_node(EXECUTE, self._node_execute)
        graph.add_node(LEARN, self._node_learn)
        graph.add_node(RESPOND, self._node_respond)

        # ── Entry point ──────────────────────────────────────────────────
        graph.set_entry_point(SAFETY)

        # ── Edges ────────────────────────────────────────────────────────
        # After safety: branch on error
        graph.add_conditional_edges(
            SAFETY,
            self._route_after_safety,
            {
                "safe": RETRIEVE,
                "blocked": RESPOND,
            },
        )

        # Linear chain: retrieve → plan → decompose → action_plan → confirm
        graph.add_edge(RETRIEVE, PLAN)
        graph.add_edge(PLAN, DECOMPOSE)
        graph.add_edge(DECOMPOSE, ACTION_PLAN)
        graph.add_edge(ACTION_PLAN, CONFIRM)

        # After confirmation: execute
        graph.add_edge(CONFIRM, EXECUTE)

        # After execution: learn → respond → END
        graph.add_edge(EXECUTE, LEARN)
        graph.add_edge(LEARN, RESPOND)
        graph.add_edge(RESPOND, END)

        return graph.compile()

    # ── Routing Functions ───────────────────────────────────────────────────

    @staticmethod
    def _route_after_safety(state: dict) -> str:
        """Decide whether to continue or short-circuit after safety check."""
        system = state.get("system", {})
        if system.get("error"):
            return "blocked"
        return "safe"

    # ── Node Implementations ────────────────────────────────────────────────
    # Each node is a thin async wrapper around the corresponding agent.  It
    # receives the full state dict and returns the (possibly updated) state.

    async def _node_safety(self, state: dict) -> dict:
        """Run safety checks on user input."""
        logger.log_state_transition("init", "safety")
        try:
            state = await run_safety_check(state)
        except Exception as e:
            logger.error(f"Safety node error: {e}", exc_info=True)
            state = add_log_entry(state, "safety", "error", str(e))
            system = {**state.get("system", {}), "error": f"Safety check failed: {e}"}
            state = {**state, "system": system}
        return state

    async def _node_retrieve(self, state: dict) -> dict:
        """Retrieve context from memory systems."""
        logger.log_state_transition("safety", "retrieval")
        try:
            state = await self.retriever.retrieve(state)
        except Exception as e:
            logger.error(f"Retrieval node error: {e}", exc_info=True)
            state = add_log_entry(state, "retriever", "error", str(e))
        return state

    async def _node_plan(self, state: dict) -> dict:
        """Generate a high-level strategy."""
        logger.log_state_transition("retrieval", "planning")
        try:
            state = await self.planner.plan(state)
        except Exception as e:
            logger.error(f"Planning node error: {e}", exc_info=True)
            state = add_log_entry(state, "planner", "error", str(e))
            # Set sensible defaults so downstream nodes can still run
            planner_output = state.get("planner_output", {})
            planner_output = {
                **planner_output,
                "decision": "answer",
                "output_format": "text",
                "goal": state.get("user_request", {}).get("raw_input", ""),
            }
            state = {**state, "planner_output": planner_output}
        return state

    async def _node_decompose(self, state: dict) -> dict:
        """Decompose strategy into discrete tasks."""
        logger.log_state_transition("planning", "task_decomposition")
        try:
            state = await self.task_decomposer.decompose(state)
        except Exception as e:
            logger.error(f"Decompose node error: {e}", exc_info=True)
            state = add_log_entry(state, "task_decomposer", "error", str(e))
        return state

    async def _node_action_plan(self, state: dict) -> dict:
        """Translate tasks into executable tool instructions."""
        logger.log_state_transition("task_decomposition", "action_planning")
        try:
            state = await self.action_planner.plan_actions(state)
        except Exception as e:
            logger.error(f"Action plan node error: {e}", exc_info=True)
            state = add_log_entry(state, "action_planner", "error", str(e))
        return state

    async def _node_confirm(self, state: dict) -> dict:
        """
        Handle action confirmation.

        In production, this node would emit a human-in-the-loop interrupt.
        For now, it auto-confirms any pending actions.
        """
        if state.get("system", {}).get("requires_confirmation"):
            state = add_log_entry(
                state, "orchestrator", "auto_confirmed",
                "Auto-confirmed (confirmation UI not yet implemented)",
            )
            logger.info("Action auto-confirmed", event_type="auto_confirm")
        return state

    async def _node_execute(self, state: dict) -> dict:
        """Execute tool calls and generate output."""
        logger.log_state_transition("action_planning", "execution")
        try:
            state = await self.executor.execute(state)
        except Exception as e:
            logger.error(f"Execution node error: {e}", exc_info=True)
            state = add_log_entry(state, "executor", "error", str(e))
            execution = {
                **state.get("execution", {}),
                "execution_status": "failed",
            }
            state = {**state, "execution": execution}
        return state

    async def _node_learn(self, state: dict) -> dict:
        """Analyse user behaviour and update learning state."""
        logger.log_state_transition("execution", "learning")
        try:
            state = await self.behavior_analyzer.analyze(state)
        except Exception as e:
            logger.error(f"Learning node error: {e}", exc_info=True)
            state = add_log_entry(state, "learning", "error", str(e))
        return state

    async def _node_respond(self, state: dict) -> dict:
        """
        Terminal node — save conversation and mark processing complete.

        The response payload is already built by the Executor; this node
        performs housekeeping (conversation save) and logs completion.
        """
        try:
            await self._save_conversation(state)
        except Exception as e:
            logger.warning(f"Failed to save conversation: {e}")

        state = add_log_entry(state, "workflow", "response_ready", "Graph execution complete")
        system = {**state.get("system", {}), "current_stage": "response"}
        state = {**state, "system": system}
        return state

    # ── Run the Graph ───────────────────────────────────────────────────────

    async def run(
        self,
        user_input: str,
        user_id: str = "default_user",
        session_id: str = "",
    ) -> Dict[str, Any]:
        """
        Process a user request through the compiled LangGraph.

        Args:
            user_input: Raw user text.
            user_id: Authenticated user ID.
            session_id: Optional session ID.

        Returns:
            Standardised response dict (same shape as Orchestrator.process).
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()

        # Create initial state
        state = create_initial_state(user_input, user_id, session_id)
        request_id = state["system"]["request_id"]

        logger.set_context(request_id=request_id, user_id=user_id)
        logger.info(f"Graph processing: {user_input[:100]}", event_type="graph_start")

        try:
            # Invoke the compiled graph
            final_state = await self._app.ainvoke(state)

            total_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Graph completed in {total_ms:.0f}ms",
                event_type="graph_complete",
                metadata={"total_ms": total_ms},
            )

            return self._build_response(final_state, start_time)

        except Exception as e:
            logger.error(f"Graph execution error: {e}", exc_info=True)
            system = {**state["system"], "error": f"An internal error occurred: {e}"}
            state = {**state, "system": system}
            return self._build_response(state, start_time)

    # ── Response Builders ───────────────────────────────────────────────────

    @staticmethod
    def _build_response(state: dict, start_time: float) -> Dict[str, Any]:
        """
        Build a unified response dict from the final graph state.

        Works for both success and error states.
        """
        total_ms = (time.time() - start_time) * 1000
        system = state.get("system", {})
        response = state.get("response", {})
        planner = state.get("planner_output", {})
        execution = state.get("execution", {})
        learning = state.get("learning", {})

        error = system.get("error", "")
        status = "error" if error else "success"

        return {
            "status": status,
            "request_id": system.get("request_id", ""),
            "response": {
                "text": error if error else response.get("final_output", ""),
                "format": response.get("response_format", "text"),
                "structured_data": response.get("structured_data"),
            },
            "metadata": {
                "request_type": system.get("request_type", ""),
                "decision": planner.get("decision", ""),
                "goal": planner.get("goal", ""),
                "tools_used": [
                    tc.get("tool", "") for tc in execution.get("tool_calls", [])
                ],
                "patterns_detected": learning.get("patterns_detected", []),
                "total_time_ms": round(total_ms, 2),
            },
            "logs": state.get("logs", []),
        }

    # ── Conversation Persistence ────────────────────────────────────────────

    async def _save_conversation(self, state: dict) -> None:
        """Persist the conversation turn to the database."""
        user_id = state["system"]["user_id"]
        session_id = state["system"]["session_id"]
        user_input = state.get("user_request", {}).get("raw_input", "")
        response_text = state.get("response", {}).get("final_output", "")

        await self.memory.save_conversation(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=user_input,
        )
        await self.memory.save_conversation(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=response_text,
            metadata={
                "request_type": state["system"].get("request_type", ""),
                "request_id": state["system"].get("request_id", ""),
            },
        )

    # ── Shutdown ────────────────────────────────────────────────────────────

    async def shutdown(self) -> None:
        """Release resources held by the workflow."""
        logger.info("Shutting down JarvisWorkflow …", event_type="workflow_shutdown")
        await self.memory.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience builder — for use by main.py / tests
# ═══════════════════════════════════════════════════════════════════════════════


def build_workflow() -> JarvisWorkflow:
    """
    Factory that returns an *uninitialised* JarvisWorkflow.

    Call ``await wf.initialize()`` before first use.
    """
    return JarvisWorkflow()
