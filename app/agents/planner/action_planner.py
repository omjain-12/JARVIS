"""Action Planner — converts decomposed tasks into tool-executable instructions."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List

from app.state.agent_state import AgentState, add_log_entry
from app.utils.azure_llm import get_openai_client
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("action_planner")

ACTION_PLANNER_PROMPT = """You are the Action Planner of JARVIS.
Convert TASKS into TOOL CALL INSTRUCTIONS.

Available Tools:
{tools_description}

Rules:
- Specify exact tool name and all required parameters
- If no tool needed, set tool_name to "none"
- Mark side-effect actions as requires_confirmation: true
- For knowledge_store_tool memory saves, set requires_confirmation: false unless the user explicitly asked for confirmation.
- Never alter user-provided literals such as email addresses, phone numbers, dates, times, URLs, or quoted text.
- If the user provided an explicit recipient/contact value, copy it exactly into parameters.

Respond with ONLY valid JSON:
{{
    "actions": [
        {{
            "action_id": "unique_id",
            "task_description": "what this action does",
            "tool_name": "tool_name or none",
            "parameters": {{}},
            "requires_confirmation": false
        }}
    ]
}}
"""


class ActionPlanner:
    """Converts tasks into executable tool call instructions."""

    def __init__(self, tools_description: str = ""):
        self.tools_description = tools_description

    @staticmethod
    def _get_llm_client():
        """Get the shared Azure OpenAI client from the central factory."""
        return get_openai_client()

    async def plan_actions(self, state: AgentState) -> AgentState:
        """Create action instructions from tasks."""
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
            raw_input = state.get("user_request", {}).get("raw_input", "")

            user_message = f"""## Context:
User ID: {user_id}
Goal: {planner_output.get('goal', '')}
Strategy: {planner_output.get('strategy', '')}
Tools Needed: {json.dumps(planner_output.get('tools_needed', []))}
Original User Request: {raw_input}

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
