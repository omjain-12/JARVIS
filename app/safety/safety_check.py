"""Safety Layer — input validation, sanitization, and rate limiting."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Dict, Tuple

from app.state.agent_state import AgentState, add_log_entry
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("safety")


# ── Rate Limiter ──

class RateLimiter:
    """Simple sliding window rate limiter per user."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, user_id: str) -> Tuple[bool, int]:
        now = time.time()
        window_start = now - self.window_seconds
        self._requests[user_id] = [
            t for t in self._requests[user_id] if t > window_start
        ]
        if len(self._requests[user_id]) >= self.max_requests:
            return False, 0
        self._requests[user_id].append(now)
        return True, self.max_requests - len(self._requests[user_id])


rate_limiter = RateLimiter()


# ── Utility helpers ──


def sanitize_input(text: str) -> str:
    """Strip control chars, normalise whitespace, truncate."""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    max_length = settings.app.max_input_length
    if len(text) > max_length:
        text = text[:max_length]
    return text


def validate_input_length(text: str) -> bool:
    """Check if input is within acceptable bounds."""
    if not text or len(text.strip()) == 0:
        return False
    return len(text) <= settings.app.max_input_length


# ── Main Safety Check Pipeline ──


async def run_safety_check(state: AgentState) -> AgentState:
    """Run the safety validation pipeline on user input."""
    logger.set_context(
        request_id=state.get("system", {}).get("request_id", ""),
        user_id=state.get("system", {}).get("user_id", ""),
        agent_name="safety",
    )
    logger.log_agent_start("safety", state.get("user_request", {}).get("raw_input", "")[:100])

    start_time = time.time()
    raw_input = state.get("user_request", {}).get("raw_input", "")
    user_id = state.get("system", {}).get("user_id", "")

    # 1. Rate limit
    allowed, _remaining = rate_limiter.is_allowed(user_id)
    if not allowed:
        state = add_log_entry(state, "safety", "rate_limited", f"User {user_id} exceeded rate limit")
        logger.warning(f"Rate limited user {user_id}")
        system = {**state["system"], "error": "Rate limit exceeded. Please wait before sending more requests.", "current_stage": "error"}
        return {**state, "system": system}

    # 2. Length validation
    if not validate_input_length(raw_input):
        state = add_log_entry(state, "safety", "invalid_input", "Input is empty or exceeds max length")
        logger.warning("Invalid input length")
        system = {**state["system"], "error": "Input is empty or too long. Please keep your message under 4000 characters.", "current_stage": "error"}
        return {**state, "system": system}

    # 3. Sanitize
    validated_input = sanitize_input(raw_input)

    # All checks passed
    user_request = {**state.get("user_request", {}), "validated_input": validated_input}
    system = {**state["system"], "current_stage": "retrieval"}

    state = {**state, "user_request": user_request, "system": system}
    state = add_log_entry(state, "safety", "validation_passed", "Input validated")

    duration_ms = (time.time() - start_time) * 1000
    logger.log_agent_end("safety", "Validation passed", duration_ms)

    return state
