"""
Tools module - all available tools.
"""
from .base import (
    BaseTool,
    ToolResult,
    ToolCall,
    ToolContext,
    ToolScope,
    ToolCategory,
)
from .registry import ToolRegistry, get_registry, registry
from .web_search import WebSearchTool, WebFetchTool
from .knowledge_search import KnowledgeSearchTool

# Initialize default tools
def init_default_tools():
    """Register all default tools."""
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    registry.register(KnowledgeSearchTool())
    return registry

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolCall",
    "ToolContext",
    "ToolScope",
    "ToolCategory",
    "ToolRegistry",
    "get_registry",
    "registry",
    "WebSearchTool",
    "WebFetchTool",
    "KnowledgeSearchTool",
    "init_default_tools",
]
