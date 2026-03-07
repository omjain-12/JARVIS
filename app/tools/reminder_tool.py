"""
Reminder Tool — creates and manages scheduled reminders in the database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.utils.logger import get_logger

logger = get_logger("reminder_tool")

# Reference to memory manager will be injected at runtime
_memory_manager = None


def set_memory_manager(mm):
    """Inject the memory manager dependency."""
    global _memory_manager
    _memory_manager = mm


async def create_reminder(
    user_id: str,
    title: str,
    message: str = "",
    remind_at: str = "",
) -> Dict[str, Any]:
    """
    Create a new reminder for the user.

    Args:
        user_id: The user ID.
        title: Reminder title.
        message: Reminder message/details.
        remind_at: ISO format datetime string for when to trigger the reminder.

    Returns:
        Dict with status and reminder details.
    """
    try:
        if not title:
            return {"status": "error", "message": "Reminder title is required."}

        if remind_at:
            try:
                remind_dt = datetime.fromisoformat(remind_at.replace("Z", "+00:00"))
            except ValueError:
                return {"status": "error", "message": f"Invalid datetime format: {remind_at}"}
        else:
            # Default: remind in 1 hour
            from datetime import timedelta
            remind_dt = datetime.now(timezone.utc) + timedelta(hours=1)

        if _memory_manager:
            result = await _memory_manager.create_reminder(user_id, title, message, remind_dt)
            logger.info(f"Reminder created: {title}", event_type="reminder_created", metadata=result)
            return {
                "status": "success",
                "message": f"Reminder '{title}' set for {remind_dt.isoformat()}",
                "details": result,
            }
        else:
            # Simulated mode
            logger.info(f"[SIMULATED] Reminder: {title} at {remind_dt.isoformat()}", event_type="reminder_simulated")
            return {
                "status": "success",
                "message": f"Reminder '{title}' set for {remind_dt.isoformat()} (simulated)",
                "details": {"title": title, "remind_at": remind_dt.isoformat(), "simulated": True},
            }

    except Exception as e:
        logger.error(f"Failed to create reminder: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to create reminder: {str(e)}"}


async def list_reminders(user_id: str) -> Dict[str, Any]:
    """List all pending reminders for the user."""
    try:
        if _memory_manager:
            reminders = await _memory_manager.get_reminders(user_id)
            return {"status": "success", "reminders": reminders, "count": len(reminders)}
        return {"status": "success", "reminders": [], "count": 0, "simulated": True}
    except Exception as e:
        logger.error(f"Failed to list reminders: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


TOOL_METADATA = {
    "name": "reminder_tool",
    "description": "Create a scheduled reminder for the user.",
    "function": create_reminder,
    "parameters": {
        "user_id": {"type": "string", "required": True, "description": "User ID"},
        "title": {"type": "string", "required": True, "description": "Reminder title"},
        "message": {"type": "string", "required": False, "description": "Reminder details"},
        "remind_at": {"type": "string", "required": False, "description": "ISO datetime for the reminder"},
    },
}
