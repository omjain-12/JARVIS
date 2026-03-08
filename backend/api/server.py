"""
JARVIS Backend API — chat, voice, and confirmation endpoints.

This module adds the assistant-UI-facing endpoints on top of the existing
api/api_server.py (which keeps auth, documents, tasks, habits, etc.).

Run with:
    uvicorn backend.api.server:app --reload --port 8001
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from backend.models.request_models import (
    ChatRequest,
    ChatResponse,
    ChatResponseData,
    ChatMetadata,
    ConfirmRequest,
    ConfirmResponse,
    HealthResponse,
    TextToVoiceRequest,
)
from backend.services import agent_service, voice_service
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("backend_api")

_start_time = time.time()


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting JARVIS backend API …", event_type="backend_startup")
    # Eagerly initialise the workflow so first request isn't slow
    await agent_service.get_workflow()
    logger.info("JARVIS backend API ready", event_type="backend_ready")
    yield
    logger.info("Shutting down …", event_type="backend_shutdown")
    await agent_service.shutdown()


# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="JARVIS Assistant API",
    version="1.0.0",
    description="Chat, voice, and confirmation endpoints for the JARVIS assistant UI",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Chat ────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a text message to the JARVIS agent pipeline and receive a response.
    """
    result = await agent_service.run_agent(
        user_id=request.user_id,
        message=request.message,
        session_id=request.session_id,
    )

    resp = result.get("response", {})
    meta = result.get("metadata", {})

    return ChatResponse(
        status=result.get("status", "error"),
        request_id=result.get("request_id", ""),
        response=ChatResponseData(
            text=resp.get("text", ""),
            format=resp.get("format", "text"),
            structured_data=resp.get("structured_data"),
        ),
        metadata=ChatMetadata(
            request_type=meta.get("request_type", ""),
            decision=meta.get("decision", ""),
            decision_explanation=meta.get("decision_explanation", ""),
            reasoning_steps=meta.get("reasoning_steps", []),
            goal=meta.get("goal", ""),
            tools_used=meta.get("tools_used", []),
            patterns_detected=meta.get("patterns_detected", []),
            total_time_ms=meta.get("total_time_ms", 0),
        ),
    )


# ── Confirm ─────────────────────────────────────────────────────────────────

@app.post("/confirm", response_model=ConfirmResponse, tags=["Chat"])
async def confirm(request: ConfirmRequest):
    """
    Confirm or reject a pending tool action.

    In the current implementation the workflow auto-confirms, so this
    endpoint acknowledges the intent and returns a status message.
    A full implementation would resume a paused LangGraph run.
    """
    if request.confirmed:
        return ConfirmResponse(
            status="confirmed",
            message=f"Action {request.action_id} confirmed.",
        )
    return ConfirmResponse(
        status="rejected",
        message=f"Action {request.action_id} was rejected by user.",
    )


# ── Voice-to-Text ──────────────────────────────────────────────────────────

@app.post("/voice-to-text", tags=["Voice"])
async def voice_to_text(file: UploadFile = File(...)):
    """
    Convert uploaded audio (WAV) to text via Azure Speech-to-Text.
    Falls back with an error message if voice services are unavailable.
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    text, ok = await voice_service.speech_to_text(audio_bytes)
    if not ok:
        raise HTTPException(
            status_code=503,
            detail="Speech recognition failed or voice service unavailable. Use text input instead.",
        )
    return {"text": text}


# ── Text-to-Voice ──────────────────────────────────────────────────────────

@app.post("/text-to-voice", tags=["Voice"])
async def text_to_voice(request: TextToVoiceRequest):
    """
    Synthesise text into speech audio (WAV) via Azure TTS.
    Returns binary audio/wav on success.
    """
    audio_data, ok = await voice_service.text_to_speech(request.text, request.voice_name)
    if not ok:
        raise HTTPException(
            status_code=503,
            detail="Text-to-speech failed or voice service unavailable.",
        )
    return Response(content=audio_data, media_type="audio/wav")


# ── Voice-to-Voice (optional pipeline) ─────────────────────────────────────

@app.post("/voice-to-voice", tags=["Voice"])
async def voice_to_voice(
    user_id: str = "default_user",
    file: UploadFile = File(...),
):
    """
    Full voice-to-voice pipeline:
      voice input → STT → agent → TTS → audio output.
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # 1. Speech-to-text
    text, stt_ok = await voice_service.speech_to_text(audio_bytes)
    if not stt_ok or not text:
        raise HTTPException(status_code=503, detail="Speech recognition failed. Use text input.")

    # 2. Agent reasoning
    result = await agent_service.run_agent(user_id=user_id, message=text)
    response_text = result.get("response", {}).get("text", "")

    # 3. Text-to-speech
    tts_audio, tts_ok = await voice_service.text_to_speech(response_text)
    if not tts_ok or not tts_audio:
        raise HTTPException(status_code=503, detail="Text-to-speech synthesis failed.")

    return Response(content=tts_audio, media_type="audio/wav")


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Health check with voice availability."""
    return HealthResponse(
        status="running",
        version="1.0.0",
        uptime_seconds=round(time.time() - _start_time, 2),
        services=settings.validate_azure_services(),
        voice_available=voice_service.is_voice_available(),
    )
