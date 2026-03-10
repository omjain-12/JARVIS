"""Task Tool — creates and manages tasks in the database."""

from __future__ import annotations

from typing import Any, Dict

from app.utils.logger import get_logger

logger = get_logger("task_tool")

_memory_manager = None


def set_memory_manager(mm):
    """Inject the memory manager dependency."""
    global _memory_manager
    _memory_manager = mm


async def create_task(
    user_id: str,
    title: str,
    description: str = "",
    priority: int = 0,
) -> Dict[str, Any]:
    """Create a new task for the user."""
    try:
        if not title:
            return {"status": "error", "message": "Task title is required."}

        if _memory_manager:
            result = await _memory_manager.create_task(
                user_id=user_id,
                title=title,
                description=description,
                priority=priority,
            )
            logger.info(f"Task created: {title}", event_type="task_created", metadata=result)
            return {
                "status": "success",
                "message": f"Task '{title}' has been added.",
                "details": result,
            }
        else:
            logger.info(f"[SIMULATED] Task: {title}", event_type="task_simulated")
            return {
                "status": "success",
                "message": f"Task '{title}' has been added (simulated).",
                "details": {"title": title, "simulated": True},
            }

    except Exception as e:
        logger.error(f"Failed to create task: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to create task: {str(e)}"}


TOOL_METADATA = {
    "name": "task_tool",
    "description": "Create a new task or to-do item for the user.",
    "function": create_task,
    "parameters": {
        "user_id": {"type": "string", "required": True, "description": "User ID"},
        "title": {"type": "string", "required": True, "description": "Task title"},
        "description": {"type": "string", "required": False, "description": "Task description or details"},
        "priority": {"type": "integer", "required": False, "description": "Priority: 0=low, 1=medium, 2=high"},
    },
}
