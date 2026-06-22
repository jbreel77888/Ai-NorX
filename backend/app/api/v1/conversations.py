"""Conversations endpoints."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.auth.deps import get_current_user
from app.db import get_db
from app.db.models import Conversation, Message, MessageRole, Agent

router = APIRouter()


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    agent_id: Optional[str] = None


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str]
    agent_id: Optional[str]
    message_count: int
    total_tokens: int
    total_cost: float
    is_pinned: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    reasoning: Optional[str]
    tool_calls: List[dict]
    model_used: Optional[str]
    provider: Optional[str]
    input_tokens: int
    output_tokens: int
    cost: float
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """List user's conversations."""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == user.tenant_id,
            Conversation.user_id == user.id,
            Conversation.is_archived == False,
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    conversations = result.scalars().all()
    return [
        ConversationResponse(
            id=str(c.id),
            title=c.title,
            agent_id=str(c.agent_id) if c.agent_id else None,
            message_count=c.message_count,
            total_tokens=c.total_tokens,
            total_cost=c.total_cost,
            is_pinned=c.is_pinned,
            is_archived=c.is_archived,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in conversations
    ]


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation."""
    agent_id = None
    if data.agent_id:
        agent_id = UUID(data.agent_id)

    conv = Conversation(
        tenant_id=user.tenant_id,
        user_id=user.id,
        agent_id=agent_id,
        title=data.title or "محادثة جديدة",
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)

    return ConversationResponse(
        id=str(conv.id),
        title=conv.title,
        agent_id=str(conv.agent_id) if conv.agent_id else None,
        message_count=conv.message_count,
        total_tokens=conv.total_tokens,
        total_cost=conv.total_cost,
        is_pinned=conv.is_pinned,
        is_archived=conv.is_archived,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == user.tenant_id,
            Conversation.user_id == user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        id=str(conv.id),
        title=conv.title,
        agent_id=str(conv.agent_id) if conv.agent_id else None,
        message_count=conv.message_count,
        total_tokens=conv.total_tokens,
        total_cost=conv.total_cost,
        is_pinned=conv.is_pinned,
        is_archived=conv.is_archived,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == user.tenant_id,
            Conversation.user_id == user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    conversation_id: UUID,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, le=500),
):
    """List messages in a conversation."""
    # Verify access
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == user.tenant_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return [
        MessageResponse(
            id=str(m.id),
            role=m.role.value,
            content=m.content,
            reasoning=m.reasoning,
            tool_calls=m.tool_calls or [],
            model_used=m.model_used,
            provider=m.provider,
            input_tokens=m.input_tokens,
            output_tokens=m.output_tokens,
            cost=m.cost,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: UUID,
    data: dict,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update conversation (title, pinned, archived)."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == user.tenant_id,
            Conversation.user_id == user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if "title" in data:
        conv.title = data["title"]
    if "is_pinned" in data:
        conv.is_pinned = data["is_pinned"]
    if "is_archived" in data:
        conv.is_archived = data["is_archived"]

    return {"status": "updated"}
