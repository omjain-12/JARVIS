"""
Orchestrator — the central controller of the JARVIS system.

The Orchestrator:
1. Receives validated user requests
2. Initializes agent state
3. Routes requests through the agent pipeline
4. Manages the flow: Safety → Retriever → Planner → TaskDecomposer → ActionPlanner → Executor → Learning
5. Handles errors gracefully at every stage
6. Produces the final response
7. Saves conversation history

This is the ONLY component that produces final output.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

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
from app.tools.reminder_tool import set_memory_manager as set_reminder_mm
from app.tools.habit_tracker_tool import set_memory_manager as set_habit_mm
from app.utils.logger import get_logger

logger = get_logger("orchestrator")


class Orchestrator:
    """
    Central controller that manages the entire agent pipeline.

    Usage:
        orchestrator = Orchestrator()
        await orchestrator.initialize()
        result = await orchestrator.process("What should I focus on today?", user_id="user123")
    """

    def __init__(self):
        # Core systems
        self.memory = MemoryManager()
        self.toolbox = Toolbox()

        # Agents (initialized after toolbox is ready)
        self.retriever: Optional[RetrieverAgent] = None
        self.planner: Optional[PlannerAgent] = None
        self.task_decomposer: Optional[TaskDecomposer] = None
        self.action_planner: Optional[ActionPlanner] = None
        self.executor: Optional[ExecutorAgent] = None
        self.behavior_analyzer: Optional[BehaviorAnalyzer] = None

        self._initialized = False

    async def initialize(self):
        """Initialize all systems and agents."""
        logger.info("Initializing JARVIS Orchestrator...", event_type="orchestrator_init")

        # Initialize memory
        await self.memory.initialize()

        # Initialize toolbox
        self.toolbox.register_defaults()

        # Inject memory manager into tools that need it
        set_reminder_mm(self.memory)
        set_habit_mm(self.memory)

        # Get tools description for the planner
        tools_desc = self.toolbox.get_tools_description()

        # Initialize agents
        self.retriever = RetrieverAgent(self.memory)
        self.planner = PlannerAgent(tools_description=tools_desc)
        self.task_decomposer = TaskDecomposer()
        self.action_planner = ActionPlanner(tools_description=tools_desc)
        self.executor = ExecutorAgent(self.memory, self.toolbox)
        self.behavior_analyzer = BehaviorAnalyzer()

        self._initialized = True
        logger.info("JARVIS Orchestrator initialized successfully", event_type="orchestrator_ready")

    async def process(
        self,
        user_input: str,
        user_id: str = "default_user",
        session_id: str = "",
    ) -> Dict[str, Any]:
        """
        Process a user request through the entire agent pipeline.

        Pipeline:
        1. Create initial state
        2. Safety check
        3. Retriever (context assembly)
        4. Planner (strategy generation)
        5. Task Decomposer (task list)
        6. Action Planner (tool instructions)
        7. Executor (output generation + tool execution)
        8. Learning (behavior analysis)
        9. Save conversation + return response

        Args:
            user_input: The raw user input.
            user_id: Authenticated user ID.
            session_id: Optional session ID.

        Returns:
            Dict with the final response, metadata, and any structured data.
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()

        # 1. Create initial state
        state = create_initial_state(user_input, user_id, session_id)
        request_id = state["system"]["request_id"]

        logger.set_context(request_id=request_id, user_id=user_id)
        logger.info(f"Processing request: {user_input[:100]}", event_type="request_start")

        try:
            # 2. Safety Check
            logger.log_state_transition("init", "safety")
            state = await run_safety_check(state)

            if state["system"].get("error"):
                return self._build_error_response(state, start_time)

            # 3. Retriever — fetch context
            logger.log_state_transition("safety", "retrieval")
            state = await self.retriever.retrieve(state)

            # 4. Planner — generate strategy
            logger.log_state_transition("retrieval", "planning")
            state = await self.planner.plan(state)

            # 5. Task Decomposer — split strategy into tasks
            logger.log_state_transition("planning", "task_decomposition")
            state = await self.task_decomposer.decompose(state)

            # 6. Action Planner — generate tool instructions
            logger.log_state_transition("task_decomposition", "action_planning")
            state = await self.action_planner.plan_actions(state)

            # 7. Confirmation check (for action requests)
            if state["system"].get("requires_confirmation"):
                # In a production system, this would pause and wait for user confirmation
                # For now, we auto-confirm and log it
                state = add_log_entry(state, "orchestrator", "auto_confirmed",
                                      "Action auto-confirmed (confirmation UI not implemented)")
                logger.info("Action auto-confirmed", event_type="auto_confirm")

            # 8. Executor — generate output + execute tools
            logger.log_state_transition("action_planning", "execution")
            state = await self.executor.execute(state)

            # 9. Learning — analyze behavior
            logger.log_state_transition("execution", "learning")
            state = await self.behavior_analyzer.analyze(state)

            # 10. Save conversation history
            await self._save_conversation(state)

            # Build and return final response
            response = self._build_success_response(state, start_time)

            total_time = (time.time() - start_time) * 1000
            logger.info(
                f"Request completed in {total_time:.0f}ms",
                event_type="request_complete",
                metadata={"total_ms": total_time, "request_type": state["system"].get("request_type", "")},
            )

            return response

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            state = add_log_entry(state, "orchestrator", "pipeline_error", str(e))
            system = {**state["system"], "error": f"An internal error occurred: {str(e)}"}
            state = {**state, "system": system}
            return self._build_error_response(state, start_time)

    def _build_success_response(self, state: AgentState, start_time: float) -> Dict[str, Any]:
        """Build the final success response dict."""
        total_ms = (time.time() - start_time) * 1000
        response = state.get("response", {})
        planner = state.get("planner_output", {})
        execution = state.get("execution", {})
        learning = state.get("learning", {})

        return {
            "status": "success",
            "request_id": state["system"]["request_id"],
            "response": {
                "text": response.get("final_output", ""),
                "format": response.get("response_format", "text"),
                "structured_data": response.get("structured_data"),
            },
            "metadata": {
                "request_type": state["system"].get("request_type", ""),
                "decision": planner.get("decision", ""),
                "goal": planner.get("goal", ""),
                "tools_used": [tc.get("tool", "") for tc in execution.get("tool_calls", [])],
                "patterns_detected": learning.get("patterns_detected", []),
                "total_time_ms": round(total_ms, 2),
            },
            "logs": state.get("logs", []),
        }

    def _build_error_response(self, state: AgentState, start_time: float) -> Dict[str, Any]:
        """Build an error response dict."""
        total_ms = (time.time() - start_time) * 1000
        error_msg = state["system"].get("error", "Unknown error occurred")

        return {
            "status": "error",
            "request_id": state["system"]["request_id"],
            "response": {
                "text": error_msg,
                "format": "text",
                "structured_data": None,
            },
            "metadata": {
                "request_type": state["system"].get("request_type", ""),
                "total_time_ms": round(total_ms, 2),
            },
            "logs": state.get("logs", []),
        }

    async def _save_conversation(self, state: AgentState):
        """Save the conversation turn to the database."""
        try:
            user_id = state["system"]["user_id"]
            session_id = state["system"]["session_id"]
            user_input = state["user_request"]["raw_input"]
            response_text = state.get("response", {}).get("final_output", "")

            # Save user message
            await self.memory.save_conversation(
                user_id=user_id,
                session_id=session_id,
                role="user",
                content=user_input,
            )

            # Save assistant response
            await self.memory.save_conversation(
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                content=response_text,
                metadata={
                    "request_type": state["system"].get("request_type", ""),
                    "request_id": state["system"]["request_id"],
                },
            )
        except Exception as e:
            logger.warning(f"Failed to save conversation: {e}")

    async def shutdown(self):
        """Gracefully shut down all systems."""
        logger.info("Shutting down JARVIS Orchestrator...", event_type="orchestrator_shutdown")
        await self.memory.close()
