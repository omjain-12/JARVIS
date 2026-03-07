"""
Behavior Analyzer — learning layer that analyzes outcomes and updates the user model.

The Learning Layer:
1. Analyzes task completion and execution outcomes
2. Detects behavioral patterns
3. Updates user preferences
4. Produces insights for future personalization
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from app.state.agent_state import AgentState, add_log_entry
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("behavior_analyzer")


class BehaviorAnalyzer:
    """
    Analyzes system outcomes and user behavior to improve personalization.

    Tracks:
    - Task completion rates
    - Tool usage patterns
    - User interaction patterns
    - Preference signals
    """

    def __init__(self):
        self._llm_client = None
        # In-memory pattern store (production: persist to DB)
        self._patterns: Dict[str, List[str]] = {}
        self._interaction_count: Dict[str, int] = {}

    def _get_llm_client(self):
        if self._llm_client is None:
            try:
                from openai import AzureOpenAI
                self._llm_client = AzureOpenAI(
                    azure_endpoint=settings.azure_openai.endpoint,
                    api_key=settings.azure_openai.api_key,
                    api_version=settings.azure_openai.api_version,
                )
            except Exception:
                return None
        return self._llm_client

    async def analyze(self, state: AgentState) -> AgentState:
        """
        Analyze the completed request and extract learning signals.

        This is the final processing step before the response is returned.

        Steps:
        1. Analyze the request type and outcome
        2. Track interaction patterns
        3. Detect behavioral trends
        4. Update the learning state

        Args:
            state: Completed AgentState with execution results.

        Returns:
            Updated AgentState with learning insights.
        """
        logger.set_context(
            request_id=state.get("system", {}).get("request_id", ""),
            user_id=state.get("system", {}).get("user_id", ""),
            agent_name="behavior_analyzer",
        )
        logger.log_agent_start("behavior_analyzer")
        start_time = time.time()

        user_id = state.get("system", {}).get("user_id", "")
        request_type = state.get("system", {}).get("request_type", "")
        execution = state.get("execution", {})
        planner_output = state.get("planner_output", {})

        state = add_log_entry(state, "behavior_analyzer", "analysis_start",
                              f"Analyzing request type: {request_type}")

        # 1. Track interaction count
        self._interaction_count[user_id] = self._interaction_count.get(user_id, 0) + 1
        interaction_num = self._interaction_count[user_id]

        # 2. Analyze execution outcome
        tool_calls = execution.get("tool_calls", [])
        execution_status = execution.get("execution_status", "unknown")

        patterns_detected = []
        preference_updates = []
        behavior_analysis = ""

        # 3. Extract patterns from the request
        output_format = planner_output.get("output_format", "text")
        decision = planner_output.get("decision", "answer")

        # Track request type distribution
        user_patterns = self._patterns.setdefault(user_id, [])
        user_patterns.append(f"{request_type}:{output_format}")

        # Keep last 50 interaction patterns
        if len(user_patterns) > 50:
            user_patterns[:] = user_patterns[-50:]

        # 4. Simple pattern detection
        if len(user_patterns) >= 5:
            # Detect most common request types
            type_counts: Dict[str, int] = {}
            for p in user_patterns:
                rtype = p.split(":")[0]
                type_counts[rtype] = type_counts.get(rtype, 0) + 1

            most_common = max(type_counts, key=type_counts.get)
            if type_counts[most_common] >= 3:
                patterns_detected.append(f"User frequently makes {most_common} requests")

            # Detect preferred output format
            format_counts: Dict[str, int] = {}
            for p in user_patterns:
                parts = p.split(":")
                if len(parts) > 1:
                    fmt = parts[1]
                    format_counts[fmt] = format_counts.get(fmt, 0) + 1

            if format_counts:
                preferred_format = max(format_counts, key=format_counts.get)
                if format_counts[preferred_format] >= 3:
                    patterns_detected.append(f"User prefers {preferred_format} format")
                    preference_updates.append({
                        "type": "preferred_format",
                        "value": preferred_format,
                    })

        # 5. Analyze tool usage
        if tool_calls:
            tool_names = [tc.get("tool", "") for tc in tool_calls]
            successful = [tc for tc in tool_calls if tc.get("status") == "success"]
            failed = [tc for tc in tool_calls if tc.get("status") == "error"]

            if failed:
                patterns_detected.append(f"Tool failures detected: {[f['tool'] for f in failed]}")

            behavior_analysis = (
                f"Interaction #{interaction_num}. "
                f"Request type: {request_type}, Format: {output_format}. "
                f"Tools used: {tool_names}. "
                f"Success rate: {len(successful)}/{len(tool_calls)}."
            )
        else:
            behavior_analysis = (
                f"Interaction #{interaction_num}. "
                f"Request type: {request_type}, Format: {output_format}. "
                f"No tool calls made."
            )

        # 6. Update learning state
        learning = {
            "behavior_analysis": behavior_analysis,
            "patterns_detected": patterns_detected,
            "preference_updates": preference_updates,
        }

        system = {**state.get("system", {}), "current_stage": "response"}
        state = {**state, "learning": learning, "system": system}
        state = add_log_entry(state, "behavior_analyzer", "analysis_complete",
                              f"Patterns: {len(patterns_detected)}, Prefs: {len(preference_updates)}")

        duration_ms = (time.time() - start_time) * 1000
        logger.log_agent_end("behavior_analyzer", behavior_analysis, duration_ms)

        return state
