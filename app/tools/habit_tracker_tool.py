"""Habit Tracker Tool — logs habit completions and tracks streaks."""

from __future__ import annotations

from typing import Any, Dict

from app.utils.logger import get_logger

logger = get_logger("habit_tracker_tool")

_memory_manager = None


def set_memory_manager(mm):
    """Inject the memory manager dependency."""
    global _memory_manager
    _memory_manager = mm


async def log_habit(
    user_id: str,
    habit_name: str,
    notes: str = "",
) -> Dict[str, Any]:
    """Log a habit completion."""
    try:
        if not habit_name:
            return {"status": "error", "message": "Habit name is required."}

        if _memory_manager:
            # Find the habit by name
            habits = await _memory_manager.get_habits(user_id)
            habit = next((h for h in habits if h["name"].lower() == habit_name.lower()), None)

            if habit:
                result = await _memory_manager.log_habit(habit["id"], notes)
                logger.info(f"Habit logged: {habit_name}", event_type="habit_logged")
                return {
                    "status": "success",
                    "message": f"Habit '{habit_name}' logged successfully",
                    "details": result,
                }
            else:
                # Create the habit first, then log it
                new_habit = await _memory_manager.create_habit(user_id, habit_name)
                result = await _memory_manager.log_habit(new_habit["id"], notes)
                logger.info(f"New habit created and logged: {habit_name}", event_type="habit_created_and_logged")
                return {
                    "status": "success",
                    "message": f"New habit '{habit_name}' created and logged",
                    "details": result,
                }
        else:
            logger.info(f"[SIMULATED] Habit logged: {habit_name}", event_type="habit_simulated")
            return {
                "status": "success",
                "message": f"Habit '{habit_name}' logged (simulated)",
                "details": {"habit_name": habit_name, "simulated": True},
            }

    except Exception as e:
        logger.error(f"Failed to log habit: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to log habit: {str(e)}"}


async def get_habits(user_id: str) -> Dict[str, Any]:
    """Get all habits and their stats for the user."""
    try:
        if _memory_manager:
            habits = await _memory_manager.get_habits(user_id)
            return {"status": "success", "habits": habits, "count": len(habits)}
        return {"status": "success", "habits": [], "count": 0, "simulated": True}
    except Exception as e:
        logger.error(f"Failed to get habits: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


TOOL_METADATA = {
    "name": "habit_tracker_tool",
    "description": "Log a habit completion and track streaks.",
    "function": log_habit,
    "parameters": {
        "user_id": {"type": "string", "required": True, "description": "User ID"},
        "habit_name": {"type": "string", "required": True, "description": "Name of the habit"},
        "notes": {"type": "string", "required": False, "description": "Optional notes"},
    },
}
