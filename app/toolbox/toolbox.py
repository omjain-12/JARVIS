"""
Toolbox — unified tool registry for all available tools.

Provides a central interface for:
- Registering tools
- Discovering available tools
- Dispatching tool calls
- Validating tool parameters
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.utils.logger import get_logger

logger = get_logger("toolbox")


class Tool:
    """Represents a single registered tool."""

    def __init__(
        self,
        name: str,
        description: str,
        function: Callable,
        parameters: Dict[str, Any],
    ):
        self.name = name
        self.description = description
        self.function = function
        self.parameters = parameters

    def to_dict(self) -> Dict[str, Any]:
        """Return tool metadata as a dictionary (for LLM function calling)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                k: {"type": v.get("type", "string"), "description": v.get("description", "")}
                for k, v in self.parameters.items()
            },
        }

    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """Validate that required parameters are present."""
        for param_name, param_spec in self.parameters.items():
            if param_spec.get("required", False) and param_name not in params:
                return False, f"Missing required parameter: {param_name}"
        return True, ""


class Toolbox:
    """
    Central tool registry and dispatcher.

    Usage:
        toolbox = Toolbox()
        toolbox.register_defaults()
        result = await toolbox.execute("email_tool", {"recipient": "...", ...})
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, name: str, description: str, function: Callable,
                 parameters: Dict[str, Any]):
        """Register a tool."""
        tool = Tool(name=name, description=description, function=function, parameters=parameters)
        self._tools[name] = tool
        logger.debug(f"Tool registered: {name}")

    def register_from_metadata(self, metadata: Dict[str, Any]):
        """Register a tool from a TOOL_METADATA dict."""
        self.register(
            name=metadata["name"],
            description=metadata["description"],
            function=metadata["function"],
            parameters=metadata["parameters"],
        )

    def register_defaults(self):
        """Register all built-in tools."""
        from app.tools.email_tool import TOOL_METADATA as email_meta
        from app.tools.sms_tool import TOOL_METADATA as sms_meta
        from app.tools.whatsapp_tool import TOOL_METADATA as whatsapp_meta
        from app.tools.reminder_tool import TOOL_METADATA as reminder_meta
        from app.tools.habit_tracker_tool import TOOL_METADATA as habit_meta
        from app.tools.knowledge_store_tool import TOOL_METADATA as knowledge_meta

        for meta in [email_meta, sms_meta, whatsapp_meta, reminder_meta, habit_meta, knowledge_meta]:
            self.register_from_metadata(meta)

        logger.info(f"Registered {len(self._tools)} default tools", event_type="toolbox_init")

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return metadata for all registered tools."""
        return [tool.to_dict() for tool in self._tools.values()]

    def get_tool_names(self) -> List[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    def get_tools_description(self) -> str:
        """Return a formatted string describing all available tools (for LLM prompts)."""
        lines = []
        for tool in self._tools.values():
            params_desc = ", ".join(
                f"{k}: {v.get('type', 'string')}"
                for k, v in tool.parameters.items()
            )
            lines.append(f"- {tool.name}: {tool.description} | Parameters: ({params_desc})")
        return "\n".join(lines)

    async def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a registered tool by name.

        Args:
            tool_name: Name of the tool to execute.
            parameters: Dict of parameters to pass to the tool function.

        Returns:
            Tool execution result dict.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            logger.warning(f"Tool not found: {tool_name}")
            return {"status": "error", "message": f"Tool '{tool_name}' not found"}

        # Validate parameters
        valid, error_msg = tool.validate_params(parameters)
        if not valid:
            logger.warning(f"Invalid parameters for {tool_name}: {error_msg}")
            return {"status": "error", "message": error_msg}

        try:
            logger.log_tool_call(tool_name, parameters, "executing")
            result = await tool.function(**parameters)
            logger.log_tool_call(tool_name, parameters, result.get("status", "unknown"), str(result.get("message", "")))
            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}: {e}", exc_info=True)
            return {"status": "error", "message": f"Tool execution failed: {str(e)}"}
