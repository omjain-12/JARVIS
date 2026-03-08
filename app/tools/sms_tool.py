"""
SMS Tool — sends SMS messages via Twilio or simulated mode.
"""

from __future__ import annotations

import os
import re
from importlib import import_module
from typing import Any, Dict

from dotenv import load_dotenv

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("sms_tool")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from provider error text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text or "")


def _normalize_phone_number(phone_number: str) -> str:
    """Normalize phone number to Twilio-friendly E.164 format."""
    digits = "".join(ch for ch in str(phone_number) if ch.isdigit())
    if len(digits) < 10:
        raise ValueError("Invalid phone number. Provide at least 10 digits.")

    if len(digits) == 10:
        cc = "".join(ch for ch in settings.twilio.default_country_code if ch.isdigit())
        if not cc:
            raise ValueError("TWILIO_DEFAULT_COUNTRY_CODE is invalid.")
        digits = f"{cc}{digits}"

    if len(digits) < 11 or len(digits) > 15:
        raise ValueError("Invalid international phone number. Use E.164 format, e.g. +919876543210")

    return f"+{digits}"


async def send_sms(
    phone_number: str,
    message: str,
    twilio_sid: str = "",
    twilio_token: str = "",
    twilio_from: str = "",
) -> Dict[str, Any]:
    """
    Send an SMS message.

    Args:
        phone_number: The recipient's phone number (E.164 format).
        message: The SMS message text.
        twilio_sid: Twilio Account SID (optional, simulates if empty).
        twilio_token: Twilio Auth Token.
        twilio_from: Twilio sender number.

    Returns:
        Dict with status and details.
    """
    try:
        # Reload .env on each call so long-running servers pick up latest sender config.
        load_dotenv(override=True)

        if not phone_number or not message:
            return {"status": "error", "message": "Phone number and message are required."}

        if len(message) > 1600:
            return {"status": "error", "message": "SMS message exceeds 1600 character limit."}

        to_number = _normalize_phone_number(phone_number)

        sid = twilio_sid or settings.twilio.account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        token = twilio_token or settings.twilio.auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        from_number = twilio_from or settings.twilio.from_number or os.getenv("TWILIO_FROM_NUMBER", "")
        messaging_service_sid = (
            settings.twilio.messaging_service_sid or os.getenv("TWILIO_MESSAGING_SERVICE_SID", "")
        )

        # Simulated mode is explicit only.
        if settings.twilio.simulate:
            logger.info(
                f"[SIMULATED] SMS to {to_number}: {message[:50]}",
                event_type="sms_simulated",
                metadata={"to": to_number, "message_preview": message[:50]},
            )
            return {
                "status": "success",
                "message": f"SMS sent to {to_number} (simulated)",
                "details": {
                    "to": to_number,
                    "message_preview": message[:100],
                    "simulated": True,
                },
            }

        if not (sid and token) or (not from_number and not messaging_service_sid):
            return {
                "status": "error",
                "message": (
                    "Twilio is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                    "and either TWILIO_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID in .env"
                ),
            }

        # Real Twilio sending
        try:
            twilio_rest = import_module("twilio.rest")
            Client = getattr(twilio_rest, "Client")
            client = Client(sid, token)

            payload = {"body": message, "to": to_number}
            if messaging_service_sid:
                payload["messaging_service_sid"] = messaging_service_sid
                sender_mode = "messaging_service_sid"
            else:
                payload["from_"] = from_number
                sender_mode = "from_number"

            sms = client.messages.create(**payload)
            logger.info(f"SMS sent to {to_number}, SID: {sms.sid}", event_type="sms_sent")
            return {
                "status": "success",
                "message": f"SMS sent to {to_number}",
                "details": {
                    "to": to_number,
                    "sid": sms.sid,
                    "status": getattr(sms, "status", None),
                    "sender_mode": sender_mode,
                    "sender": messaging_service_sid or from_number,
                    "simulated": False,
                },
            }
        except ImportError:
            logger.error("Twilio SDK not installed. Install dependency: pip install twilio")
            return {
                "status": "error",
                "message": "Twilio SDK not installed. Install dependency: pip install twilio",
                "details": {"to": to_number, "simulated": False},
            }
        except Exception as twilio_error:
            code = getattr(twilio_error, "code", None)
            cleaned = _strip_ansi(str(twilio_error))

            if code == 21659 or "21659" in cleaned:
                return {
                    "status": "error",
                    "message": (
                        "Twilio sender rejected (21659): TWILIO_FROM_NUMBER is not a valid Twilio sender "
                        "for this account/region. Use a Twilio-purchased SMS-enabled number, or set "
                        "TWILIO_MESSAGING_SERVICE_SID."
                    ),
                    "details": {
                        "to": to_number,
                        "twilio_error_code": 21659,
                        "twilio_error": cleaned,
                        "simulated": False,
                    },
                }

            return {
                "status": "error",
                "message": f"Failed to send SMS via Twilio: {cleaned}",
                "details": {
                    "to": to_number,
                    "twilio_error_code": code,
                    "simulated": False,
                },
            }
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send SMS: {str(e)}"}


TOOL_METADATA = {
    "name": "sms_tool",
    "description": "Send an SMS message to a phone number.",
    "function": send_sms,
    "parameters": {
        "phone_number": {"type": "string", "required": True, "description": "Recipient phone number"},
        "message": {"type": "string", "required": True, "description": "SMS message content"},
    },
}
