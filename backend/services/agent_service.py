"""Agent service — thin wrapper that calls the JarvisWorkflow from the API layer."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict

from app.graph.workflow import JarvisWorkflow, build_workflow
from app.utils.logger import get_logger

logger = get_logger("agent_service")

_workflow: JarvisWorkflow | None = None


async def get_workflow() -> JarvisWorkflow:
    """Return the shared, initialised workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
        await _workflow.initialize()
        logger.info("AgentService: workflow initialised", event_type="agent_service_ready")
    return _workflow


async def run_agent(
    user_id: str,
    message: str,
    session_id: str = "",
) -> Dict[str, Any]:
    """Send a user message through the LangGraph agent pipeline."""
    wf = await get_workflow()
    result = await wf.run(
        user_input=message,
        user_id=user_id,
        session_id=session_id,
    )
    return result


async def run_agent_stream(
    user_id: str,
    message: str,
    session_id: str = "",
) -> AsyncIterator[str]:
    """Stream assistant text in small chunks for realtime UI updates."""
    result = await run_agent(user_id=user_id, message=message, session_id=session_id)
    text = result.get("response", {}).get("text", "")
    if not text:
        return

    words = text.split()
    if not words:
        yield text
        return

    # Yield words in small batches for a natural streaming feel
    batch_size = 3
    for i in range(0, len(words), batch_size):
        batch = " ".join(words[i : i + batch_size]) + " "
        yield batch
        await asyncio.sleep(0.04)  # ~25 batches/sec for smooth streaming


async def shutdown() -> None:
    """Gracefully shut down the workflow."""
    global _workflow
    if _workflow is not None:
        await _workflow.shutdown()
        _workflow = None
