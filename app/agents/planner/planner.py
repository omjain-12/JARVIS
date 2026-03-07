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
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("planner")

# ── Planner System Prompt ──

PLANNER_SYSTEM_PROMPT = """You are the Planner Agent of JARVIS, an intelligent personal AI assistant.

Your role is to ANALYZE the user's request and produce a STRATEGY. You do NOT execute actions.

## Your Responsibilities:
1. Understand what the user wants
2. Analyze the retrieved context
3. Classify the request type
4. Create a step-by-step strategy
5. Decide what tools are needed (if any)
6. Decide the output format

## Request Types:
- "reasoning" — The user wants analysis, explanation, or insight. No tools needed.
- "planning" — The user wants a plan, schedule, or structured output (flashcards, quiz, study plan, summary).
- "action" — The user wants to perform a real-world action (send email, set reminder, log habit).

## Available Tools:
{tools_description}

## Output Format:
You MUST respond with ONLY a valid JSON object. No markdown, no explanation outside the JSON.

```json
{{
    "goal": "One sentence describing what the user wants",
    "request_type": "reasoning | planning | action",
    "strategy": "Brief description of the approach",
    "reasoning_steps": ["step 1", "step 2", "step 3"],
    "decision": "answer | plan | action",
    "context_needed": ["list of topics or data points needed"],
    "tools_needed": ["list of tool names needed, empty if none"],
    "output_format": "text | summary | flashcards | quiz | study_plan | action_result"
}}
```

## Rules:
- NEVER fabricate information. Only use what is in the retrieved context.
- If you don't have enough context, set decision to "answer" and explain what's missing.
- For action requests, always list the specific tools needed.
- Be precise and structured in your reasoning steps.
- If the user is asking a simple question, keep the strategy simple.
"""


class PlannerAgent:
    """
    The Planner Agent — produces strategies for handling user requests.

    The Planner uses Azure OpenAI to reason about the user's intent,
    the available context, and the best approach to fulfill the request.
    """

    def __init__(self, tools_description: str = ""):
        self._llm_client = None
        self.tools_description = tools_description

    def _get_llm_client(self):
        """Lazy-initialize Azure OpenAI client."""
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

        # Vector memory — knowledge chunks
        vm = context.get("vector_memory", {})
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

        # Update state
        planner_output = {
            "goal": strategy.get("goal", query),
            "strategy": strategy.get("strategy", ""),
            "reasoning_steps": strategy.get("reasoning_steps", []),
            "decision": strategy.get("decision", "answer"),
            "context_needed": strategy.get("context_needed", []),
            "tools_needed": strategy.get("tools_needed", []),
            "output_format": strategy.get("output_format", "text"),
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
