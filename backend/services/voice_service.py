"""
Voice service — Azure Speech SDK helpers for speech-to-text and text-to-speech.
"""

from __future__ import annotations

import io
import os
import tempfile
from typing import Optional, Tuple

from app.utils.logger import get_logger

logger = get_logger("voice_service")

_speech_config = None

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

    key = os.getenv("AZURE_SPEECH_KEY", "")
    region = os.getenv("AZURE_SPEECH_REGION", "")

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
    """
    Convert raw audio (WAV) to text using Azure Speech-to-Text.

    Args:
        audio_bytes: WAV-format audio data.

    Returns:
        (transcribed_text, success)
    """
    if not _HAS_SPEECH_SDK:
        logger.warning("Speech SDK not installed — STT unavailable")
        return "", False

    cfg = _get_speech_config()

    try:
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


async def text_to_speech(text: str, voice_name: str = "en-US-JennyNeural") -> Tuple[bytes, bool]:
    """
    Convert text to speech audio using Azure TTS.

    Args:
        text: The text to synthesise.
        voice_name: SSML voice name.

    Returns:
        (wav_bytes, success)
    """
    if not _HAS_SPEECH_SDK:
        logger.warning("Speech SDK not installed — TTS unavailable")
        return b"", False

    cfg = _get_speech_config()

    try:
        cfg.speech_synthesis_voice_name = voice_name

        # Use default audio config (None) so result.audio_data is populated
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)

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
