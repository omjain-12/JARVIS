"""
Executor Agent — generates outputs and performs actions.

The Executor:
1. Receives strategy + context + action plan
2. Generates the appropriate output format:
   - Text answers
   - Summaries
   - Flashcards
   - Quizzes
   - Study plans
3. Executes tool calls (email, SMS, reminders, etc.)
4. Validates all outputs before returning
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from app.memory.memory_manager import MemoryManager
from app.state.agent_state import AgentState, add_log_entry
from app.toolbox.toolbox import Toolbox
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("executor")

# ── Output Generator Prompts ──

ANSWER_PROMPT = """You are JARVIS, an intelligent personal AI assistant.

Generate a helpful, accurate, and grounded answer to the user's question.

## Rules:
- ONLY use information from the provided context
- If the context doesn't contain the answer, say so honestly
- Be clear, concise, and well-structured
- Use bullet points or numbered lists when appropriate
- Cite the source document when possible

## Context:
{context}

## User Question:
{query}

Provide your answer:"""

SUMMARY_PROMPT = """You are JARVIS, an intelligent personal AI assistant.

Generate a comprehensive summary of the provided content.

## Rules:
- Include all key points and main ideas
- Organize with clear section headings
- Highlight actionable takeaways
- Be faithful to the source material — no hallucination
- End with a "Key Takeaways" section

## Content to Summarize:
{context}

## User Request:
{query}

Generate the summary:"""

FLASHCARD_PROMPT = """You are JARVIS, an intelligent personal AI assistant.

Generate study flashcards from the provided content.

## Rules:
- Each flashcard must have a clear question (front) and answer (back)
- Questions should test understanding, not trivial recall
- Answers must be grounded in the source material
- Assign difficulty: easy, medium, or hard
- Generate 8-15 flashcards covering the key concepts

## Output Format:
Respond with ONLY a valid JSON object:
```json
{{
    "title": "Flashcard set title",
    "topic": "Topic name",
    "cards": [
        {{
            "front": "Question text",
            "back": "Answer text",
            "difficulty": "easy | medium | hard"
        }}
    ]
}}
```

## Source Content:
{context}

## User Request:
{query}

Generate the flashcards:"""

QUIZ_PROMPT = """You are JARVIS, an intelligent personal AI assistant.

Generate a quiz from the provided content.

## Rules:
- Each question must have exactly 4 options
- Exactly one option must be correct
- Wrong options (distractors) must be plausible but clearly wrong
- Questions should test genuine comprehension
- Include a brief explanation for each correct answer
- Generate 5-10 questions

## Output Format:
Respond with ONLY a valid JSON object:
```json
{{
    "title": "Quiz title",
    "topic": "Topic name",
    "questions": [
        {{
            "question": "Question text",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "Option A",
            "explanation": "Why this is correct"
        }}
    ]
}}
```

## Source Content:
{context}

## User Request:
{query}

Generate the quiz:"""

STUDY_PLAN_PROMPT = """You are JARVIS, an intelligent personal AI assistant.

Generate a structured study plan based on the user's request and available information.

## Rules:
- Create a day-by-day schedule
- Each day should have specific topics and activities
- Include review/revision sessions
- Balance the workload across days
- Include milestones and checkpoints
- Be realistic about time estimates

## Output Format:
Respond with ONLY a valid JSON object:
```json
{{
    "title": "Study Plan title",
    "total_days": 7,
    "schedule": {{
        "Day 1": {{
            "topics": ["Topic 1", "Topic 2"],
            "activities": ["Read chapter 1", "Practice problems"],
            "estimated_hours": 3,
            "milestone": "Complete fundamentals"
        }}
    }}
}}
```

## Available Context:
{context}

## User Request:
{query}

Generate the study plan:"""


class ExecutorAgent:
    """
    The Executor Agent — generates outputs and executes tool actions.

    Supports multiple output formats:
    - text: Direct text answers
    - summary: Structured summaries
    - flashcards: Question/answer card sets
    - quiz: Multiple choice quizzes
    - study_plan: Day-by-day study schedules
    - action_result: Results from tool execution
    """

    def __init__(self, memory_manager: MemoryManager, toolbox: Toolbox):
        self.memory = memory_manager
        self.toolbox = toolbox
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

    def _build_context_text(self, state: AgentState) -> str:
        """Extract plain text context from the state for LLM prompts."""
        context = state.get("memory_context", {})
        parts = []

        # Knowledge chunks
        chunks = context.get("vector_memory", {}).get("knowledge_chunks", [])
        for chunk in chunks:
            source = chunk.get("source_filename", "unknown")
            content = chunk.get("content", "")
            if content:
                parts.append(f"[Source: {source}]\n{content}")

        # Structured data summary
        sm = context.get("structured_memory", {})
        if sm.get("tasks"):
            parts.append(f"User's tasks: {json.dumps(sm['tasks'][:5], default=str)}")
        if sm.get("habits"):
            parts.append(f"User's habits: {json.dumps(sm['habits'][:5], default=str)}")
        if sm.get("goals"):
            parts.append(f"User's goals: {json.dumps(sm['goals'][:3], default=str)}")

        return "\n\n---\n\n".join(parts) if parts else "No specific context available."

    async def execute(self, state: AgentState) -> AgentState:
        """
        Main execution pipeline — the workflow graph node function.

        Routes to the appropriate generator based on the planner's output_format,
        or executes tool calls if the request type is 'action'.

        Args:
            state: Current AgentState with all previous stages complete.

        Returns:
            Updated AgentState with execution results and response populated.
        """
        logger.set_context(
            request_id=state.get("system", {}).get("request_id", ""),
            user_id=state.get("system", {}).get("user_id", ""),
            agent_name="executor",
        )
        logger.log_agent_start("executor")
        start_time = time.time()

        planner_output = state.get("planner_output", {})
        output_format = planner_output.get("output_format", "text")
        request_type = state.get("system", {}).get("request_type", "reasoning")
        action_plan = state.get("action_plan", {})

        state = add_log_entry(state, "executor", "execution_start",
                              f"Format: {output_format}, Type: {request_type}")

        query = state.get("user_request", {}).get("validated_input", "")
        context_text = self._build_context_text(state)
        user_id = state.get("system", {}).get("user_id", "")

        # Execute tool calls if any
        tool_results = []
        actions = action_plan.get("actions", [])
        for action in actions:
            tool_name = action.get("tool_name", "none")
            if tool_name and tool_name != "none":
                params = action.get("parameters", {})
                # Inject user_id if the tool needs it
                if "user_id" in self.toolbox.get_tool(tool_name).parameters if self.toolbox.get_tool(tool_name) else {}:
                    params["user_id"] = user_id
                result = await self.toolbox.execute(tool_name, params)
                tool_results.append({
                    "tool": tool_name,
                    "parameters": params,
                    "status": result.get("status", "unknown"),
                    "result": result.get("message", str(result)),
                })

        # Generate output based on format
        generated_output = None
        response_text = ""
        response_format = output_format
        structured_data = None

        if output_format == "summary":
            response_text = await self._generate_summary(query, context_text)
        elif output_format == "flashcards":
            flashcard_data = await self._generate_flashcards(query, context_text)
            if flashcard_data:
                structured_data = flashcard_data
                # Save to database
                await self.memory.save_flashcard_set(
                    user_id=user_id,
                    title=flashcard_data.get("title", "Flashcards"),
                    topic=flashcard_data.get("topic", ""),
                    cards=flashcard_data.get("cards", []),
                )
                response_text = f"Generated {len(flashcard_data.get('cards', []))} flashcards: {flashcard_data.get('title', '')}"
            else:
                response_text = "Failed to generate flashcards. Please try again."
                response_format = "text"
        elif output_format == "quiz":
            quiz_data = await self._generate_quiz(query, context_text)
            if quiz_data:
                structured_data = quiz_data
                await self.memory.save_quiz(
                    user_id=user_id,
                    title=quiz_data.get("title", "Quiz"),
                    topic=quiz_data.get("topic", ""),
                    questions=quiz_data.get("questions", []),
                )
                response_text = f"Generated quiz with {len(quiz_data.get('questions', []))} questions: {quiz_data.get('title', '')}"
            else:
                response_text = "Failed to generate quiz. Please try again."
                response_format = "text"
        elif output_format == "study_plan":
            plan_data = await self._generate_study_plan(query, context_text)
            if plan_data:
                structured_data = plan_data
                await self.memory.save_study_plan(
                    user_id=user_id,
                    title=plan_data.get("title", "Study Plan"),
                    schedule=plan_data.get("schedule", {}),
                )
                response_text = f"Generated {plan_data.get('total_days', 0)}-day study plan: {plan_data.get('title', '')}"
            else:
                response_text = "Failed to generate study plan. Please try again."
                response_format = "text"
        elif output_format == "action_result":
            if tool_results:
                results_summary = "\n".join(
                    f"- {r['tool']}: {r['result']}" for r in tool_results
                )
                response_text = f"Actions completed:\n{results_summary}"
            else:
                response_text = "No actions were executed."
        else:
            # Default: text answer
            response_text = await self._generate_answer(query, context_text)

        # Build execution result
        execution = {
            "tool_calls": tool_results,
            "execution_status": "completed",
            "generated_output": structured_data,
        }

        response = {
            "final_output": response_text,
            "response_format": response_format,
            "structured_data": structured_data,
        }

        system = {**state.get("system", {}), "current_stage": "learning"}

        state = {**state, "execution": execution, "response": response, "system": system}
        state = add_log_entry(state, "executor", "execution_complete",
                              f"Format: {response_format}, Output length: {len(response_text)}")

        duration_ms = (time.time() - start_time) * 1000
        logger.log_agent_end("executor", f"Generated {response_format}", duration_ms)

        return state

    # ── Output Generators ──

    async def _generate_answer(self, query: str, context: str) -> str:
        """Generate a text answer using the LLM."""
        prompt = ANSWER_PROMPT.format(context=context, query=query)
        return await self._call_llm_text(prompt)

    async def _generate_summary(self, query: str, context: str) -> str:
        """Generate a structured summary."""
        prompt = SUMMARY_PROMPT.format(context=context, query=query)
        return await self._call_llm_text(prompt)

    async def _generate_flashcards(self, query: str, context: str) -> Optional[Dict[str, Any]]:
        """Generate a flashcard set."""
        prompt = FLASHCARD_PROMPT.format(context=context, query=query)
        result = await self._call_llm_json(prompt)

        if result:
            # Validate flashcards
            cards = result.get("cards", [])
            valid_cards = [
                c for c in cards
                if c.get("front", "").strip() and c.get("back", "").strip()
            ]
            if valid_cards:
                result["cards"] = valid_cards
                return result

        return None

    async def _generate_quiz(self, query: str, context: str) -> Optional[Dict[str, Any]]:
        """Generate a quiz."""
        prompt = QUIZ_PROMPT.format(context=context, query=query)
        result = await self._call_llm_json(prompt)

        if result:
            # Validate questions
            questions = result.get("questions", [])
            valid_questions = []
            for q in questions:
                if (
                    q.get("question", "").strip()
                    and len(q.get("options", [])) == 4
                    and q.get("correct_answer", "").strip()
                ):
                    valid_questions.append(q)

            if valid_questions:
                result["questions"] = valid_questions
                return result

        return None

    async def _generate_study_plan(self, query: str, context: str) -> Optional[Dict[str, Any]]:
        """Generate a study plan."""
        prompt = STUDY_PLAN_PROMPT.format(context=context, query=query)
        result = await self._call_llm_json(prompt)

        if result and result.get("schedule"):
            return result

        return None

    # ── LLM Call Helpers ──

    async def _call_llm_text(self, prompt: str) -> str:
        """Call the LLM and return text response."""
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
            return f"I encountered an error generating a response: {str(e)}"

    async def _call_llm_json(self, prompt: str, retries: int = 3) -> Optional[Dict[str, Any]]:
        """Call the LLM and parse JSON response with retries."""
        client = self._get_llm_client()
        if not client:
            return None

        for attempt in range(retries):
            try:
                start = time.time()
                response = client.chat.completions.create(
                    model=settings.azure_openai.chat_deployment,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2000,
                    response_format={"type": "json_object"},
                )
                latency = (time.time() - start) * 1000

                logger.log_llm_call(
                    model=settings.azure_openai.chat_deployment,
                    input_tokens=response.usage.prompt_tokens if response.usage else 0,
                    output_tokens=response.usage.completion_tokens if response.usage else 0,
                    latency_ms=latency,
                )

                content = response.choices[0].message.content.strip()
                return json.loads(content)

            except json.JSONDecodeError:
                logger.warning(f"JSON parse failed, attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"LLM JSON call failed, attempt {attempt + 1}: {e}", exc_info=True)

        return None
