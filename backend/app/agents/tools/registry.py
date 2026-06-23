"""
Tool Registry - manages all available tools.
Inspired by Onyx (tools/built_in_tools.py) + Nanobot (agent/tools/registry.py)
"""
from typing import Dict, List, Optional, Type
import logging

from .base import BaseTool, ToolScope, ToolContext, ToolResult, ToolCall

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for all available tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if not tool.name:
            raise ValueError(f"Tool must have a name: {tool.__class__.__name__}")
        self._tools[tool.name] = tool
        logger.info(f"  ✓ Registered tool: {tool.name} ({tool.display_name})")

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> List[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_by_scope(self, scope: ToolScope) -> List[BaseTool]:
        """List tools available for a given scope."""
        return [
            t for t in self._tools.values()
            if t.scope in (scope, ToolScope.ALL)
        ]

    def get_openai_schemas(
        self, tool_names: Optional[List[str]] = None
    ) -> List[Dict]:
        """Get OpenAI function schemas for specified tools (or all)."""
        tools = []
        for tool in self._tools.values():
            if tool_names and tool.name not in tool_names:
                continue
            schema = tool.get_openai_schema()
            schema["function"]["name"] = tool.name
            tools.append(schema)
        return tools

    async def execute(
        self,
        tool_call: ToolCall,
        context: ToolContext,
    ) -> ToolResult:
        """Execute a tool call safely with timeout."""
        tool = self.get(tool_call.name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_call.name}' not found",
            )

        start_time = time.time()
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                tool.execute(tool_call.arguments, context),
                timeout=tool.timeout_seconds,
            )
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Tool '{tool_call.name}' timed out after {tool.timeout_seconds}s")
            return ToolResult(
                success=False,
                output="",
                error=f"Tool timed out after {tool.timeout_seconds} seconds",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            logger.error(f"Tool '{tool_call.name}' failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output="",
                error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
            )


# Singleton
import time
import asyncio

registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return registry
