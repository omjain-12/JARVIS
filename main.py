"""JARVIS AI Second Brain — Application Entry Point."""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger("main")


def start_server() -> None:
    """Launch the FastAPI server via uvicorn."""
    import uvicorn

    host = settings.app.host
    port = settings.app.port
    debug = settings.app.debug

    logger.info(
        f"Starting JARVIS API on {host}:{port} (debug={debug})",
        event_type="server_start",
    )

    uvicorn.run(
        "api.api_server:app",
        host=host,
        port=port,
        reload=debug,
        log_level=settings.app.log_level.lower(),
    )


async def interactive_cli() -> None:
    """Simple interactive loop for testing the pipeline without the API server."""
    from app.graph.workflow import build_workflow

    print("\n[ JARVIS AI Second Brain — Interactive CLI ]")
    print("=" * 50)
    print("Type a question or command. Type 'exit' to quit.\n")

    wf = build_workflow()
    await wf.initialize()

    session_id = ""
    user_id = "cli_user"

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit", "q"}:
                print("\nGoodbye!")
                break

            result = await wf.run(user_input, user_id=user_id, session_id=session_id)

            # Display response
            status_icon = "[SUCCESS]" if result["status"] == "success" else "[ERROR]"
            print(f"\n{status_icon} JARVIS [{result['metadata'].get('request_type', '')}]:")
            print("-" * 40)
            print(result["response"]["text"])
            
            # Show structured data if present
            structured = result["response"].get("structured_data")
            if structured:
                print(f"\n* Structured data: {type(structured).__name__}")

            # Show metadata
            tools = result["metadata"].get("tools_used", [])
            if tools:
                print(f"* Tools used: {', '.join(tools)}")

            patterns = result["metadata"].get("patterns_detected", [])
            if patterns:
                print(f"* Patterns: {', '.join(patterns)}")

            print(f"* Latency: {result['metadata'].get('total_time_ms', 0):.0f}ms")
            print()

    finally:
        await wf.shutdown()


def main() -> None:
    """Parse arguments and start the appropriate mode."""
    parser = argparse.ArgumentParser(description="JARVIS AI Second Brain")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Start in interactive CLI mode instead of API server",
    )
    args = parser.parse_args()

    # Print startup banner
    print(r"""
       _   _    ______   __     __ ___  ____
      | | / \  |  _ \ \ / /    / _/ _|/ ___|
   _  | |/ _ \ | |_) \ V /____| | |  | |
  | |_| / ___ \|  _ < | |_____| | |  | |___
   \___/_/   \_\_| \_\|_|      |_|_|   \____|

   AI Second Brain — Personal Knowledge Manager
    """)

    # Validate configuration
    services = settings.validate_azure_services()
    configured = [k for k, v in services.items() if v]
    missing = [k for k, v in services.items() if not v]

    if configured:
        logger.info(f"Azure services configured: {', '.join(configured)}")
    if missing:
        logger.warning(f"Azure services NOT configured: {', '.join(missing)}")

    if args.cli:
        asyncio.run(interactive_cli())
    else:
        start_server()


if __name__ == "__main__":
    main()
