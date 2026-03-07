"""
Task Decomposer — converts a Planner strategy into concrete tasks.

Takes the high-level strategy from the Planner and breaks it down into
specific, ordered, actionable tasks that the Executor can work on.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List

from app.state.agent_state import AgentState, add_log_entry
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("task_decomposer")

DECOMPOSER_SYSTEM_PROMPT = """You are the Task Decomposer of JARVIS, an intelligent AI assistant.

Your role is to take a STRATEGY and break it into CONCRETE TASKS.

## Rules:
- Each task must be specific and actionable
- Tasks must be ordered by priority (highest first)
- Each task must have a clear description
- Estimate the time needed for each task
- Keep tasks atomic — one action per task

## Output Format:
Respond with ONLY a valid JSON object:

```json
{
    "tasks": [
        {
            "task_id": "unique_id",
            "description": "What needs to be done",
            "priority": 1,
            "estimated_time": "30 seconds",
            "status": "pending",
            "depends_on": null
        }
    ]
}
```
"""


class TaskDecomposer:
    """
    Decomposes planner strategies into ordered task lists.
    """

    def __init__(self):
        self._llm_client = None

    def _get_llm_client(self):
        if self._llm_client is None:
            try:
                from openai import AzureOpenAI
                self._llm_client = AzureOpenAI(
                    azure_endpoint=settings.azure_openai.endpoint,
                    api_key=settings.azure_openai.api_key,
                    api_version=settings.azure_openai.api_version,
                )
            except Exception as e:
                logger.warning(f"LLM client not available: {e}")
                return None
        return self._llm_client

    async def decompose(self, state: AgentState) -> AgentState:
        """
        Decompose the planner strategy into tasks.

        For simple reasoning requests, creates a single "generate response" task.
        For complex planning/action requests, uses the LLM to decompose.

        Args:
            state: Current AgentState with planner_output populated.

        Returns:
            Updated AgentState with task_plan populated.
        """
        logger.set_context(
            request_id=state.get("system", {}).get("request_id", ""),
            user_id=state.get("system", {}).get("user_id", ""),
            agent_name="task_decomposer",
        )
        logger.log_agent_start("task_decomposer")
        start_time = time.time()

        planner_output = state.get("planner_output", {})
        decision = planner_output.get("decision", "answer")
        request_type = state.get("system", {}).get("request_type", "reasoning")

        state = add_log_entry(state, "task_decomposer", "decomposition_start",
                              f"Decision: {decision}, Type: {request_type}")

        if decision == "answer" or request_type == "reasoning":
            # Simple reasoning — single task
            tasks = [{
                "task_id": str(uuid.uuid4())[:8],
                "description": f"Generate response: {planner_output.get('goal', 'answer query')}",
                "priority": 1,
                "estimated_time": "5 seconds",
                "status": "pending",
            }]
        else:
            # Complex — use LLM to decompose
            tasks = await self._llm_decompose(planner_output)
            if not tasks:
                # Fallback
                tasks = [{
                    "task_id": str(uuid.uuid4())[:8],
                    "description": planner_output.get("goal", "Execute request"),
                    "priority": 1,
                    "estimated_time": "10 seconds",
                    "status": "pending",
                }]

        task_plan = {"tasks": tasks}
        system = {**state.get("system", {}), "current_stage": "action_planning"}
        state = {**state, "task_plan": task_plan, "system": system}

        state = add_log_entry(state, "task_decomposer", "decomposition_complete",
                              f"Generated {len(tasks)} tasks")

        duration_ms = (time.time() - start_time) * 1000
        logger.log_agent_end("task_decomposer", f"{len(tasks)} tasks", duration_ms)

        return state

    async def _llm_decompose(self, planner_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use the LLM to decompose a strategy into tasks."""
        client = self._get_llm_client()
        if not client:
            return []

        try:
            user_message = f"""## Strategy to decompose:

Goal: {planner_output.get('goal', '')}
Strategy: {planner_output.get('strategy', '')}
Reasoning Steps: {json.dumps(planner_output.get('reasoning_steps', []))}
Tools Needed: {json.dumps(planner_output.get('tools_needed', []))}
Output Format: {planner_output.get('output_format', 'text')}

Break this strategy into concrete, ordered tasks."""

            response = client.chat.completions.create(
                model=settings.azure_openai.chat_deployment,
                messages=[
                    {"role": "system", "content": DECOMPOSER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=800,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content.strip()
            result = json.loads(content)
            tasks = result.get("tasks", [])

            # Ensure each task has required fields
            for task in tasks:
                task.setdefault("task_id", str(uuid.uuid4())[:8])
                task.setdefault("description", "")
                task.setdefault("priority", 0)
                task.setdefault("estimated_time", "")
                task.setdefault("status", "pending")

            return tasks

        except Exception as e:
            logger.error(f"LLM decomposition failed: {e}", exc_info=True)
            return []
