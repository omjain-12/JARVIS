"""JARVIS Backend API — chat, voice, and confirmation endpoints."""

from __future__ import annotations

import asyncio
import base64
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from dataclasses import field
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from pydantic import BaseModel, Field

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


@dataclass
class LiveSessionState:
    user_id: str = "demo_user"
    session_id: str = ""
    active_task: Optional[asyncio.Task] = None
    audio_buffer: bytearray = field(default_factory=bytearray)
    audio_mime_type: str = "audio/webm"


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
    """Send a text message to the JARVIS agent pipeline and receive a response."""
    try:
        result = await agent_service.run_agent(
            user_id=request.user_id,
            message=request.message,
            session_id=request.session_id,
        )
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        result = {
            "status": "error",
            "request_id": "",
            "response": {"text": "Something went wrong. Please try again.", "format": "text"},
            "metadata": {},
        }

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
    """Confirm or reject a pending communication action."""
    if not request.confirmed:
        return ConfirmResponse(
            status="rejected",
            message=f"Message was cancelled. Nothing was sent.",
        )

    # If no tool specified, just acknowledge
    if not request.tool_name:
        return ConfirmResponse(
            status="confirmed",
            message=f"Action {request.action_id} confirmed.",
        )

    # Execute the actual tool
    try:
        wf = await agent_service.get_workflow()
        result = await wf.toolbox.execute(request.tool_name, request.tool_params)
        status = result.get("status", "unknown")
        message = result.get("message", str(result))

        return ConfirmResponse(
            status=status,
            message=message,
            result=result,
        )
    except Exception as e:
        logger.error(f"Confirm tool execution failed: {e}", exc_info=True)
        return ConfirmResponse(
            status="error",
            message=f"Failed to send: {str(e)}",
        )


# ── Voice-to-Text ──────────────────────────────────────────────────────────

@app.post("/voice-to-text", tags=["Voice"])
async def voice_to_text(file: UploadFile = File(...)):
    """Convert uploaded audio (WAV) to text via Azure Speech-to-Text."""
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
    """Synthesise text into speech audio (WAV) via Azure TTS."""
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
    """Full voice-to-voice pipeline."""
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


# ── Live Talk (WebSocket) ───────────────────────────────────────────────────

@app.websocket("/ws/live-talk")
async def live_talk(websocket: WebSocket):
    """Realtime voice session protocol."""
    await websocket.accept()
    state = LiveSessionState(session_id=f"live_{int(time.time() * 1000)}")

    async def process_utterance(text: str) -> None:
        if not text.strip():
            await websocket.send_json({"type": "error", "message": "Empty utterance."})
            return

        await websocket.send_json({"type": "assistant.thinking"})

        full_text = ""
        try:
            async for chunk in agent_service.run_agent_stream(
                user_id=state.user_id,
                message=text,
                session_id=state.session_id,
            ):
                full_text += chunk
                await websocket.send_json({"type": "assistant.text.delta", "text": chunk})
                await asyncio.sleep(0.01)  # Allow event-loop to flush WS frames
        except asyncio.CancelledError:
            await websocket.send_json({"type": "assistant.interrupted"})
            await websocket.send_json({"type": "assistant.done"})
            return
        except WebSocketDisconnect:
            return
        except Exception as e:
            logger.error(f"Live talk processing failed: {e}", exc_info=True)
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Live response failed. Please try again.",
                    }
                )
                await websocket.send_json({"type": "assistant.done"})
            except Exception:
                pass
            return

        final_text = full_text.strip()
        await websocket.send_json({"type": "assistant.text.final", "text": final_text})

        try:
            if final_text and voice_service.is_voice_available():
                tts_audio, ok = await voice_service.text_to_speech(final_text)
                if ok and tts_audio:
                    payload = base64.b64encode(tts_audio).decode("ascii")
                    await websocket.send_json(
                        {
                            "type": "assistant.audio.chunk",
                            "mime_type": "audio/wav",
                            "audio_base64": payload,
                        }
                    )
        except Exception as e:
            logger.error(f"Live talk TTS failed: {e}", exc_info=True)

        await websocket.send_json({"type": "assistant.done"})

    try:
        await websocket.send_json(
            {
                "type": "session.ready",
                "session_id": state.session_id,
                "voice_available": voice_service.is_voice_available(),
            }
        )

        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type", "")

            if msg_type == "session.start":
                state.user_id = message.get("user_id", state.user_id)
                state.session_id = message.get("session_id", state.session_id)
                await websocket.send_json(
                    {
                        "type": "session.ready",
                        "session_id": state.session_id,
                        "voice_available": voice_service.is_voice_available(),
                    }
                )
                continue

            if msg_type == "assistant.interrupt":
                if state.active_task and not state.active_task.done():
                    state.active_task.cancel()
                continue

            if msg_type == "utterance.final":
                text = message.get("text", "")
                if state.active_task and not state.active_task.done():
                    state.active_task.cancel()
                state.active_task = asyncio.create_task(process_utterance(text))
                continue

            if msg_type == "audio.chunk":
                audio_base64 = message.get("audio_base64", "")
                if not audio_base64:
                    await websocket.send_json({"type": "error", "message": "Missing audio chunk payload."})
                    continue

                try:
                    chunk = base64.b64decode(audio_base64)
                except Exception:
                    await websocket.send_json({"type": "error", "message": "Invalid audio chunk encoding."})
                    continue

                state.audio_buffer.extend(chunk)
                state.audio_mime_type = message.get("mime_type", state.audio_mime_type)
                continue

            if msg_type == "audio.stop":
                if not state.audio_buffer:
                    await websocket.send_json({"type": "error", "message": "No audio received before audio.stop."})
                    continue

                # Current STT path expects a complete file payload.
                # Frontend may still use browser-native STT for lower latency.
                text, ok = await voice_service.speech_to_text(bytes(state.audio_buffer))
                state.audio_buffer.clear()
                if not ok or not text:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Live STT failed for streamed audio. Browser STT fallback is recommended.",
                        }
                    )
                    continue

                await websocket.send_json({"type": "stt.final", "text": text})
                if state.active_task and not state.active_task.done():
                    state.active_task.cancel()
                state.active_task = asyncio.create_task(process_utterance(text))
                continue

            await websocket.send_json({"type": "error", "message": f"Unsupported message type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("Live talk client disconnected", event_type="live_talk_disconnect")
    finally:
        if state.active_task and not state.active_task.done():
            state.active_task.cancel()


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


# ── Data API: Request Models ───────────────────────────────────────────────


class ContactCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=50)
    relationship: str = Field(default="", max_length=100)
    notes: str = Field(default="")
    tags: str = Field(default="")


class ContactUpdateRequest(BaseModel):
    name: str = Field(default="", max_length=255)
    email: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=50)
    relationship: str = Field(default="", max_length=100)
    notes: str = Field(default="")
    tags: str = Field(default="")


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="")
    priority: int = Field(default=0, ge=0, le=2)
    due_date: str = Field(default="")


class TaskUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1)


class ReminderCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    message: str = Field(default="")
    remind_at: str = Field(...)


class KnowledgeAddRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    topic: str = Field(default="general", max_length=100)


class PreferenceUpdateRequest(BaseModel):
    preferences: dict = Field(default_factory=dict)


# ── Data API: Tasks ────────────────────────────────────────────────────────


@app.get("/data/tasks", tags=["Data"])
async def get_tasks(user_id: str = "demo_user", status: str = ""):
    """List tasks for a user."""
    wf = await agent_service.get_workflow()
    tasks = await wf.memory.get_tasks(user_id, status=status)
    return {"tasks": tasks}


@app.post("/data/tasks", tags=["Data"], status_code=201)
async def create_task(request: TaskCreateRequest, user_id: str = "demo_user"):
    """Create a new task."""
    from datetime import datetime

    due_dt = None
    if request.due_date:
        try:
            due_dt = datetime.fromisoformat(request.due_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {request.due_date}")

    wf = await agent_service.get_workflow()
    task = await wf.memory.create_task(
        user_id=user_id,
        title=request.title,
        description=request.description,
        priority=request.priority,
        due_date=due_dt,
    )
    return {"task": task}


@app.patch("/data/tasks/{task_id}", tags=["Data"])
async def update_task(task_id: str, request: TaskUpdateRequest):
    """Update a task's status."""
    wf = await agent_service.get_workflow()
    await wf.memory.structured_db.update_task_status(task_id, request.status)
    return {"status": "updated", "task_id": task_id}


# ── Data API: Reminders ───────────────────────────────────────────────────


@app.get("/data/reminders", tags=["Data"])
async def get_reminders(user_id: str = "demo_user"):
    """List reminders for a user."""
    wf = await agent_service.get_workflow()
    reminders = await wf.memory.get_reminders(user_id)
    return {"reminders": reminders}


@app.post("/data/reminders", tags=["Data"], status_code=201)
async def create_reminder(request: ReminderCreateRequest, user_id: str = "demo_user"):
    """Create a new reminder."""
    from datetime import datetime

    try:
        remind_dt = datetime.fromisoformat(request.remind_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {request.remind_at}")

    wf = await agent_service.get_workflow()
    reminder = await wf.memory.create_reminder(
        user_id=user_id,
        title=request.title,
        message=request.message,
        remind_at=remind_dt,
    )
    return {"reminder": reminder}


# ── Data API: Contacts ─────────────────────────────────────────────────────


@app.get("/data/contacts", tags=["Data"])
async def get_contacts(user_id: str = "demo_user"):
    """List contacts for a user."""
    wf = await agent_service.get_workflow()
    contacts = await wf.memory.structured_db.get_contacts(user_id)
    return {"contacts": contacts}


@app.post("/data/contacts", tags=["Data"], status_code=201)
async def create_contact(request: ContactCreateRequest, user_id: str = "demo_user"):
    """Create a new contact."""
    wf = await agent_service.get_workflow()
    contact = await wf.memory.structured_db.create_contact(
        user_id=user_id,
        name=request.name,
        email=request.email,
        phone=request.phone,
        relationship=request.relationship,
        notes=request.notes,
    )
    return {"contact": contact}


@app.put("/data/contacts/{contact_id}", tags=["Data"])
async def update_contact(contact_id: str, request: ContactUpdateRequest):
    """Update an existing contact."""
    wf = await agent_service.get_workflow()
    contact = await wf.memory.structured_db.update_contact(
        contact_id=contact_id,
        name=request.name or None,
        email=request.email or None,
        phone=request.phone or None,
        relationship=request.relationship or None,
        notes=request.notes or None,
    )
    return {"contact": contact}


@app.delete("/data/contacts/{contact_id}", tags=["Data"])
async def delete_contact(contact_id: str):
    """Delete a contact."""
    wf = await agent_service.get_workflow()
    await wf.memory.structured_db.delete_contact(contact_id)
    return {"status": "deleted", "contact_id": contact_id}


# ── Data API: Habits ───────────────────────────────────────────────────────


@app.get("/data/habits", tags=["Data"])
async def get_habits(user_id: str = "demo_user"):
    """List habits for a user."""
    wf = await agent_service.get_workflow()
    habits = await wf.memory.get_habits(user_id)
    return {"habits": habits}


# ── Data API: Preferences ─────────────────────────────────────────────────


@app.get("/data/preferences", tags=["Data"])
async def get_preferences(user_id: str = "demo_user"):
    """Get user preferences."""
    wf = await agent_service.get_workflow()
    prefs = await wf.memory.structured_db.get_preferences(user_id)
    return {"preferences": prefs}


@app.put("/data/preferences", tags=["Data"])
async def update_preferences(request: PreferenceUpdateRequest, user_id: str = "demo_user"):
    """Update user preferences."""
    wf = await agent_service.get_workflow()
    result = await wf.memory.update_user_preferences(user_id, request.preferences)
    return {"preferences": result}


# ── Data API: Knowledge ───────────────────────────────────────────────────


@app.post("/data/knowledge", tags=["Data"], status_code=201)
async def add_knowledge(request: KnowledgeAddRequest, user_id: str = "demo_user"):
    """Add user knowledge directly to vector memory."""
    wf = await agent_service.get_workflow()
    result = await wf.memory.store_memory(
        user_id=user_id,
        content=request.content,
        memory_type="knowledge",
        metadata={"topic": request.topic, "source": "user_manual"},
    )
    return {"status": "stored", "result": result}


@app.get("/data/knowledge", tags=["Data"])
async def search_knowledge(user_id: str = "demo_user", query: str = ""):
    """Search user knowledge in vector memory."""
    wf = await agent_service.get_workflow()
    if query:
        results = await wf.memory.search_knowledge(query, user_id, top_k=20)
    else:
        results = await wf.memory.search_knowledge("user knowledge", user_id, top_k=50)
    return {"knowledge": results}


# ── Data API: Memory Viewer ───────────────────────────────────────────────


@app.get("/data/memories", tags=["Data"])
async def get_memories(user_id: str = "demo_user"):
    """Get all stored memories for the memory viewer page."""
    wf = await agent_service.get_workflow()

    # Get preferences and learned facts
    prefs = await wf.memory.structured_db.get_preferences(user_id)
    learned_facts = []
    if prefs and isinstance(prefs, list) and prefs:
        prefs_dict = prefs[0] if isinstance(prefs[0], dict) else {}
        learned_facts = list(prefs_dict.get("learned_facts", []))

    # Get behavior patterns from vector memory
    behavior_patterns = []
    try:
        behavior_patterns = await wf.memory.search_knowledge(
            query="behavior_pattern",
            user_id=user_id,
            top_k=20,
            topic_filter="behavior_pattern",
        )
    except Exception:
        pass

    # Get user knowledge from vector memory
    knowledge_entries = []
    try:
        knowledge_entries = await wf.memory.search_knowledge(
            query="user knowledge",
            user_id=user_id,
            top_k=50,
        )
    except Exception:
        pass

    # Get conversation history
    history = await wf.memory.get_conversation_history(user_id, limit=20)

    return {
        "learned_facts": learned_facts,
        "behavior_patterns": behavior_patterns,
        "knowledge_entries": knowledge_entries,
        "conversation_history": history,
    }


# ── Data API: Contact Lookup (for agent use) ──────────────────────────────


@app.get("/data/contacts/lookup/{name}", tags=["Data"])
async def lookup_contact(name: str, user_id: str = "demo_user"):
    """Look up a contact by name for agent tool resolution."""
    wf = await agent_service.get_workflow()
    contact = await wf.memory.structured_db.lookup_contact_by_name(user_id, name)
    if not contact:
        raise HTTPException(status_code=404, detail=f"Contact '{name}' not found")
    return {"contact": contact}
