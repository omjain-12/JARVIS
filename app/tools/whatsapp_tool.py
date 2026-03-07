"""
WhatsApp Tool — sends WhatsApp messages via Twilio WhatsApp API or simulated mode.
"""

from __future__ import annotations

from typing import Any, Dict

from app.utils.logger import get_logger

logger = get_logger("whatsapp_tool")


async def send_whatsapp(
    phone_number: str,
    message: str,
    twilio_sid: str = "",
    twilio_token: str = "",
    twilio_from: str = "",
) -> Dict[str, Any]:
    """
    Send a WhatsApp message.

    Args:
        phone_number: Recipient phone number (E.164 format).
        message: Message content.
        twilio_sid: Twilio Account SID.
        twilio_token: Twilio Auth Token.
        twilio_from: Twilio WhatsApp-enabled sender number.

    Returns:
        Dict with status and details.
    """
    try:
        if not phone_number or not message:
            return {"status": "error", "message": "Phone number and message are required."}

        # Simulated mode
        if not twilio_sid:
            logger.info(
                f"[SIMULATED] WhatsApp to {phone_number}: {message[:50]}",
                event_type="whatsapp_simulated",
                metadata={"to": phone_number, "message_preview": message[:50]},
            )
            return {
                "status": "success",
                "message": f"WhatsApp sent to {phone_number} (simulated)",
                "details": {
                    "to": phone_number,
                    "message_preview": message[:100],
                    "simulated": True,
                },
            }

        # Real Twilio WhatsApp
        try:
            from twilio.rest import Client

            client = Client(twilio_sid, twilio_token)
            wa_message = client.messages.create(
                body=message,
                from_=f"whatsapp:{twilio_from}",
                to=f"whatsapp:{phone_number}",
            )
            logger.info(f"WhatsApp sent to {phone_number}, SID: {wa_message.sid}", event_type="whatsapp_sent")
            return {
                "status": "success",
                "message": f"WhatsApp sent to {phone_number}",
                "details": {"to": phone_number, "sid": wa_message.sid, "simulated": False},
            }
        except ImportError:
            logger.warning("Twilio library not installed. Using simulated mode.")
            return {
                "status": "success",
                "message": f"WhatsApp sent to {phone_number} (simulated)",
                "details": {"to": phone_number, "simulated": True},
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
