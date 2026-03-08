"""
Planner Agent — the reasoning brain of the system.

The Planner:
1. Analyzes the user request + retrieved context
2. Classifies the request type (reasoning, planning, action)
3. Produces a strategy with reasoning steps
4. Decides what output format is needed
5. Does NOT execute actions directly
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict

from app.state.agent_state import AgentState, add_log_entry
from app.utils.azure_llm import get_openai_client
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("planner")

# ── Planner System Prompt ──

PLANNER_SYSTEM_PROMPT = """You are the Planner of JARVIS, a personal AI assistant.
Analyze the request and produce a strategy. Do NOT execute actions.

Request Types:
- reasoning: analysis, explanation, insight (no tools)
- planning: plan, schedule, organized response
- action: real-world action or memory-write action (email, reminder, habit, storing user info)

Available Tools:
{tools_description}

Respond with ONLY valid JSON:
{{
    "goal": "what the user wants",
    "request_type": "reasoning | planning | action",
    "strategy": "approach description",
    "reasoning_steps": ["step 1", "step 2"],
    "decision": "answer | plan | action",
    "tools_needed": [],
    "output_format": "text | action_result"
}}

Rules:
- Only use retrieved context. Never fabricate.
- If context is insufficient, decision=answer and explain.
- For actions, list specific tools needed.
- If user says "remember", "save this", "note this", or shares personal details/preferences for future use, choose request_type=action and include knowledge_store_tool in tools_needed.
- Preserve user-provided literals exactly (emails, phone numbers, dates, times, URLs, quoted values). Never rewrite them.
"""


class PlannerAgent:
    """
    The Planner Agent — produces strategies for handling user requests.

    The Planner uses Azure OpenAI to reason about the user's intent,
    the available context, and the best approach to fulfill the request.
    """

    def __init__(self, tools_description: str = ""):
        self.tools_description = tools_description

    @staticmethod
    def _get_llm_client():
        """Get the shared Azure OpenAI client from the central factory."""
        return get_openai_client()

    def _build_context_summary(self, state: AgentState) -> str:
        """Build a text summary of the retrieved context for the LLM."""
        context = state.get("memory_context", {})
        parts = []

        # Structured memory summary
        sm = context.get("structured_memory", {})
        if sm.get("tasks"):
            parts.append(f"Active tasks: {json.dumps(sm['tasks'][:5], default=str)}")
        if sm.get("reminders"):
            parts.append(f"Pending reminders: {json.dumps(sm['reminders'][:5], default=str)}")
        if sm.get("habits"):
            parts.append(f"Tracked habits: {json.dumps(sm['habits'][:5], default=str)}")
        if sm.get("documents"):
            parts.append(f"Documents: {json.dumps(sm['documents'][:5], default=str)}")
        if sm.get("goals"):
            parts.append(f"Goals: {json.dumps(sm['goals'][:3], default=str)}")

        # User preferences and learned facts
        if sm.get("preferences"):
            prefs = sm["preferences"]
            prefs_dict = prefs[0] if isinstance(prefs, list) and prefs else prefs
            if isinstance(prefs_dict, dict):
                profile = prefs_dict.get("profile", {})
                if profile:
                    parts.append(f"User profile: {json.dumps(profile, default=str)}")
        learned_facts = sm.get("learned_facts", [])
        if learned_facts:
            fact_lines = [f"- {f.get('summary', '')}" for f in learned_facts[-10:] if isinstance(f, dict)]
            if fact_lines:
                parts.append("Learned user facts:\n" + "\n".join(fact_lines))

        # Behavior patterns from vector memory
        vm = context.get("vector_memory", {})
        behavior_patterns = vm.get("behavior_patterns", [])
        if behavior_patterns:
            pattern_lines = [f"- {p.get('content', '')}" for p in behavior_patterns[:10]]
            if pattern_lines:
                parts.append("Detected behavior patterns:\n" + "\n".join(pattern_lines))

        # Knowledge chunks
        chunks = vm.get("knowledge_chunks", [])
        if chunks:
            chunk_texts = []
            for i, c in enumerate(chunks[:5]):
                source = c.get("source_filename", "unknown")
                content = c.get("content", "")[:500]
                chunk_texts.append(f"[Source: {source}] {content}")
            parts.append("Relevant knowledge:\n" + "\n---\n".join(chunk_texts))

        # Conversation history
        conv = vm.get("conversation_history", [])
        if conv:
            recent = conv[-3:]
            conv_text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent)
            parts.append(f"Recent conversation:\n{conv_text}")

        retrieval_summary = context.get("retrieval_summary", "")
        if retrieval_summary:
            parts.insert(0, retrieval_summary)

        return "\n\n".join(parts) if parts else "No context available."

    async def plan(self, state: AgentState) -> AgentState:
        """
        Main planning pipeline — the workflow graph node function.

        Steps:
        1. Build context summary from retrieved memory
        2. Call LLM with planner prompt
        3. Parse and validate the strategy output
        4. Store the strategy in state

        Args:
            state: Current AgentState with memory_context populated.

        Returns:
            Updated AgentState with planner_output populated.
        """
        logger.set_context(
            request_id=state.get("system", {}).get("request_id", ""),
            user_id=state.get("system", {}).get("user_id", ""),
            agent_name="planner",
        )
        logger.log_agent_start("planner")
        start_time = time.time()

        query = state.get("user_request", {}).get("validated_input", "")
        context_summary = self._build_context_summary(state)

        state = add_log_entry(state, "planner", "planning_start", f"Query: {query[:100]}")

        # Build the prompt
        system_prompt = PLANNER_SYSTEM_PROMPT.format(
            tools_description=self.tools_description or "No tools available"
        )

        user_message = f"""## User Request:
{query}

## Retrieved Context:
{context_summary}

Analyze this request and produce your strategy as a JSON object."""

        # Call LLM
        strategy = await self._call_llm(system_prompt, user_message)

        if not strategy:
            # Fallback: simple reasoning response
            strategy = {
                "goal": query,
                "request_type": "reasoning",
                "strategy": "Direct response based on available context",
                "reasoning_steps": ["Analyze the user query", "Provide a direct answer"],
                "decision": "answer",
                "context_needed": [],
                "tools_needed": [],
                "output_format": "text",
            }

        # Determine if confirmation is needed (for action requests)
        requires_confirmation = strategy.get("request_type") == "action"

        # Clamp output_format to allowed values
        raw_format = strategy.get("output_format", "text")
        output_format = raw_format if raw_format in ("text", "action_result") else "text"

        # Update state
        planner_output = {
            "goal": strategy.get("goal", query),
            "strategy": strategy.get("strategy", ""),
            "reasoning_steps": strategy.get("reasoning_steps", []),
            "decision": strategy.get("decision", "answer"),
            "context_needed": strategy.get("context_needed", []),
            "tools_needed": strategy.get("tools_needed", []),
            "output_format": output_format,
        }

        system = {
            **state.get("system", {}),
            "current_stage": "task_decomposition",
            "request_type": strategy.get("request_type", "reasoning"),
            "requires_confirmation": requires_confirmation,
        }

        state = {**state, "planner_output": planner_output, "system": system}
        state = add_log_entry(
            state, "planner", "planning_complete",
            f"Decision: {planner_output['decision']}, Type: {strategy.get('request_type', 'reasoning')}"
        )

        duration_ms = (time.time() - start_time) * 1000
        logger.log_planner_decision(
            decision=planner_output["decision"],
            goal=planner_output["goal"],
            strategy=planner_output["strategy"],
            tools_needed=planner_output.get("tools_needed", []),
            latency_ms=duration_ms,
        )
        logger.log_agent_end("planner", f"Decision: {planner_output['decision']}", duration_ms)

        return state

    async def _call_llm(self, system_prompt: str, user_message: str, retries: int = 3) -> dict:
        """Call Azure OpenAI and parse the JSON response, with retries."""
        client = self._get_llm_client()
        if not client:
            return {}

        for attempt in range(retries):
            try:
                start = time.time()
                response = client.chat.completions.create(
                    model=settings.azure_openai.chat_deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.2,
                    max_tokens=1000,
                    response_format={"type": "json_object"},
                )
                latency = (time.time() - start) * 1000

                content = response.choices[0].message.content.strip()

                logger.log_llm_call(
                    model=settings.azure_openai.chat_deployment,
                    input_tokens=response.usage.prompt_tokens if response.usage else 0,
                    output_tokens=response.usage.completion_tokens if response.usage else 0,
                    latency_ms=latency,
                )

                strategy = json.loads(content)
                # Validate required fields
                required = ["goal", "request_type", "decision"]
                if all(k in strategy for k in required):
                    return strategy

                logger.warning(f"Planner output missing required fields, attempt {attempt + 1}")

            except json.JSONDecodeError as e:
                logger.warning(f"Planner JSON parse failed (attempt {attempt + 1}): {e}")
            except Exception as e:
                logger.error(f"Planner LLM call failed (attempt {attempt + 1}): {e}", exc_info=True)

        return {}
