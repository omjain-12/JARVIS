"""Voice service — Azure Speech SDK helpers for speech-to-text and text-to-speech."""

from __future__ import annotations

import io
import os
import tempfile
from xml.sax.saxutils import escape
from typing import Optional, Tuple

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("voice_service")

_speech_config = None

_DEFAULT_MALE_VOICES = (
    "en-US-AndrewNeural",
    "en-US-GuyNeural",
    "en-US-DavisNeural",
    "en-GB-RyanNeural",
)


def _looks_male_voice(name: str) -> bool:
    """Best-effort check to keep default synthesis on a male voice."""
    lowered = (name or "").lower()
    return any(
        token in lowered
        for token in ("andrew", "guy", "davis", "ryan", "david", "male", "guy")
    )


def _pick_tts_voice(requested_voice: str) -> str:
    """Resolve preferred TTS voice with optional male-only enforcement."""
    env_voice = settings.azure_speech.tts_voice or os.getenv("AZURE_TTS_VOICE", "").strip()
    force_male = settings.azure_speech.tts_force_male

    candidates = [requested_voice.strip(), env_voice, *_DEFAULT_MALE_VOICES]
    for candidate in candidates:
        if not candidate:
            continue
        if force_male and not _looks_male_voice(candidate):
            continue
        return candidate

    return "en-US-GuyNeural"

try:
    import azure.cognitiveservices.speech as speechsdk
    _HAS_SPEECH_SDK = True
except ImportError:
    speechsdk = None
    _HAS_SPEECH_SDK = False


def _get_speech_config():
    """Lazy-initialise and cache the SpeechConfig."""
    global _speech_config
    if _speech_config is not None:
        return _speech_config

    if not _HAS_SPEECH_SDK:
        raise RuntimeError(
            "Azure Speech SDK (azure-cognitiveservices-speech) is not installed."
        )

    key = settings.azure_speech.key or os.getenv("AZURE_SPEECH_KEY", "")
    region = settings.azure_speech.region or os.getenv("AZURE_SPEECH_REGION", "")

    if not key or not region:
        raise RuntimeError(
            "Azure Speech credentials not configured. "
            "Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION."
        )

    _speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    _speech_config.speech_recognition_language = "en-US"
    logger.info("Azure Speech config created", event_type="voice_init")
    return _speech_config


def is_voice_available() -> bool:
    """Return True if the voice SDK + credentials are ready."""
    if not _HAS_SPEECH_SDK:
        return False
    try:
        _get_speech_config()
        return True
    except RuntimeError:
        return False


async def speech_to_text(audio_bytes: bytes) -> Tuple[str, bool]:
    """Convert raw audio (WAV) to text using Azure Speech-to-Text."""
    if not _HAS_SPEECH_SDK:
        logger.warning("Speech SDK not installed — STT unavailable")
        return "", False

    try:
        cfg = _get_speech_config()

        # Write audio to temp file — SDK needs a file path or push stream
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        audio_config = speechsdk.audio.AudioConfig(filename=tmp_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=audio_config)
        result = recognizer.recognize_once()

        os.unlink(tmp_path)

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            logger.info(f"STT recognised: {result.text[:80]}", event_type="stt_success")
            return result.text, True
        elif result.reason == speechsdk.ResultReason.NoMatch:
            logger.warning("STT: no match", event_type="stt_no_match")
            return "", False
        else:
            detail = getattr(result, "cancellation_details", None)
            msg = detail.reason if detail else "unknown"
            logger.error(f"STT cancelled: {msg}", event_type="stt_error")
            return "", False

    except Exception as e:
        logger.error(f"STT exception: {e}", exc_info=True)
        return "", False


async def text_to_speech(text: str, voice_name: str = "en-US-GuyNeural") -> Tuple[bytes, bool]:
    """Convert text to speech audio using Azure TTS."""
    if not _HAS_SPEECH_SDK:
        logger.warning("Speech SDK not installed — TTS unavailable")
        return b"", False

    try:
        cfg = _get_speech_config()

        selected_voice = _pick_tts_voice(voice_name)
        cfg.speech_synthesis_voice_name = selected_voice

        # Use default audio config (None) so result.audio_data is populated
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)

        style = settings.azure_speech.tts_style or os.getenv("AZURE_TTS_STYLE", "chat").strip()
        escaped_text = escape(text)
        ssml = (
            "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
            "xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='en-US'>"
            f"<voice name='{selected_voice}'>"
            f"<mstts:express-as style='{style}'>"
            "<prosody rate='+2%' pitch='-4%'>"
            f"{escaped_text}"
            "</prosody>"
            "</mstts:express-as>"
            "</voice>"
            "</speak>"
        )

        # Some voices don't support all styles; fall back to plain TTS if needed.
        result = synthesizer.speak_ssml(ssml)
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            result = synthesizer.speak_text(text)

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.info(f"TTS completed ({len(result.audio_data)} bytes)", event_type="tts_success")
            return result.audio_data, True
        else:
            detail = getattr(result, "cancellation_details", None)
            msg = detail.reason if detail else "unknown"
            logger.error(f"TTS cancelled: {msg}", event_type="tts_error")
            return b"", False

    except Exception as e:
        logger.error(f"TTS exception: {e}", exc_info=True)
        return b"", False
