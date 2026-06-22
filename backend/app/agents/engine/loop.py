"""
Agent Loop - simplified for MVP.
Streams LLM responses and handles basic tool calls.
"""
import logging
from typing import AsyncIterator, Optional, List
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant.context import get_current_tenant_id, get_current_user_id
from app.db.models import Agent, Conversation, Message, MessageRole
from app.llm import LLMMessage, LLMChunk, llm_gateway

logger = logging.getLogger(__name__)


class AgentLoop:
    """Simplified agent loop for MVP."""

    def __init__(
        self,
        agent: Agent,
        db: AsyncSession,
    ):
        self.agent = agent
        self.db = db

    async def run(
        self,
        conversation: Conversation,
        user_message: str,
        attachments: Optional[List[dict]] = None,
    ) -> AsyncIterator[dict]:
        """
        Run the agent loop.
        Yields events for the WebSocket client.
        """
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

        # 3. Build LLM messages
        llm_messages = self._build_llm_messages(history, user_message)

        # 4. Stream LLM response
        full_response = ""
        tool_calls = []
        input_tokens = 0
        output_tokens = 0
        cost = 0.0
        finish_reason = None

        try:
            async for chunk in llm_gateway.chat_stream(
                messages=llm_messages,
                model=self.agent.llm_model,
                provider=self.agent.llm_provider,
                temperature=self.agent.temperature,
                max_tokens=self.agent.max_tokens,
            ):
                if chunk.type == "text":
                    full_response += chunk.content
                    yield {
                        "type": "text",
                        "content": chunk.content,
                    }

                elif chunk.type == "tool_call":
                    tool_calls.append(chunk.tool_call)
                    yield {
                        "type": "tool_call",
                        "tool_call": chunk.tool_call,
                    }

                elif chunk.type == "usage":
                    input_tokens += chunk.input_tokens
                    output_tokens += chunk.output_tokens
                    cost += chunk.cost

                elif chunk.type == "done":
                    finish_reason = chunk.finish_reason or "stop"

                elif chunk.type == "error":
                    yield {"type": "error", "content": chunk.content}
                    return

            # 5. Save assistant message
            assistant_msg = Message(
                tenant_id=conversation.tenant_id,
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=full_response,
                tool_calls=tool_calls,
                model_used=self.agent.llm_model,
                provider=self.agent.llm_provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                is_streamed=True,
                stop_reason=finish_reason,
            )
            self.db.add(assistant_msg)

            # 6. Update conversation stats
            conversation.message_count += 2
            conversation.total_tokens += input_tokens + output_tokens
            conversation.total_cost += cost
            conversation.updated_at = datetime.utcnow()

            await self.db.flush()
            await self.db.refresh(assistant_msg)

            yield {
                "type": "assistant_message_saved",
                "message_id": str(assistant_msg.id),
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": cost,
                },
                "finish_reason": finish_reason,
            }

            yield {"type": "done"}

        except Exception as e:
            logger.error(f"Agent loop error: {e}")
            yield {"type": "error", "content": str(e)}

    async def _load_history(self, conversation_id: UUID) -> List[Message]:
        """Load message history (last 20 messages)."""
        result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
            )
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
