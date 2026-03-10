"""Central Azure OpenAI LLM factory — single source of truth for all LLM clients."""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from app.utils.logger import get_logger

logger = get_logger("azure_llm")

# ── Cached singleton ────────────────────────────────────────────────────────

_openai_client = None


def _normalize_azure_endpoint(endpoint: str) -> str:
    """Return the base Azure endpoint expected by AzureOpenAI SDK."""
    if not endpoint:
        return endpoint

    parsed = urlsplit(endpoint)
    if not parsed.scheme or not parsed.netloc:
        return endpoint.rstrip("/")

    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def get_openai_client():
    """Return a shared AzureOpenAI client (openai SDK) for structured JSON calls."""
    global _openai_client
    if _openai_client is not None:
        return _openai_client

    try:
        from openai import AzureOpenAI
        from app.utils.config import settings

        endpoint = settings.azure_openai.endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", "")
        api_key = settings.azure_openai.api_key or os.getenv("AZURE_OPENAI_API_KEY", "")
        api_version = settings.azure_openai.api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

        if not endpoint or not api_key:
            logger.warning("Azure OpenAI credentials not configured — SDK client unavailable")
            return None

        normalized_endpoint = _normalize_azure_endpoint(endpoint)
        if normalized_endpoint != endpoint:
            logger.warning(
                "Normalized AZURE_OPENAI_ENDPOINT to base URL",
                event_type="llm_factory",
                metadata={"original_path_present": True},
            )

        _openai_client = AzureOpenAI(
            azure_endpoint=normalized_endpoint,
            api_key=api_key,
            api_version=api_version,
        )

        logger.info("AzureOpenAI SDK client created", event_type="llm_factory")
        return _openai_client

    except ImportError:
        logger.warning("openai SDK not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to create AzureOpenAI client: {e}", exc_info=True)
        return None
