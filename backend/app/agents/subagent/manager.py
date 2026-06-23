"""
Subagent Manager - يدير الـ subagents.
مستوحى من Nanobot (agent/subagent.py) + LibreChat (@librechat/agents)

النمط: Subagent spawning
- الـ parent agent يستدعي spawn tool لتوليد subagent
- الـ subagent ينفذ المهمة في isolated context
- النتيجة تُحقن كـ tool result للـ parent (mid-turn injection)
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Agent, Conversation, Message, MessageRole
from app.llm import LLMMessage, LLMChunk, llm_gateway
from app.agents.tools import (
    get_registry,
    ToolContext,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


class SubagentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubagentTask:
    """حالة subagent."""
    task_id: str
    label: str
    task: str
    status: SubagentStatus = SubagentStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    iterations: int = 0
    tool_calls_count: int = 0


# Subagent system prompt
SUBAGENT_SYSTEM_PROMPT = """أنت وكيل فرعي (subagent) في منصة Ai NorX. تم تعيينك لمهمة محددة من الوكيل الرئيسي.

## مهمتك
{task}

## سياق من الوكيل الرئيسي
{parent_context}

## قواعد
- **ركز على مهمتك فقط** - لا تحاول القيام بمهام أخرى
- **كن مختصراً** - أعطِ النتيجة مباشرة بدون مقدمات
- **استخدم الأدوات المتاحة** إذا لزم الأمر
- **لا تولّد وكلاء فرعيين آخرين** - أنت في أدنى مستوى
- **إذا فشلت**، اشرح الخطأ بإيجاز

## الصيغة
اكتب نتيجة مهمتك مباشرة. ستُمرّر للوكيل الرئيسي."""


class SubagentManager:
    """يدير الـ subagents."""

    MAX_CONCURRENT = 2  # حد أقصى subagents متزامنين
    MAX_DEPTH = 1  # subagent لا يولّد subagent (depth 1 فقط)
    SUBAGENT_MAX_ITERATIONS = 3  # subagent له iterations أقل

    def __init__(
        self,
        parent_agent: Agent,
        db: AsyncSession,
        conversation: Conversation,
    ):
        self.parent_agent = parent_agent
        self.db = db
        self.conversation = conversation
        self.active_tasks: Dict[str, SubagentTask] = {}
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)

    async def spawn(
        self,
        task: str,
        label: str,
        tools_subset: Optional[List[str]] = None,
    ) -> str:
        """
        يولّد subagent جديد وينتظر نتيجته.

        يُرجع: النتيجة (string)
        """
        task_id = uuid4().hex[:8]
        subagent_task = SubagentTask(
            task_id=task_id,
            label=label,
            task=task,
            status=SubagentStatus.PENDING,
        )
        self.active_tasks[task_id] = subagent_task

        # Run subagent (synchronously - parent waits)
        async with self._semaphore:
            subagent_task.status = SubagentStatus.RUNNING
            subagent_task.started_at = datetime.utcnow()

            try:
                result = await self._run_subagent(subagent_task, tools_subset)
                subagent_task.result = result
                subagent_task.status = SubagentStatus.SUCCESS
                subagent_task.completed_at = datetime.utcnow()
                return result

            except Exception as e:
                logger.error(f"Subagent {task_id} failed: {e}", exc_info=True)
                subagent_task.error = str(e)
                subagent_task.status = SubagentStatus.FAILED
                subagent_task.completed_at = datetime.utcnow()
                return f"خطأ في الوكيل الفرعي: {e}"

    async def _run_subagent(
        self,
        subagent_task: SubagentTask,
        tools_subset: Optional[List[str]] = None,
    ) -> str:
        """ينفّذ subagent في isolated context."""
        # Build tool registry (subset - no spawn tool!)
        registry = get_registry()
        # Remove spawn tool from subagent's tools
        available_tools = tools_subset or ["web_search", "knowledge_search"]
        available_tools = [t for t in available_tools if t != "spawn"]
        tool_schemas = registry.get_openai_schemas(available_tools)

        # Build system prompt for subagent
        parent_context = f"المستخدم: {self.conversation.title or 'محادثة عامة'}"
        system_prompt = SUBAGENT_SYSTEM_PROMPT.format(
            task=subagent_task.task,
            parent_context=parent_context,
        )

        # Build LLM messages
        llm_messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=subagent_task.task),
        ]

        # Build tool context
        tool_context = ToolContext(
            tenant_id=self.conversation.tenant_id,
            user_id=self.conversation.user_id,
            agent_id=self.parent_agent.id,
            conversation_id=self.conversation.id,
        )

        # Run subagent loop (limited iterations)
        final_response = ""

        for iteration in range(self.SUBAGENT_MAX_ITERATIONS):
            subagent_task.iterations = iteration + 1

            iteration_text = ""
            tool_call_accumulator: dict[int, dict] = {}

            try:
                async for chunk in llm_gateway.chat_stream(
                    messages=llm_messages,
                    model=self.parent_agent.llm_model,
                    provider=self.parent_agent.llm_provider,
                    temperature=0.3,  # lower temp for focused task
                    max_tokens=2000,
                    tools=tool_schemas if tool_schemas else None,
                ):
                    if chunk.type == "text":
                        iteration_text += chunk.content
                        final_response += chunk.content

                    elif chunk.type == "tool_call":
                        tc = chunk.tool_call or {}
                        idx = tc.get("index", 0)
                        if idx not in tool_call_accumulator:
                            tool_call_accumulator[idx] = {
                                "id": tc.get("id", ""),
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        existing = tool_call_accumulator[idx]
                        if tc.get("id"):
                            existing["id"] = tc["id"]
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            existing["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            existing["function"]["arguments"] += fn["arguments"]

                    elif chunk.type == "error":
                        return f"خطأ: {chunk.content}"

            except Exception as e:
                logger.error(f"Subagent LLM error: {e}")
                return f"خطأ في الاتصال: {e}"

            # Process tool calls
            iteration_tool_calls = [
                tool_call_accumulator[i] for i in sorted(tool_call_accumulator)
            ]

            if not iteration_tool_calls:
                # No more tool calls, done
                break

            # Add assistant message with tool calls
            llm_messages.append(LLMMessage(
                role="assistant",
                content=iteration_text,
                tool_calls=iteration_tool_calls,
            ))

            # Execute tools
            for tc in iteration_tool_calls[:2]:  # max 2 tools per iteration
                subagent_task.tool_calls_count += 1

                import json
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}

                tool_call_obj = ToolCall(
                    id=tc.get("id", ""),
                    name=tc["function"]["name"],
                    arguments=args,
                )

                result: ToolResult = await registry.execute(tool_call_obj, tool_context)

                result_text = result.output if result.success else f"خطأ: {result.error}"

                llm_messages.append(LLMMessage(
                    role="tool",
                    content=result_text[:2000],  # truncate for subagent
                    tool_call_id=tc.get("id"),
                    tool_name=tc["function"]["name"],
                ))

        return final_response.strip() or "لا توجد نتيجة"

    def get_active_tasks(self) -> List[SubagentTask]:
        """يجلب كل الـ tasks النشطة."""
        return list(self.active_tasks.values())

    async def cancel_all(self):
        """يلغي كل الـ subagents النشطين."""
        for task in self.active_tasks.values():
            if task.status == SubagentStatus.RUNNING:
                task.status = SubagentStatus.CANCELLED
                task.completed_at = datetime.utcnow()
