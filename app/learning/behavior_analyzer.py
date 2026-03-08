"""
Behavior Analyzer — lightweight learning layer.

Tracks:
- Missed reminders (overdue / not completed)
- Habit streaks (consecutive days)
- Frequent tasks / action types
- Time preferences (active hours based on interaction timestamps)
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.state.agent_state import AgentState, add_log_entry
from app.utils.azure_llm import get_openai_client
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("behavior_analyzer")


class BehaviorAnalyzer:
    """Tracks basic behavioral patterns for personalization."""

    def __init__(self, memory_manager=None):
        self._memory = memory_manager
        self._action_log: Dict[str, List[str]] = {}  # user_id → recent action types
        self._interaction_count: Dict[str, int] = {}
        self._hour_log: Dict[str, List[int]] = {}  # user_id → recent interaction hours
        self._loaded_users: set = set()  # track which users had counters loaded

    def _build_learning_text(self, state: AgentState) -> str:
        """Build a compact transcript from current state for fact extraction."""
        user_input = state.get("user_request", {}).get("raw_input", "")
        assistant_output = state.get("response", {}).get("final_output", "")
        history = state.get("memory_context", {}).get("vector_memory", {}).get("conversation_history", [])

        lines: List[str] = []
        if history:
            for msg in history[-6:]:
                role = msg.get("role", "user")
                content = str(msg.get("content", "")).strip()
                if content:
                    lines.append(f"{role}: {content}")

        if user_input:
            lines.append(f"user: {user_input}")
        if assistant_output:
            lines.append(f"assistant: {assistant_output}")

        return "\n".join(lines)

    @staticmethod
    def _deduplicate_facts(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove near-duplicate facts by normalized summary."""
        unique: List[Dict[str, Any]] = []
        seen = set()
        for fact in facts:
            summary = str(fact.get("summary", "")).strip().lower()
            if not summary:
                continue
            if summary in seen:
                continue
            seen.add(summary)
            unique.append(fact)
        return unique

    @staticmethod
    def _is_trivial_message(text: str) -> bool:
        """Return True if the message is too short or generic to learn from."""
        stripped = text.strip().lower()
        if len(stripped) < 5:
            return True
        trivial = {
            "hello", "hi", "hey", "thanks", "thank you", "ok", "okay",
            "yes", "no", "sure", "bye", "goodbye", "good", "great",
            "fine", "cool", "nice", "yep", "nope", "yeah", "nah",
            "got it", "alright", "hmm", "hm", "lol", "haha",
        }
        return stripped in trivial

    async def _extract_useful_facts(self, state: AgentState) -> List[Dict[str, Any]]:
        """Extract durable user facts from chat state using LLM, with regex fallback."""
        user_input = state.get("user_request", {}).get("raw_input", "")
        if self._is_trivial_message(user_input):
            return []

        transcript = self._build_learning_text(state)
        if not transcript.strip():
            return []

        facts: List[Dict[str, Any]] = []
        client = get_openai_client()

        if client:
            system_prompt = (
                "Extract ONLY durable user facts from the transcript. "
                "Focus on stable preferences, profile details, routines, goals, and constraints. "
                "Ignore temporary requests and assistant opinions. "
                "Return strict JSON with shape: "
                "{\"facts\": [{\"summary\": str, \"key\": str, \"value\": str, \"topic\": str, \"confidence\": float}]}. "
                "Topics must be one of: profile, preference, routine, goal, constraint, personal_info."
            )
            try:
                response = client.chat.completions.create(
                    model=settings.azure_openai.chat_deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": transcript[:4000]},
                    ],
                    temperature=0.1,
                    max_tokens=700,
                    response_format={"type": "json_object"},
                )
                payload = json.loads(response.choices[0].message.content.strip())
                candidate_facts = payload.get("facts", []) if isinstance(payload, dict) else []
                for item in candidate_facts:
                    if not isinstance(item, dict):
                        continue
                    summary = str(item.get("summary", "")).strip()
                    key = str(item.get("key", "")).strip()
                    value = str(item.get("value", "")).strip()
                    topic = str(item.get("topic", "preference")).strip().lower()
                    try:
                        confidence = float(item.get("confidence", 0.0))
                    except (TypeError, ValueError):
                        confidence = 0.0

                    if not summary or not value:
                        continue
                    if topic not in {"profile", "preference", "routine", "goal", "constraint", "personal_info"}:
                        topic = "preference"
                    if confidence < 0.55:
                        continue

                    facts.append(
                        {
                            "summary": summary,
                            "key": key or "fact",
                            "value": value,
                            "topic": topic,
                            "confidence": round(confidence, 3),
                        }
                    )
            except Exception as e:
                logger.warning(f"LLM fact extraction failed, using fallback rules: {e}")

        if not facts:
            text = transcript.lower()

            m = re.search(r"\bmy name is\s+([a-z][a-z\s'\-]{1,40})", text)
            if m:
                name_value = m.group(1).strip().title()
                facts.append({
                    "summary": f"User name is {name_value}",
                    "key": "name",
                    "value": name_value,
                    "topic": "profile",
                    "confidence": 0.8,
                })

            m = re.search(r"\bi (?:prefer|like)\s+([^.!\n]{2,80})", text)
            if m:
                pref = m.group(1).strip()
                facts.append({
                    "summary": f"User preference: {pref}",
                    "key": "stated_preference",
                    "value": pref,
                    "topic": "preference",
                    "confidence": 0.7,
                })

            m = re.search(r"\bi (?:live|am based) in\s+([a-z][a-z\s'\-]{1,50})", text)
            if m:
                city = m.group(1).strip().title()
                facts.append({
                    "summary": f"User location is {city}",
                    "key": "location",
                    "value": city,
                    "topic": "profile",
                    "confidence": 0.75,
                })

        return self._deduplicate_facts(facts)

    async def analyze(self, state: AgentState) -> AgentState:
        """
        Analyze the completed request and extract learning signals.

        Tracks: missed reminders, habit streaks, frequent tasks, time preferences.
        """
        logger.log_agent_start("behavior_analyzer")
        start_time = time.time()

        user_id = state.get("system", {}).get("user_id", "") or "anonymous_user"
        request_type = state.get("system", {}).get("request_type", "")
        execution = state.get("execution", {})
        sm = state.get("memory_context", {}).get("structured_memory", {})

        # Load persisted counters on first encounter of this user
        if user_id not in self._loaded_users and self._memory and user_id != "anonymous_user":
            await self._load_counters(user_id)
            self._loaded_users.add(user_id)

        # Track interaction count
        self._interaction_count[user_id] = self._interaction_count.get(user_id, 0) + 1

        # Log action type (keep last 30)
        actions = self._action_log.setdefault(user_id, [])
        actions.append(request_type)
        if len(actions) > 30:
            actions[:] = actions[-30:]

        # Log interaction hour (keep last 50)
        current_hour = datetime.now(timezone.utc).hour
        hours = self._hour_log.setdefault(user_id, [])
        hours.append(current_hour)
        if len(hours) > 50:
            hours[:] = hours[-50:]

        patterns: List[str] = []

        # 1. Frequent task detection
        if len(actions) >= 5:
            counts = Counter(actions)
            top, top_count = counts.most_common(1)[0]
            if top_count >= 3:
                patterns.append(f"Frequent action: {top}")

        # 2. Habit streak detection
        habits = sm.get("habits", [])
        for h in habits:
            streak = h.get("streak", 0)
            if streak >= 7:
                patterns.append(f"Habit streak: {h.get('name', '?')} ({streak} days)")
            elif streak == 0 and h.get("total_completions", 0) > 0:
                patterns.append(f"Habit needs attention: {h.get('name', '?')}")

        # 3. Missed reminder detection
        now = datetime.now(timezone.utc)
        reminders = sm.get("reminders", [])
        missed = []
        for r in reminders:
            if r.get("status") == "completed":
                continue
            remind_at = r.get("remind_at")
            if remind_at:
                try:
                    due = datetime.fromisoformat(str(remind_at))
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                    if due < now:
                        missed.append(r.get("title", "?"))
                except (ValueError, TypeError):
                    pass
        if missed:
            patterns.append(f"Missed reminders ({len(missed)}): {', '.join(missed[:5])}")

        # 4. Time preference detection
        if len(hours) >= 10:
            hour_counts = Counter(hours)
            peak_hour, peak_count = hour_counts.most_common(1)[0]
            # Determine active period
            morning = sum(hour_counts.get(h, 0) for h in range(6, 12))
            afternoon = sum(hour_counts.get(h, 0) for h in range(12, 18))
            evening = sum(hour_counts.get(h, 0) for h in range(18, 24))
            night = sum(hour_counts.get(h, 0) for h in range(0, 6))
            periods = {"morning": morning, "afternoon": afternoon, "evening": evening, "night": night}
            preferred = max(periods, key=periods.get)
            patterns.append(f"Time preference: most active in {preferred} (peak hour: {peak_hour}:00 UTC)")

        extracted_facts = await self._extract_useful_facts(state)

        # Build learning state
        tool_calls = execution.get("tool_calls", [])
        tool_names = [tc.get("tool", "") for tc in tool_calls]
        learning = {
            "behavior_analysis": f"Interaction #{self._interaction_count[user_id]}, type={request_type}, tools={tool_names or 'none'}",
            "patterns_detected": patterns,
            "extracted_facts": extracted_facts,
            "preference_updates": [],
        }

        system = {**state.get("system", {}), "current_stage": "response"}
        state = {**state, "learning": learning, "system": system}
        state = add_log_entry(
            state,
            "behavior_analyzer",
            "analysis_complete",
            f"Patterns: {len(patterns)}, facts: {len(extracted_facts)}",
        )

        duration_ms = (time.time() - start_time) * 1000
        logger.log_agent_end("behavior_analyzer", f"{len(patterns)} patterns, {len(extracted_facts)} facts", duration_ms)

        # Persist counters so they survive restarts
        if self._memory and user_id != "anonymous_user":
            await self._save_counters(user_id)

        return state

    async def _load_counters(self, user_id: str) -> None:
        """Load interaction counters from user preferences."""
        try:
            user = await self._memory.get_user_by_id(user_id)
            if not user:
                return
            prefs = user.get("preferences") or {}
            counters = prefs.get("_interaction_counters", {})
            if counters:
                self._interaction_count[user_id] = counters.get("interaction_count", 0)
                self._action_log[user_id] = counters.get("action_log", [])
                self._hour_log[user_id] = counters.get("hour_log", [])
        except Exception as e:
            logger.warning(f"Failed to load interaction counters for {user_id}: {e}")

    async def _save_counters(self, user_id: str) -> None:
        """Persist interaction counters into user preferences."""
        try:
            user = await self._memory.get_user_by_id(user_id)
            if not user:
                return
            prefs = dict(user.get("preferences") or {})
            prefs["_interaction_counters"] = {
                "interaction_count": self._interaction_count.get(user_id, 0),
                "action_log": (self._action_log.get(user_id, []))[-30:],
                "hour_log": (self._hour_log.get(user_id, []))[-50:],
            }
            await self._memory.update_user_preferences(user_id, prefs)
        except Exception as e:
            logger.warning(f"Failed to save interaction counters for {user_id}: {e}")
