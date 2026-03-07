"""
Email Tool — sends emails via SMTP or Azure Communication Services.
"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict

from app.utils.logger import get_logger

logger = get_logger("email_tool")


async def send_email(
    recipient: str,
    subject: str,
    body: str,
    sender: str = "jarvis@assistant.ai",
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_password: str = "",
) -> Dict[str, Any]:
    """
    Send an email message.

    Args:
        recipient: Email address of the recipient.
        subject: Email subject line.
        body: Email body text.
        sender: Sender email address.
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port.
        smtp_user: SMTP auth username.
        smtp_password: SMTP auth password.

    Returns:
        Dict with status and details.
    """
    try:
        if not recipient or not subject:
            return {"status": "error", "message": "Recipient and subject are required."}

        # If SMTP is not configured, simulate sending
        if not smtp_host:
            logger.info(
                f"[SIMULATED] Email to {recipient}: {subject}",
                event_type="email_simulated",
                metadata={"to": recipient, "subject": subject},
            )
            return {
                "status": "success",
                "message": f"Email sent to {recipient} (simulated)",
                "details": {
                    "to": recipient,
                    "subject": subject,
                    "body_preview": body[:100],
                    "simulated": True,
                },
            }

        # Real SMTP sending
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(
            f"Email sent to {recipient}",
            event_type="email_sent",
            metadata={"to": recipient, "subject": subject},
        )
        return {
            "status": "success",
            "message": f"Email sent to {recipient}",
            "details": {"to": recipient, "subject": subject, "simulated": False},
        }

    except Exception as e:
        logger.error(f"Failed to send email: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send email: {str(e)}"}


# Tool metadata for the toolbox registry
TOOL_METADATA = {
    "name": "email_tool",
    "description": "Send an email to a specified recipient with a subject and body.",
    "function": send_email,
    "parameters": {
        "recipient": {"type": "string", "required": True, "description": "Recipient email address"},
        "subject": {"type": "string", "required": True, "description": "Email subject line"},
        "body": {"type": "string", "required": True, "description": "Email body content"},
    },
}
