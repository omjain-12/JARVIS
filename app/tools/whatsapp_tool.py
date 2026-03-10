"""WhatsApp Tool — sends WhatsApp messages via Whapi Cloud API."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict

import requests

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("whatsapp_tool")


def _normalize_whapi_to_number(phone_number: str) -> str:
    """Normalize input to Whapi destination format <countrycode+number>@s.whatsapp.net."""
    digits = "".join(ch for ch in str(phone_number) if ch.isdigit())

    if len(digits) < 10:
        raise ValueError("Invalid phone number. Provide at least 10 digits.")

    # If user provides local 10-digit number, prepend default country code.
    if len(digits) == 10:
        country_code = settings.whapi.default_country_code
        country_code_digits = "".join(ch for ch in country_code if ch.isdigit())
        if not country_code_digits:
            raise ValueError("WHAPI_DEFAULT_COUNTRY_CODE is invalid.")
        digits = f"{country_code_digits}{digits}"

    if len(digits) < 11 or len(digits) > 15:
        raise ValueError("Invalid international phone number. Use E.164 format, e.g. 919876543210")

    return f"{digits}@s.whatsapp.net"


def _post_whapi_message(api_token: str, base_url: str, to: str, body: str) -> Dict[str, Any]:
    """Blocking HTTP post to Whapi API (executed in thread by async wrapper)."""
    payload = {
        "typing_time": 0,
        "to": to,
        "body": body,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {api_token}",
    }

    attempts = max(1, settings.whapi.max_retries + 1)
    timeout = max(5, settings.whapi.timeout_seconds)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(base_url, json=payload, headers=headers, timeout=timeout)

            # Retry transient 5xx errors.
            if response.status_code >= 500 and attempt < attempts:
                time.sleep(0.6 * attempt)
                continue

            response.raise_for_status()
            return response.json() if response.content else {"status": "ok"}

        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            last_error = e
            if attempt >= attempts:
                break
            time.sleep(0.6 * attempt)

    raise RuntimeError(f"Whapi request failed after {attempts} attempts: {last_error}")


async def send_whatsapp(
    phone_number: str,
    message: str,
    api_token: str = "",
    base_url: str = "",
) -> Dict[str, Any]:
    """Send a WhatsApp message."""
    try:
        if not phone_number or not message:
            return {"status": "error", "message": "Phone number and message are required."}

        if len(message) > 4096:
            return {"status": "error", "message": "WhatsApp message exceeds 4096 character limit."}

        token = api_token or settings.whapi.token or os.getenv("WHAPI_TOKEN", "")
        if not token:
            return {
                "status": "error",
                "message": "WHAPI token not configured. Set WHAPI_TOKEN env var or pass api_token.",
            }

        effective_base_url = base_url or settings.whapi.base_url

        to = _normalize_whapi_to_number(phone_number)

        result = await asyncio.to_thread(
            _post_whapi_message,
            token,
            effective_base_url,
            to,
            message,
        )

        # Whapi may return HTTP 200 for accepted requests. Validate obvious error payloads.
        if isinstance(result, dict):
            lower_status = str(result.get("status", "")).lower()
            if result.get("error") or lower_status in {"error", "failed"}:
                return {
                    "status": "error",
                    "message": f"Whapi rejected message: {result.get('error') or lower_status}",
                    "details": {"to": to, "provider": "whapi", "response": result, "simulated": False},
                }

        logger.info(
            f"WhatsApp accepted by Whapi for {to}",
            event_type="whatsapp_sent",
            metadata={"to": to, "provider": "whapi"},
        )
        return {
            "status": "success",
            "message": (
                f"WhatsApp request accepted for {phone_number}. "
                "Delivery depends on recipient WhatsApp availability and account state."
            ),
            "details": {
                "to": to,
                "provider": "whapi",
                "message_id": result.get("id") if isinstance(result, dict) else None,
                "response": result,
                "simulated": False,
            },
        }

    except Exception as e:
        logger.error(f"Failed to send WhatsApp: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send WhatsApp: {str(e)}"}


TOOL_METADATA = {
    "name": "whatsapp_tool",
    "description": "Send a WhatsApp message to a phone number.",
    "function": send_whatsapp,
    "parameters": {
        "phone_number": {"type": "string", "required": True, "description": "Recipient phone number"},
        "message": {"type": "string", "required": True, "description": "WhatsApp message content"},
    },
}
