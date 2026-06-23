"""
Tools Framework - Base classes for tool definitions.
Inspired by Onyx (tools/built_in_tools.py) + Nanobot (agent/tools/base.py)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
import logging
import time
import asyncio

logger = logging.getLogger(__name__)


class ToolScope(str, Enum):
    """Tool execution scope - inspired by Nanobot."""
    CORE = "core"          # Available to main agent
    SUBAGENT = "subagent"  # Available to subagents only
    ALL = "all"            # Available everywhere


class ToolCategory(str, Enum):
    """Tool categories for UI grouping."""
    SEARCH = "search"
    CODE = "code"
    FILES = "files"
    KNOWLEDGE = "knowledge"
    WEB = "web"
    UTILITY = "utility"


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str
    data: Optional[Dict[str, Any]] = None
    citations: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    execution_time_ms: int = 0


@dataclass
class ToolCall:
    """A tool call from the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]


class BaseTool(ABC):
    """Base class for all tools - inspired by Onyx + Nanobot."""

    # Metadata (must be overridden)
    name: str = ""
    display_name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.UTILITY
    scope: ToolScope = ToolScope.ALL

    # Behavior flags
    is_async: bool = True
    is_dangerous: bool = False  # Requires user confirmation
    requires_confirmation: bool = False
    timeout_seconds: int = 30

    @abstractmethod
    def get_openai_schema(self) -> Dict[str, Any]:
        """Return OpenAI function-calling schema."""
        pass

    @abstractmethod
    async def execute(
        self,
        arguments: Dict[str, Any],
        context: "ToolContext",
    ) -> ToolResult:
        """Execute the tool with the given arguments."""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Get tool metadata for UI display."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category.value,
            "is_dangerous": self.is_dangerous,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class ToolContext:
    """Context passed to tools during execution."""
    tenant_id: UUID
    user_id: UUID
    agent_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    session_id: Optional[str] = None

    # Settings access (lazy-loaded)
    _settings: Dict[str, Any] = field(default_factory=dict)

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)
