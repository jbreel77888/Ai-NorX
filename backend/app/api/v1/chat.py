"""
Chat endpoints - includes WebSocket for streaming.
"""
import json
import logging
from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.auth.clerk import verify_clerk_token, get_or_create_user_from_clerk
from app.core.tenant.context import TenantContext
from app.db import async_session_factory
from app.db.models import Conversation, Agent, User, Tenant
from app.agents.engine import AgentLoop

logger = logging.getLogger(__name__)

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str
    agent_id: Optional[str] = None
    conversation_id: Optional[str] = None
    attachments: Optional[list] = None


@router.post("/send")
async def send_message(
    data: SendMessageRequest,
    token: str,
    db: AsyncSession = Depends(),
):
    """Send a message and get a response (non-streaming for testing)."""
    # This is a placeholder - real streaming happens via WebSocket
    return {"status": "use websocket", "ws_url": "/api/v1/chat/ws"}


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket endpoint for streaming chat."""
    await websocket.accept()

    try:
        # Wait for auth message
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")
        if not token:
            await websocket.send_json({"type": "error", "content": "Missing token"})
            await websocket.close()
            return

        # Verify token
        clerk_data = await verify_clerk_token(token)
        if not clerk_data:
            await websocket.send_json({"type": "error", "content": "Invalid token"})
            await websocket.close()
            return

        # Get or create user - clerk_data is the JWT claims
        async with async_session_factory() as db:
            result = await get_or_create_user_from_clerk(db, clerk_data)
            if not result:
                await websocket.send_json({"type": "error", "content": "Auth failed"})
                await websocket.close()
                return

            user, tenant = result
            await db.commit()

        # Send auth success
        await websocket.send_json({
            "type": "auth_success",
            "user_id": str(user.id),
            "tenant_id": str(tenant.id),
        })

        # Main message loop
        while True:
            try:
                msg_data = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            msg_type = msg_data.get("type")
            if msg_type != "chat":
                continue

            content = msg_data.get("content", "").strip()
            if not content:
                continue

            agent_id = msg_data.get("agent_id")
            conversation_id = msg_data.get("conversation_id")

            if not agent_id:
                await websocket.send_json({
                    "type": "error",
                    "content": "agent_id required",
                })
                continue

            # Process in a new session with tenant context
            async with async_session_factory() as db:
                with TenantContext(tenant.id, user.id, user.role, user.email):
                    # Get agent
                    agent_result = await db.execute(
                        select(Agent).where(
                            Agent.id == UUID(agent_id),
                            Agent.tenant_id == tenant.id,
                        )
                    )
                    agent = agent_result.scalar_one_or_none()
                    if not agent:
                        await websocket.send_json({
                            "type": "error",
                            "content": "Agent not found",
                        })
                        continue

                    # Get or create conversation
                    if conversation_id:
                        conv_result = await db.execute(
                            select(Conversation).where(
                                Conversation.id == UUID(conversation_id),
                                Conversation.tenant_id == tenant.id,
                                Conversation.user_id == user.id,
                            )
                        )
                        conversation = conv_result.scalar_one_or_none()
                    else:
                        # Create new conversation
                        conversation = Conversation(
                            tenant_id=tenant.id,
                            user_id=user.id,
                            agent_id=agent.id,
                            title=content[:50] + ("..." if len(content) > 50 else ""),
                        )
                        db.add(conversation)
                        await db.flush()
                        await db.refresh(conversation)

                    await websocket.send_json({
                        "type": "conversation_created",
                        "conversation_id": str(conversation.id),
                    })

                    # Run agent loop
                    loop = AgentLoop(agent=agent, db=db)
                    async for event in loop.run(
                        conversation=conversation,
                        user_message=content,
                        attachments=msg_data.get("attachments"),
                    ):
                        await websocket.send_json(event)
                        if event.get("type") == "done":
                            break

                    await db.commit()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except:
            pass
