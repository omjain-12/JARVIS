"""Pydantic request/response models for the JARVIS chat and voice API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request Models ──


class ChatRequest(BaseModel):
    """POST /chat request body."""
    user_id: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(default="")


class ConfirmRequest(BaseModel):
    """POST /confirm request body."""
    action_id: str = Field(..., min_length=1)
    confirmed: bool = True
    tool_name: str = Field(default="")
    tool_params: Dict[str, Any] = Field(default_factory=dict)


class TextToVoiceRequest(BaseModel):
    """POST /text-to-voice request body."""
    text: str = Field(..., min_length=1, max_length=5000)
    voice_name: str = Field(default="en-US-GuyNeural")


# ── Response Models ──


class ChatResponseData(BaseModel):
    """The response payload inside ChatResponse."""
    text: str = ""
    format: str = "text"
    structured_data: Optional[Dict[str, Any]] = None


class ChatMetadata(BaseModel):
    """Metadata attached to a chat response."""
    request_type: str = ""
    decision: str = ""
    decision_explanation: str = ""
    reasoning_steps: List[str] = Field(default_factory=list)
    goal: str = ""
    tools_used: List[str] = Field(default_factory=list)
    patterns_detected: List[str] = Field(default_factory=list)
    total_time_ms: float = 0.0


class ChatResponse(BaseModel):
    """POST /chat response body."""
    status: str
    request_id: str = ""
    response: ChatResponseData
    metadata: ChatMetadata


class ConfirmResponse(BaseModel):
    """POST /confirm response body."""
    status: str
    message: str
    result: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """GET /health response body."""
    status: str
    version: str
    uptime_seconds: float
    services: Dict[str, bool] = Field(default_factory=dict)
    voice_available: bool = False
