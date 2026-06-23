"""
Spawn Tool - يولّد subagent لمهمة فرعية.
مستوحى من Nanobot (agent/tools/spawn.py)
"""
import logging
from typing import Any, Dict, List
import json

from .base import BaseTool, ToolCategory, ToolScope, ToolResult, ToolContext

logger = logging.getLogger(__name__)


class SpawnTool(BaseTool):
    """يولّد وكيل فرعي (subagent) لمهمة محددة."""

    name = "spawn"
    display_name = "توليد وكيل فرعي"
    description = """يولّد وكيل فرعي (subagent) لتنفيذ مهمة فرعية محددة.

استخدم هذا عندما:
- تحتاج تقسيم مهمة معقدة إلى مهام فرعية
- تريد البحث عن عدة أشياء بالتوازي
- تحتاج تحليل عميق لموضوع معين

الوكيل الفرعي سينفذ المهمة ويعيد النتيجة لك لتدمجها في إجابتك."""

    category = ToolCategory.UTILITY
    scope = ToolScope.CORE  # only available to main agent, NOT subagents
    timeout_seconds = 60  # subagents may take longer

    def get_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "وصف المهمة التي يجب على الوكيل الفرعي تنفيذها. كن محدداً.",
                        },
                        "label": {
                            "type": "string",
                            "description": "اسم مختصر للمهمة (مثال: 'بحث عن الأسعار')",
                        },
                    },
                    "required": ["task", "label"],
                },
            },
        }

    async def execute(
        self,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        task = arguments.get("task", "").strip()
        label = arguments.get("label", "").strip()

        if not task:
            return ToolResult(
                success=False,
                output="",
                error="task is required",
            )

        if not label:
            label = task[:30]

        # Import here to avoid circular import
        from app.agents.subagent import SubagentManager
        from app.db.models import Agent, Conversation
        from sqlalchemy import select

        # We need to get the parent agent + conversation
        # This is stored in the context
        # For now, we'll use a simpler approach - get from DB

        # Get a db session
        from app.db.session import async_session_factory

        try:
            async with async_session_factory() as db:
                # Get the agent
                agent_result = await db.execute(
                    select(Agent).where(Agent.id == context.agent_id)
                )
                agent = agent_result.scalar_one_or_none()

                if not agent:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Agent not found",
                    )

                # Get or create a conversation context
                # We'll use a dummy conversation for the subagent
                conv_result = await db.execute(
                    select(Conversation).where(Conversation.id == context.conversation_id)
                )
                conversation = conv_result.scalar_one_or_none()

                if not conversation:
                    return ToolResult(
                        success=False,
                        output="",
                        error="Conversation not found",
                    )

                # Create subagent manager
                manager = SubagentManager(
                    parent_agent=agent,
                    db=db,
                    conversation=conversation,
                )

                # Spawn subagent and wait for result
                result = await manager.spawn(
                    task=task,
                    label=label,
                    tools_subset=["web_search", "knowledge_search"],
                )

                # Format output
                output = f"## نتيجة الوكيل الفرعي '{label}':\n\n{result}"

                return ToolResult(
                    success=True,
                    output=output,
                    data={
                        "label": label,
                        "task": task,
                        "iterations": manager.active_tasks.get(
                            list(manager.active_tasks.keys())[0]
                        ).iterations if manager.active_tasks else 0,
                        "tool_calls": manager.active_tasks.get(
                            list(manager.active_tasks.keys())[0]
                        ).tool_calls_count if manager.active_tasks else 0,
                    },
                )

        except Exception as e:
            logger.error(f"Spawn tool failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to spawn subagent: {e}",
            )
