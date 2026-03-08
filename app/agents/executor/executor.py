"""
Executor Agent — generates text responses and executes tool actions.

The Executor:
1. Generates text answers using the LLM
2. Executes tool calls via the Toolbox
3. Formats the final response

The Executor does NOT reason — that is the Planner's job.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List

from app.memory.memory_manager import MemoryManager
from app.state.agent_state import AgentState, add_log_entry
from app.toolbox.toolbox import Toolbox
from app.utils.azure_llm import get_openai_client
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("executor")

# ── Prompt ──

ANSWER_PROMPT = """You are JARVIS, a personal AI assistant.
Answer using ONLY the provided context. Be concise and use bullet points when helpful.
If context is insufficient, say so.

Context:
{context}

Question:
{query}"""


class ExecutorAgent:
    """
    Generates text responses, executes tool actions, and formats output.
    """

    def __init__(self, memory_manager: MemoryManager, toolbox: Toolbox):
        self.memory = memory_manager
        self.toolbox = toolbox

    @staticmethod
    def _get_llm_client():
        """Get the shared Azure OpenAI client from the central factory."""
        return get_openai_client()

    # ── Main entry point ──

    async def execute(self, state: AgentState) -> AgentState:
        """
        Main execution pipeline — the workflow graph node function.

        Routes based on planner decision:
        - answer/plan: generate text response
        - action (confirmed): execute tools then format
        - action (unconfirmed): return confirmation request
        """
        logger.set_context(
            request_id=state.get("system", {}).get("request_id", ""),
            user_id=state.get("system", {}).get("user_id", ""),
            agent_name="executor",
        )
        logger.log_agent_start("executor")
        start_time = time.time()

        planner_output = state.get("planner_output", {})
        decision = planner_output.get("decision", "answer")
        action_plan = state.get("action_plan", {})
        system = state.get("system", {})

        state = add_log_entry(state, "executor", "execution_start", f"Decision: {decision}")

        # Check confirmation gate for action requests
        if decision == "action" and system.get("requires_confirmation") and not system.get("confirmed"):
            state = self._build_confirmation_response(state, action_plan)
            logger.log_agent_end("executor", "confirmation_request", (time.time() - start_time) * 1000)
            return state

        # Execute based on decision
        if decision == "action":
            state = await self._handle_action(state, action_plan)
        else:
            state = await self._handle_text(state)

        duration_ms = (time.time() - start_time) * 1000
        response_format = state.get("response", {}).get("response_format", "text")
        logger.log_agent_end("executor", f"Generated {response_format}", duration_ms)
        return state

    # ── Text response handler ──

    async def _handle_text(self, state: AgentState) -> AgentState:
        """Generate a text response using the LLM."""
        query = state.get("user_request", {}).get("validated_input", "")
        context_text = self._build_context_text(state)

        response_text = await self.generate_text_response(query, context_text)

        return self.format_response(state, response_text, "text", tool_calls=[])

    # ── Action handler ──

    async def _handle_action(self, state: AgentState, action_plan: dict) -> AgentState:
        """Execute tool actions and format the results."""
        user_id = state.get("system", {}).get("user_id", "")
        raw_input = state.get("user_request", {}).get("raw_input", "")
        tool_results = await self.execute_actions(action_plan, user_id, raw_input)

        lines = [f"- {r['tool']}: {r['result']}" for r in tool_results]
        response_text = "Actions completed:\n" + "\n".join(lines) if lines else "No actions were executed."

        return self.format_response(state, response_text, "action_result", tool_calls=tool_results)

    # ── Confirmation response ──

    @staticmethod
    def _build_confirmation_response(state: AgentState, action_plan: dict) -> AgentState:
        """Return a structured confirmation request instead of executing."""
        actions = action_plan.get("actions", [])
        confirmable = [a for a in actions if a.get("requires_confirmation")]

        confirm_items = []
        for a in confirmable:
            confirm_items.append({
                "type": "confirmation",
                "message": a.get("task_description", "Confirm this action?"),
                "action_id": a.get("action_id", ""),
            })

        # Use the first confirmable action for the top-level message
        top_message = confirmable[0].get("task_description", "Confirm action?") if confirmable else "Confirm action?"

        response = {
            "final_output": top_message,
            "response_format": "confirmation_request",
            "structured_data": {
                "type": "confirmation",
                "message": top_message,
                "action_id": confirmable[0].get("action_id", "") if confirmable else "",
                "pending_actions": confirm_items,
            },
        }
        execution = {"tool_calls": [], "execution_status": "awaiting_confirmation", "generated_output": None}
        system = {**state.get("system", {}), "current_stage": "learning"}

        state = {**state, "execution": execution, "response": response, "system": system}
        state = add_log_entry(state, "executor", "awaiting_confirmation",
                              f"{len(confirmable)} actions pending confirmation")
        return state

    # ── Core methods ──

    async def generate_text_response(self, query: str, context: str) -> str:
        """Generate a text answer using the LLM."""
        prompt = ANSWER_PROMPT.format(context=context, query=query)

        client = self._get_llm_client()
        if not client:
            return "I'm sorry, but the AI service is currently unavailable. Please try again later."

        try:
            start = time.time()
            response = client.chat.completions.create(
                model=settings.azure_openai.chat_deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=2000,
            )
            latency = (time.time() - start) * 1000

            logger.log_llm_call(
                model=settings.azure_openai.chat_deployment,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                latency_ms=latency,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"LLM text generation failed: {e}", exc_info=True)
            err = str(e)
            if "404" in err and "Resource not found" in err:
                return (
                    "I cannot reach the configured Azure OpenAI deployment. "
                    "Please verify AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT, "
                    "and AZURE_OPENAI_EMBEDDING_DEPLOYMENT in your .env file."
                )
            return "I encountered an error generating a response. Please try again."

    @staticmethod
    def _extract_emails(text: str) -> List[str]:
        """Extract email addresses from user input, preserving order."""
        if not text:
            return []
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        deduped: List[str] = []
        seen = set()
        for email in emails:
            key = email.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(email)
        return deduped

    @staticmethod
    def _extract_phone_numbers(text: str) -> List[str]:
        """Extract phone numbers from user input in a permissive but practical format."""
        if not text:
            return []
        # Matches common international/local formats with optional separators.
        candidates = re.findall(r"\+?\d[\d\s\-()]{7,}\d", text)
        cleaned: List[str] = []
        seen = set()
        for c in candidates:
            normalized = re.sub(r"[\s\-()]", "", c)
            if len(re.sub(r"\D", "", normalized)) < 10:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)
        return cleaned

    def _sanitize_action_params(self, tool_name: str, params: Dict[str, Any], raw_input: str) -> Dict[str, Any]:
        """Enforce literal entity preservation for high-risk contact channels."""
        safe = dict(params or {})
        quoted_emails = self._extract_emails(raw_input)
        quoted_phones = self._extract_phone_numbers(raw_input)

        if tool_name == "email_tool":
            if quoted_emails:
                provided = str(safe.get("recipient", "")).strip()
                if provided and provided.lower() not in {e.lower() for e in quoted_emails}:
                    logger.warning(
                        "Email recipient corrected to user-provided literal",
                        event_type="param_guardrail",
                        metadata={"provided": provided, "used": quoted_emails[0]},
                    )
                safe["recipient"] = quoted_emails[0]

        if tool_name in {"sms_tool", "whatsapp_tool"}:
            if quoted_phones:
                provided = str(safe.get("phone_number", "")).strip()
                if provided and provided not in set(quoted_phones):
                    logger.warning(
                        "Phone number corrected to user-provided literal",
                        event_type="param_guardrail",
                        metadata={"provided": provided, "used": quoted_phones[0]},
                    )
                safe["phone_number"] = quoted_phones[0]

        return safe

    async def execute_actions(self, action_plan: dict, user_id: str, raw_input: str = "") -> List[Dict[str, Any]]:
        """Execute all tool calls from the action plan via the Toolbox."""
        tool_results = []
        actions = action_plan.get("actions", [])

        for action in actions:
            tool_name = action.get("tool_name", "none")
            if not tool_name or tool_name == "none":
                continue

            params = action.get("parameters", {})
            params = self._sanitize_action_params(tool_name, params, raw_input)
            tool = self.toolbox.get_tool(tool_name)
            if tool and "user_id" in tool.parameters:
                params["user_id"] = user_id

            result = await self.toolbox.execute(tool_name, params)
            status = result.get("status", "unknown")
            tool_results.append({
                "tool": tool_name,
                "parameters": params,
                "status": status,
                "result": result.get("message", str(result)),
            })

            # Telemetry — logged via logger
            logger.log_tool_call(tool_name, params, status, result.get("message", str(result)))

        return tool_results

    @staticmethod
    def format_response(
        state: AgentState,
        response_text: str,
        response_format: str,
        tool_calls: List[Dict[str, Any]],
    ) -> AgentState:
        """Build the final execution and response state dicts."""
        execution = {
            "tool_calls": tool_calls,
            "execution_status": "completed",
            "generated_output": None,
        }
        response = {
            "final_output": response_text,
            "response_format": response_format,
            "structured_data": None,
        }
        system = {**state.get("system", {}), "current_stage": "learning"}

        state = {**state, "execution": execution, "response": response, "system": system}
        state = add_log_entry(state, "executor", "execution_complete",
                              f"Format: {response_format}, Output length: {len(response_text)}")
        return state

    # ── Helpers ──

    def _build_context_text(self, state: AgentState) -> str:
        """Extract plain text context from the state for LLM prompts."""
        context = state.get("memory_context", {})
        parts = []

        chunks = context.get("vector_memory", {}).get("knowledge_chunks", [])
        for chunk in chunks:
            source = chunk.get("source_filename", "unknown")
            content = chunk.get("content", "")
            if content:
                parts.append(f"[Source: {source}]\n{content}")

        sm = context.get("structured_memory", {})
        if sm.get("tasks"):
            parts.append(f"User's tasks: {json.dumps(sm['tasks'][:5], default=str)}")
        if sm.get("habits"):
            parts.append(f"User's habits: {json.dumps(sm['habits'][:5], default=str)}")
        if sm.get("goals"):
            parts.append(f"User's goals: {json.dumps(sm['goals'][:3], default=str)}")

        return "\n\n---\n\n".join(parts) if parts else "No specific context available."
