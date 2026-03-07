"""
Action Planner — converts decomposed tasks into tool-executable instructions.

Takes each task from the Task Decomposer and, if it requires tool usage,
generates precise tool call instructions with validated parameters.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List

from app.state.agent_state import AgentState, add_log_entry
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("action_planner")

ACTION_PLANNER_PROMPT = """You are the Action Planner of JARVIS, an intelligent AI assistant.

Your role is to convert TASKS into TOOL CALL INSTRUCTIONS.

## Available Tools:
{tools_description}

## Rules:
- Each action must specify the exact tool name
- All required parameters must be provided
- If a task does NOT need a tool, set tool_name to "none"
- Mark actions that could have side effects as requires_confirmation: true

## Output Format:
Respond with ONLY a valid JSON object:

```json
{{
    "actions": [
        {{
            "action_id": "unique_id",
            "task_description": "What this action accomplishes",
            "tool_name": "tool_name or none",
            "parameters": {{}},
            "requires_confirmation": false
        }}
    ]
}}
```
"""


class ActionPlanner:
    """
    Converts tasks into executable tool call instructions.
    """

    def __init__(self, tools_description: str = ""):
        self._llm_client = None
        self.tools_description = tools_description

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

    async def plan_actions(self, state: AgentState) -> AgentState:
        """
        Create action instructions from tasks.

        For reasoning/planning requests: no tool actions needed, skip to execution.
        For action requests: generate tool call instructions.

        Args:
            state: Current AgentState with task_plan populated.

        Returns:
            Updated AgentState with action_plan populated.
        """
        logger.set_context(
            request_id=state.get("system", {}).get("request_id", ""),
            user_id=state.get("system", {}).get("user_id", ""),
            agent_name="action_planner",
        )
        logger.log_agent_start("action_planner")
        start_time = time.time()

        request_type = state.get("system", {}).get("request_type", "reasoning")
        planner_output = state.get("planner_output", {})
        task_plan = state.get("task_plan", {})
        tools_needed = planner_output.get("tools_needed", [])

        state = add_log_entry(state, "action_planner", "action_planning_start",
                              f"Type: {request_type}, Tools needed: {tools_needed}")

        if request_type in ("reasoning", "planning") and not tools_needed:
            # No tool actions needed — create a "generate" action
            actions = [{
                "action_id": str(uuid.uuid4())[:8],
                "task_description": planner_output.get("goal", "Generate response"),
                "tool_name": "none",
                "parameters": {},
                "requires_confirmation": False,
            }]
        else:
            # Use LLM to plan tool calls
            actions = await self._llm_plan_actions(state)
            if not actions:
                actions = [{
                    "action_id": str(uuid.uuid4())[:8],
                    "task_description": "Fallback: generate response",
                    "tool_name": "none",
                    "parameters": {},
                    "requires_confirmation": False,
                }]

        # Determine if any action needs confirmation
        needs_confirmation = any(a.get("requires_confirmation", False) for a in actions)

        action_plan = {"actions": actions}
        system = {
            **state.get("system", {}),
            "current_stage": "confirmation" if needs_confirmation else "execution",
            "requires_confirmation": needs_confirmation,
        }

        state = {**state, "action_plan": action_plan, "system": system}
        state = add_log_entry(state, "action_planner", "action_planning_complete",
                              f"Generated {len(actions)} actions, confirmation: {needs_confirmation}")

        duration_ms = (time.time() - start_time) * 1000
        logger.log_agent_end("action_planner", f"{len(actions)} actions", duration_ms)

        return state

    async def _llm_plan_actions(self, state: AgentState) -> List[Dict[str, Any]]:
        """Use the LLM to generate tool call instructions."""
        client = self._get_llm_client()
        if not client:
            return []

        try:
            planner_output = state.get("planner_output", {})
            task_plan = state.get("task_plan", {})
            user_id = state.get("system", {}).get("user_id", "")

            user_message = f"""## Context:
User ID: {user_id}
Goal: {planner_output.get('goal', '')}
Strategy: {planner_output.get('strategy', '')}
Tools Needed: {json.dumps(planner_output.get('tools_needed', []))}

## Tasks to convert to actions:
{json.dumps(task_plan.get('tasks', []), indent=2)}

Convert these tasks into precise tool call instructions."""

            prompt = ACTION_PLANNER_PROMPT.format(
                tools_description=self.tools_description or "No tools available"
            )

            response = client.chat.completions.create(
                model=settings.azure_openai.chat_deployment,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content.strip()
            result = json.loads(content)
            actions = result.get("actions", [])

            # Ensure required fields
            for action in actions:
                action.setdefault("action_id", str(uuid.uuid4())[:8])
                action.setdefault("task_description", "")
                action.setdefault("tool_name", "none")
                action.setdefault("parameters", {})
                action.setdefault("requires_confirmation", False)

            return actions

        except Exception as e:
            logger.error(f"LLM action planning failed: {e}", exc_info=True)
            return []
