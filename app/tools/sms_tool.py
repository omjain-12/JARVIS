"""
SMS Tool — sends SMS messages via Twilio or simulated mode.
"""

from __future__ import annotations

from typing import Any, Dict

from app.utils.logger import get_logger

logger = get_logger("sms_tool")


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
        if not phone_number or not message:
            return {"status": "error", "message": "Phone number and message are required."}

        if len(message) > 1600:
            return {"status": "error", "message": "SMS message exceeds 1600 character limit."}

        # Simulated mode if Twilio is not configured
        if not twilio_sid:
            logger.info(
                f"[SIMULATED] SMS to {phone_number}: {message[:50]}",
                event_type="sms_simulated",
                metadata={"to": phone_number, "message_preview": message[:50]},
            )
            return {
                "status": "success",
                "message": f"SMS sent to {phone_number} (simulated)",
                "details": {
                    "to": phone_number,
                    "message_preview": message[:100],
                    "simulated": True,
                },
            }

        # Real Twilio sending
        try:
            from twilio.rest import Client

            client = Client(twilio_sid, twilio_token)
            sms = client.messages.create(
                body=message,
                from_=twilio_from,
                to=phone_number,
            )
            logger.info(f"SMS sent to {phone_number}, SID: {sms.sid}", event_type="sms_sent")
            return {
                "status": "success",
                "message": f"SMS sent to {phone_number}",
                "details": {"to": phone_number, "sid": sms.sid, "simulated": False},
            }
        except ImportError:
            logger.warning("Twilio library not installed. Using simulated mode.")
            return {
                "status": "success",
                "message": f"SMS sent to {phone_number} (simulated — Twilio not installed)",
                "details": {"to": phone_number, "simulated": True},
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
