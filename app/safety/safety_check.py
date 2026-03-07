"""
Safety Layer — input validation, prompt injection detection, and rate limiting.

This module runs before any user input reaches the agent pipeline.
It validates, sanitizes, and filters all inputs to protect the system.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Dict, Tuple

from app.state.agent_state import AgentState, add_log_entry
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("safety")


# ── Known Prompt Injection Patterns ──

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?prior\s+instructions",
    r"ignore\s+(all\s+)?above\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"pretend\s+you\s+are",
    r"act\s+as\s+if\s+you\s+are",
    r"you\s+are\s+now\s+a",
    r"from\s+now\s+on\s+you\s+are",
    r"DAN\s+mode",
    r"jailbreak",
    r"developer\s+mode",
    r"(system|admin)\s*prompt",
    r"override\s+(your\s+)?(system|instructions|rules)",
    r"new\s+instructions?\s*:",
    r"<\s*system\s*>",
    r"\[SYSTEM\]",
    r"```\s*system",
    r"roleplay\s+as\s+an?\s+unrestricted",
    r"bypass\s+(your\s+)?(safety|filter|rules)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


# ── Rate Limiter ──

class RateLimiter:
    """Simple sliding window rate limiter per user."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, user_id: str) -> Tuple[bool, int]:
        """
        Check if a user is within the rate limit.

        Returns:
            (is_allowed, remaining_requests)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        self._requests[user_id] = [
            t for t in self._requests[user_id] if t > window_start
        ]

        if len(self._requests[user_id]) >= self.max_requests:
            remaining = 0
            return False, remaining

        self._requests[user_id].append(now)
        remaining = self.max_requests - len(self._requests[user_id])
        return True, remaining


# Global rate limiter
rate_limiter = RateLimiter()


# ── Safety Check Functions ──


def sanitize_input(text: str) -> str:
    """
    Clean and sanitize user input.

    - Strip dangerous control characters
    - Normalize whitespace
    - Truncate to max length
    """
    # Remove null bytes and control characters (except newline, tab)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Normalize whitespace (collapse multiple spaces, preserve newlines)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Truncate to max length
    max_length = settings.app.max_input_length
    if len(text) > max_length:
        text = text[:max_length]

    return text


def detect_injection(text: str) -> Tuple[bool, str]:
    """
    Check for prompt injection patterns in user input.

    Returns:
        (is_injection, matched_pattern)
    """
    for pattern in COMPILED_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, match.group()

    return False, ""


def validate_input_length(text: str) -> bool:
    """Check if input is within acceptable length."""
    if not text or len(text.strip()) == 0:
        return False
    if len(text) > settings.app.max_input_length:
        return False
    return True


# ── Main Safety Check Pipeline ──


async def run_safety_check(state: AgentState) -> AgentState:
    """
    Run the complete safety validation pipeline on the user input.

    This is the first step in the agent workflow graph.

    Checks performed:
    1. Input length validation
    2. Input sanitization
    3. Prompt injection detection
    4. Rate limiting

    Updates:
        state.user_request.validated_input — sanitized input
        state.system.current_stage — advances to next stage or sets error
        state.system.error — error message if validation fails

    Args:
        state: The current AgentState.

    Returns:
        Updated AgentState.
    """
    logger.set_context(
        request_id=state.get("system", {}).get("request_id", ""),
        user_id=state.get("system", {}).get("user_id", ""),
        agent_name="safety",
    )
    logger.log_agent_start("safety", state.get("user_request", {}).get("raw_input", "")[:100])

    start_time = time.time()
    raw_input = state.get("user_request", {}).get("raw_input", "")
    user_id = state.get("system", {}).get("user_id", "")

    # 1. Rate limit check
    allowed, remaining = rate_limiter.is_allowed(user_id)
    if not allowed:
        state = add_log_entry(state, "safety", "rate_limited", f"User {user_id} exceeded rate limit")
        logger.warning(f"Rate limited user {user_id}")
        system = {**state["system"], "error": "Rate limit exceeded. Please wait before sending more requests.", "current_stage": "error"}
        return {**state, "system": system}

    # 2. Input length validation
    if not validate_input_length(raw_input):
        state = add_log_entry(state, "safety", "invalid_input", "Input is empty or exceeds max length")
        logger.warning("Invalid input length")
        system = {**state["system"], "error": "Input is empty or too long. Please keep your message under 4000 characters.", "current_stage": "error"}
        return {**state, "system": system}

    # 3. Sanitize input
    validated_input = sanitize_input(raw_input)

    # 4. Prompt injection detection
    is_injection, matched_pattern = detect_injection(validated_input)
    if is_injection:
        state = add_log_entry(state, "safety", "injection_detected", f"Pattern: {matched_pattern}")
        logger.warning(f"Prompt injection detected: {matched_pattern}")
        system = {**state["system"], "error": "Your input was flagged by our safety system. Please rephrase your request.", "current_stage": "error"}
        return {**state, "system": system}

    # All checks passed — update state
    user_request = {**state.get("user_request", {}), "validated_input": validated_input}
    system = {**state["system"], "current_stage": "retrieval"}

    state = {**state, "user_request": user_request, "system": system}
    state = add_log_entry(state, "safety", "validation_passed", "Input validated and sanitized")

    duration_ms = (time.time() - start_time) * 1000
    logger.log_agent_end("safety", "Validation passed", duration_ms)

    return state
