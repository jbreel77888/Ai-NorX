"""Agents endpoints."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.auth.deps import get_current_user, get_current_tenant, require_admin
from app.core.tenant.context import TenantContext
from app.db import get_db
from app.db.models import Agent, User, Tenant, AgentVisibility
from app.llm import get_all_available_models

router = APIRouter()


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=10)
    llm_provider: str = "nvidia"
    llm_model: str = "meta/llama-3.1-70b-instruct"
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: List[str] = []
    conversation_starters: List[str] = []
    visibility: AgentVisibility = AgentVisibility.PRIVATE


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[str]] = None
    conversation_starters: Optional[List[str]] = None
    visibility: Optional[AgentVisibility] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    system_prompt: str
    llm_provider: str
    llm_model: str
    temperature: float
    max_tokens: int
    tools: List[str]
    conversation_starters: List[str]
    visibility: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[AgentResponse])
async def list_agents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all agents for the current tenant."""
    result = await db.execute(
        select(Agent).where(
            Agent.tenant_id == user.tenant_id,
            (Agent.owner_id == user.id) | (Agent.visibility != AgentVisibility.PRIVATE),
        ).order_by(Agent.created_at.desc())
    )
    agents = result.scalars().all()
    return [
        AgentResponse(
            id=str(a.id),
            name=a.name,
            description=a.description,
            system_prompt=a.system_prompt,
            llm_provider=a.llm_provider,
            llm_model=a.llm_model,
            temperature=a.temperature,
            max_tokens=a.max_tokens,
            tools=a.tools or [],
            conversation_starters=a.conversation_starters or [],
            visibility=a.visibility.value,
            owner_id=str(a.owner_id),
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in agents
    ]


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    data: AgentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new agent."""
    # Check agent limit
    count_result = await db.execute(
        select(func.count(Agent.id)).where(Agent.tenant_id == user.tenant_id)
    )
    count = count_result.scalar()
    # For MVP, no limit enforced

    agent = Agent(
        tenant_id=user.tenant_id,
        owner_id=user.id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        llm_provider=data.llm_provider,
        llm_model=data.llm_model,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        tools=data.tools,
        conversation_starters=data.conversation_starters,
        visibility=data.visibility,
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)

    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        llm_provider=agent.llm_provider,
        llm_model=agent.llm_model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tools=agent.tools or [],
        conversation_starters=agent.conversation_starters or [],
        visibility=agent.visibility.value,
        owner_id=str(agent.owner_id),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific agent."""
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == user.tenant_id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        llm_provider=agent.llm_provider,
        llm_model=agent.llm_model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tools=agent.tools or [],
        conversation_starters=agent.conversation_starters or [],
        visibility=agent.visibility.value,
        owner_id=str(agent.owner_id),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    data: AgentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an agent."""
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == user.tenant_id,
            Agent.owner_id == user.id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)

    await db.flush()
    await db.refresh(agent)

    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        llm_provider=agent.llm_provider,
        llm_model=agent.llm_model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tools=agent.tools or [],
        conversation_starters=agent.conversation_starters or [],
        visibility=agent.visibility.value,
        owner_id=str(agent.owner_id),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an agent."""
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == user.tenant_id,
            Agent.owner_id == user.id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)


@router.get("/models/list")
async def list_models(
    user: User = Depends(get_current_user),
):
    """List all available LLM models."""
    return get_all_available_models()
