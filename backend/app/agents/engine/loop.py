"""
Agent Loop - with tool calling support.
Inspired by Nanobot AgentLoop + Onyx process_message.py
"""
import logging
import json
from typing import AsyncIterator, Optional, List
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant.context import get_current_tenant_id, get_current_user_id
from app.db.models import Agent, Conversation, Message, MessageRole
from app.llm import LLMMessage, LLMChunk, llm_gateway
from app.agents.tools import (
    get_registry,
    ToolContext,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


class AgentLoop:
    """Agent loop with tool calling support."""

    MAX_ITERATIONS = 5  # 1 initial + up to 4 follow-ups after tools
    MAX_TOOL_CALLS_PER_ITERATION = 3  # max parallel tool calls in one LLM response
    MAX_TOTAL_TOOL_CALLS = 6  # absolute max across entire turn

    def __init__(
        self,
        agent: Agent,
        db: AsyncSession,
    ):
        self.agent = agent
        self.db = db
        self.registry = get_registry()

    async def run(
        self,
        conversation: Conversation,
        user_message: str,
        attachments: Optional[List[dict]] = None,
    ) -> AsyncIterator[dict]:
        """Run the agent loop with tool calling."""
        # 1. Save user message
        user_msg = Message(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=user_message,
            attachments=attachments or [],
        )
        self.db.add(user_msg)
        await self.db.flush()
        await self.db.refresh(user_msg)

        yield {
            "type": "user_message_saved",
            "message_id": str(user_msg.id),
        }

        # 2. Load conversation history
        history = await self._load_history(conversation.id)

        # 3. Build initial LLM messages
        llm_messages = self._build_llm_messages(history, user_message)

        # 4. Get available tools (from agent config + default)
        tool_names = self.agent.tools or ["web_search"]
        tool_schemas = self.registry.get_openai_schemas(tool_names)

        # 5. Build tool context
        tool_context = ToolContext(
            tenant_id=conversation.tenant_id,
            user_id=conversation.user_id,
            agent_id=self.agent.id,
            conversation_id=conversation.id,
        )

        # 6. Agent loop - iterate until done or max iterations
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0
        finish_reason = None
        full_response = ""
        tool_calls_history = []
        all_citations = []
        iteration = 0
        tool_call_count = 0

        while iteration < self.MAX_ITERATIONS:
            iteration += 1

            # Stream LLM response
            iteration_text = ""
            iteration_tool_calls = []
            finish_reason = None

            try:
                async for chunk in llm_gateway.chat_stream(
                    messages=llm_messages,
                    model=self.agent.llm_model,
                    provider=self.agent.llm_provider,
                    temperature=self.agent.temperature,
                    max_tokens=self.agent.max_tokens,
                    tools=tool_schemas if tool_schemas else None,
                ):
                    if chunk.type == "text":
                        iteration_text += chunk.content
                        full_response += chunk.content
                        yield {
                            "type": "text",
                            "content": chunk.content,
                        }

                    elif chunk.type == "tool_call":
                        iteration_tool_calls.append(chunk.tool_call)

                    elif chunk.type == "usage":
                        total_input_tokens += chunk.input_tokens
                        total_output_tokens += chunk.output_tokens
                        total_cost += chunk.cost

                    elif chunk.type == "done":
                        finish_reason = chunk.finish_reason or "stop"

                    elif chunk.type == "error":
                        yield {"type": "error", "content": chunk.content}
                        return

            except Exception as e:
                logger.error(f"LLM streaming error: {e}", exc_info=True)
                yield {"type": "error", "content": f"خطأ في الاتصال بالـ LLM: {e}"}
                return

            # If no tool calls, we're done
            if not iteration_tool_calls:
                break

            # Cap tool calls per iteration (avoid LLM spamming many calls at once)
            iteration_tool_calls = iteration_tool_calls[:self.MAX_TOOL_CALLS_PER_ITERATION]

            # Check global tool call limit
            if tool_call_count + len(iteration_tool_calls) > self.MAX_TOTAL_TOOL_CALLS:
                # Tell LLM to wrap up - we've used enough tools
                llm_messages.append(LLMMessage(
                    role="system",
                    content="لقد استخدمت ما يكفي من الأدوات. استخدم المعلومات المتاحة لديك لكتابة الإجابة النهائية للمستخدم. لا تستدعِ المزيد من الأدوات.",
                ))
                # Continue loop to get final answer (no more tool calls will be allowed)
                iteration_tool_calls = []
                continue

            # Add assistant message with tool calls to history
            llm_messages.append(LLMMessage(
                role="assistant",
                content=iteration_text,
                tool_calls=iteration_tool_calls,
            ))

            # Execute each tool call
            for tc in iteration_tool_calls:
                tool_call_count += 1

                # Notify frontend that tool execution is starting
                yield {
                    "type": "tool_call_start",
                    "tool": tc.get("function", {}).get("name", "unknown"),
                    "arguments": tc.get("function", {}).get("arguments", ""),
                    "call_id": tc.get("id"),
                }

                # Parse arguments
                try:
                    args_str = tc.get("function", {}).get("arguments", "{}")
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}

                tool_name = tc.get("function", {}).get("name", "")
                tool_call_obj = ToolCall(
                    id=tc.get("id", ""),
                    name=tool_name,
                    arguments=args,
                )

                # Execute the tool
                result: ToolResult = await self.registry.execute(tool_call_obj, tool_context)

                # Format result for LLM
                if result.success:
                    result_text = result.output
                else:
                    result_text = f"خطأ: {result.error}"

                # Collect citations
                if result.citations:
                    all_citations.extend(result.citations)

                # Notify frontend
                yield {
                    "type": "tool_call_end",
                    "tool": tool_name,
                    "call_id": tc.get("id"),
                    "success": result.success,
                    "result_preview": result_text[:500],
                    "citations": result.citations[:5],
                    "execution_time_ms": result.execution_time_ms,
                }

                # Add tool result to LLM messages
                llm_messages.append(LLMMessage(
                    role="tool",
                    content=result_text,
                    tool_call_id=tc.get("id"),
                    tool_name=tool_name,
                ))

                tool_calls_history.append({
                    "id": tc.get("id"),
                    "name": tool_name,
                    "arguments": args,
                    "result": result_text[:1000],
                    "success": result.success,
                    "execution_time_ms": result.execution_time_ms,
                })

            # Continue the loop - LLM will process tool results

        # 7. Save assistant message
        assistant_msg = Message(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=full_response,
            tool_calls=tool_calls_history,
            model_used=self.agent.llm_model,
            provider=self.agent.llm_provider,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost=total_cost,
            is_streamed=True,
            stop_reason=finish_reason,
            citations=all_citations,
        )
        self.db.add(assistant_msg)

        # 8. Update conversation stats
        conversation.message_count += 2
        conversation.total_tokens += total_input_tokens + total_output_tokens
        conversation.total_cost += total_cost
        conversation.updated_at = datetime.utcnow()

        # Auto-rename conversation if first message
        if conversation.message_count == 2 and not conversation.title:
            conversation.title = user_message[:50] + ("..." if len(user_message) > 50 else "")

        await self.db.flush()
        await self.db.refresh(assistant_msg)

        yield {
            "type": "assistant_message_saved",
            "message_id": str(assistant_msg.id),
            "usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cost": total_cost,
            },
            "citations": all_citations,
            "finish_reason": finish_reason,
        }

        yield {"type": "done"}

    async def _load_history(self, conversation_id: UUID) -> List[Message]:
        """Load message history (last 20 messages)."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(20)
        )
        messages = result.scalars().all()
        return list(reversed(messages))

    def _build_llm_messages(
        self, history: List[Message], user_message: str
    ) -> List[LLMMessage]:
        """Build the message list for the LLM."""
        llm_messages = [LLMMessage(role="system", content=self.agent.system_prompt)]

        for msg in history:
            if msg.role == MessageRole.USER:
                llm_messages.append(LLMMessage(role="user", content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                llm_messages.append(LLMMessage(role="assistant", content=msg.content))

        return llm_messages
