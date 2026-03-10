"""Knowledge Store Tool — saves user-provided information into the vector knowledge base."""

from __future__ import annotations

from typing import Any, Dict

from app.utils.logger import get_logger

logger = get_logger("knowledge_store_tool")

_memory_manager = None


def set_memory_manager(mm):
    """Inject the memory manager dependency."""
    global _memory_manager
    _memory_manager = mm


async def store_knowledge(
    user_id: str,
    content: str,
    topic: str = "personal_info",
) -> Dict[str, Any]:
    """Store a piece of knowledge or personal information for the user."""
    try:
        if not content or not content.strip():
            return {"status": "error", "message": "Content is required."}

        if _memory_manager:
            result = await _memory_manager.store_user_fact(
                user_id=user_id,
                summary=content.strip(),
                key="explicit_memory_note",
                value=content.strip(),
                topic=topic,
                confidence=0.95,
            )
            logger.info(
                f"Knowledge stored: {content[:80]}",
                event_type="knowledge_stored",
                metadata={"topic": topic, "result": result},
            )
            return {
                "status": "success",
                "message": f"Information saved successfully under topic '{topic}'.",
                "details": {"content_preview": content[:100], "topic": topic, "storage": result},
            }
        else:
            # Simulated mode
            logger.info(
                f"[SIMULATED] Knowledge stored: {content[:80]}",
                event_type="knowledge_simulated",
            )
            return {
                "status": "success",
                "message": f"Information saved (simulated): {content[:80]}",
                "details": {"content_preview": content[:100], "topic": topic, "simulated": True},
            }

    except Exception as e:
        logger.error(f"Failed to store knowledge: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to store information: {str(e)}"}


async def recall_knowledge(user_id: str, query: str) -> Dict[str, Any]:
    """Search stored knowledge for the user."""
    try:
        if _memory_manager:
            results = await _memory_manager.search_knowledge(query, user_id, top_k=5)
            return {
                "status": "success",
                "results": results,
                "count": len(results),
            }
        return {"status": "success", "results": [], "count": 0, "simulated": True}
    except Exception as e:
        logger.error(f"Failed to recall knowledge: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


TOOL_METADATA = {
    "name": "knowledge_store_tool",
    "description": "Save user-provided information, facts, personal details, notes, or preferences into long-term memory so they can be recalled later.",
    "function": store_knowledge,
    "parameters": {
        "user_id": {"type": "string", "required": True, "description": "User ID"},
        "content": {"type": "string", "required": True, "description": "The information to save"},
        "topic": {"type": "string", "required": False, "description": "Category (e.g. personal_info, preference, note)"},
    },
}
