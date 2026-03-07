"""
Structured logging module for JARVIS AI System.
Provides JSON-structured logging with request tracing and agent decision logging.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for structured logging and Application Insights ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service_name", "jarvis"),
            "request_id": getattr(record, "request_id", ""),
            "user_id": getattr(record, "user_id", ""),
            "agent": getattr(record, "agent_name", ""),
            "event": getattr(record, "event_type", ""),
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add metadata if present
        metadata = getattr(record, "metadata", None)
        if metadata:
            log_entry["metadata"] = metadata

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class AgentLogger:
    """
    Logger with built-in support for agent tracing, request correlation,
    and structured metadata.
    """

    def __init__(self, name: str = "jarvis", level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))

        # Prevent duplicate handlers
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JSONFormatter())
            self.logger.addHandler(handler)

        self._request_id: str = ""
        self._user_id: str = ""
        self._agent_name: str = ""

    def set_context(
        self,
        request_id: str = "",
        user_id: str = "",
        agent_name: str = "",
    ):
        """Set logging context for the current request."""
        self._request_id = request_id
        self._user_id = user_id
        self._agent_name = agent_name

    def _log(
        self,
        level: int,
        message: str,
        event_type: str = "",
        metadata: Optional[dict] = None,
        exc_info: bool = False,
    ):
        """Internal log method with structured context."""
        extra = {
            "service_name": "jarvis",
            "request_id": self._request_id,
            "user_id": self._user_id,
            "agent_name": self._agent_name,
            "event_type": event_type,
            "metadata": metadata,
        }
        self.logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(self, message: str, event_type: str = "", metadata: Optional[dict] = None):
        self._log(logging.DEBUG, message, event_type, metadata)

    def info(self, message: str, event_type: str = "", metadata: Optional[dict] = None):
        self._log(logging.INFO, message, event_type, metadata)

    def warning(self, message: str, event_type: str = "", metadata: Optional[dict] = None):
        self._log(logging.WARNING, message, event_type, metadata)

    def error(
        self, message: str, event_type: str = "", metadata: Optional[dict] = None, exc_info: bool = True
    ):
        self._log(logging.ERROR, message, event_type, metadata, exc_info=exc_info)

    def critical(
        self, message: str, event_type: str = "", metadata: Optional[dict] = None, exc_info: bool = True
    ):
        self._log(logging.CRITICAL, message, event_type, metadata, exc_info=exc_info)

    # ── Agent-specific logging helpers ──

    def log_agent_start(self, agent_name: str, input_summary: str = ""):
        """Log when an agent starts processing."""
        self._agent_name = agent_name
        self.info(
            f"Agent [{agent_name}] started",
            event_type="agent_start",
            metadata={"input_summary": input_summary[:200] if input_summary else ""},
        )

    def log_agent_end(self, agent_name: str, output_summary: str = "", duration_ms: float = 0):
        """Log when an agent finishes processing."""
        self.info(
            f"Agent [{agent_name}] completed",
            event_type="agent_end",
            metadata={
                "output_summary": output_summary[:200] if output_summary else "",
                "duration_ms": round(duration_ms, 2),
            },
        )

    def log_llm_call(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0,
        status: str = "success",
    ):
        """Log an LLM API call with token and latency details."""
        self.info(
            f"LLM call to {model}",
            event_type="llm_call",
            metadata={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": round(latency_ms, 2),
                "status": status,
            },
        )

    def log_tool_call(self, tool_name: str, parameters: dict = None, status: str = "success", result: str = ""):
        """Log a tool execution."""
        self.info(
            f"Tool [{tool_name}] called",
            event_type="tool_call",
            metadata={
                "tool_name": tool_name,
                "parameters": parameters or {},
                "status": status,
                "result_preview": str(result)[:200] if result else "",
            },
        )

    def log_state_transition(self, from_stage: str, to_stage: str):
        """Log state transitions in the pipeline."""
        self.info(
            f"State transition: {from_stage} → {to_stage}",
            event_type="state_transition",
            metadata={"from": from_stage, "to": to_stage},
        )


def get_logger(name: str = "jarvis", level: str = "INFO") -> AgentLogger:
    """Factory function to get a configured logger instance."""
    return AgentLogger(name=name, level=level)
