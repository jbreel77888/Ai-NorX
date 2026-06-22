"""
Database models for Ai NorX - multi-tenant SaaS AI Agent platform.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4, UUID
import enum

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, UUID as PGUUID,
    ForeignKey, JSON, Index, Enum as PGEnum, text, ForeignKeyConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.db.session import Base


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Enums
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PlanType(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class AgentVisibility(str, enum.Enum):
    PRIVATE = "private"
    SHARED = "shared"
    PUBLIC = "public"


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AgentStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tenant & Users
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Tenant(Base):
    """Tenant model - each customer = one tenant."""
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subdomain: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    custom_domain: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    plan: Mapped[PlanType] = mapped_column(PGEnum(PlanType), default=PlanType.FREE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Clerk integration
    clerk_org_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)

    # Quotas (per month)
    monthly_message_limit: Mapped[int] = mapped_column(Integer, default=1000)
    monthly_token_limit: Mapped[int] = mapped_column(Integer, default=500000)
    storage_limit_mb: Mapped[int] = mapped_column(Integer, default=50)
    agent_limit: Mapped[int] = mapped_column(Integer, default=3)

    # Settings
    settings: Mapped[Dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="tenant")
    agents: Mapped[List["Agent"]] = relationship(back_populates="tenant")
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="tenant")

    __table_args__ = (
        Index("idx_tenants_subdomain_active", "subdomain", "is_active"),
    )


class User(Base):
    """User model - belongs to a tenant."""
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(50), default="user")  # admin, user, viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    agents: Mapped[List["Agent"]] = relationship(back_populates="owner")
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="user")

    __table_args__ = (
        Index("idx_users_tenant_email", "tenant_id", "email"),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Agents & Conversations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Agent(Base):
    """Agent model - AI assistant configuration."""
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512))

    # LLM Configuration
    llm_provider: Mapped[str] = mapped_column(String(100), default="nvidia")
    llm_model: Mapped[str] = mapped_column(String(100), default="meta/llama-3.1-70b-instruct")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)

    # Tools
    tools: Mapped[List] = mapped_column(JSONB, default=list)
    skills: Mapped[List] = mapped_column(JSONB, default=list)

    # Knowledge
    knowledge_base_ids: Mapped[List] = mapped_column(JSONB, default=list)

    # Behavior
    max_iterations: Mapped[int] = mapped_column(Integer, default=25)
    allow_subagents: Mapped[bool] = mapped_column(Boolean, default=True)

    # Visibility
    visibility: Mapped[AgentVisibility] = mapped_column(
        PGEnum(AgentVisibility), default=AgentVisibility.PRIVATE
    )
    shared_with: Mapped[List] = mapped_column(JSONB, default=list)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Conversation starters
    conversation_starters: Mapped[List] = mapped_column(JSONB, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="agents")
    owner: Mapped["User"] = relationship(back_populates="agents")
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="agent")

    __table_args__ = (
        Index("idx_agents_tenant_owner", "tenant_id", "owner_id"),
        Index("idx_agents_visibility", "visibility"),
    )


class Conversation(Base):
    """Conversation model - a chat session."""
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[Optional[str]] = mapped_column(String(500))
    parent_message_id: Mapped[Optional[UUID]] = mapped_column(PGUUID)

    # State
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_temporary: Mapped[bool] = mapped_column(Boolean, default=False)

    # Tags
    tags: Mapped[List] = mapped_column(JSONB, default=list)

    # Usage stats
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="conversations")
    user: Mapped["User"] = relationship(back_populates="conversations")
    agent: Mapped[Optional["Agent"]] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_conversations_tenant_user_created", "tenant_id", "user_id", "created_at"),
    )


class Message(Base):
    """Message model - individual message in a conversation."""
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_message_id: Mapped[Optional[UUID]] = mapped_column(PGUUID)

    role: Mapped[MessageRole] = mapped_column(PGEnum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[Optional[str]] = mapped_column(Text)

    # Tool calls
    tool_calls: Mapped[List] = mapped_column(JSONB, default=list)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(100))
    tool_name: Mapped[Optional[str]] = mapped_column(String(100))

    # LLM info
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    provider: Mapped[Optional[str]] = mapped_column(String(50))

    # Usage
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Metadata
    citations: Mapped[List] = mapped_column(JSONB, default=list)
    attachments: Mapped[List] = mapped_column(JSONB, default=list)
    is_streamed: Mapped[bool] = mapped_column(Boolean, default=True)
    stop_reason: Mapped[Optional[str]] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("idx_messages_tenant_conversation_created", "tenant_id", "conversation_id", "created_at"),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Knowledge Base & Documents (RAG)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class KnowledgeBase(Base):
    """Knowledge base model - collection of documents."""
    __tablename__ = "knowledge_bases"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Owner
    owner_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Visibility
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    # Stats
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size_mb: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    documents: Mapped[List["Document"]] = relationship(
        back_populates="knowledge_base", cascade="all, delete-orphan"
    )


class Document(Base):
    """Document model - uploaded file in a knowledge base."""
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255))  # upload, web, connector
    file_type: Mapped[Optional[str]] = mapped_column(String(50))  # pdf, txt, md, docx
    file_size: Mapped[int] = mapped_column(Integer, default=0)

    # Content
    content: Mapped[Optional[str]] = mapped_column(Text)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)

    # Storage
    storage_url: Mapped[Optional[str]] = mapped_column(String(1024))

    # Indexing status
    indexing_status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, indexing, indexed, failed
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata (renamed from 'metadata' which is reserved in SQLAlchemy)
    doc_metadata: Mapped[Dict] = mapped_column("metadata", JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """Document chunk model - for RAG vector search."""
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Vector embedding (1536 for OpenAI, 1024 for BGE-M3)
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(1024))

    # Metadata (renamed from 'metadata' which is reserved in SQLAlchemy)
    chunk_metadata: Mapped[Dict] = mapped_column("metadata", JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("idx_chunks_tenant_kb", "tenant_id", "knowledge_base_id"),
        Index("idx_chunks_document", "document_id"),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Memory
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MemoryEntry(Base):
    """Short-term memory entry (consolidatable)."""
    __tablename__ = "memory_entries"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[Optional[UUID]] = mapped_column(PGUUID, index=True)

    cursor: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    is_consolidated: Mapped[bool] = mapped_column(Boolean, default=False)
    entry_metadata: Mapped[Dict] = mapped_column("metadata", JSONB, default=dict)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class LongTermMemory(Base):
    """Long-term memory (Dream output)."""
    __tablename__ = "long_term_memory"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)  # soul, user, memory, skill
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_hash: Mapped[Optional[str]] = mapped_column(String(64))
    last_dream_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Usage & Billing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class UsageRecord(Base):
    """Usage tracking for metering."""
    __tablename__ = "usage_records"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    usage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # messages, tokens, storage
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_metadata: Mapped[Dict] = mapped_column("metadata", JSONB, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_usage_tenant_type_timestamp", "tenant_id", "usage_type", "timestamp"),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Audit Log (hash-chained, immutable)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AuditLog(Base):
    """Tamper-evident audit log with hash chaining."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[UUID]] = mapped_column(PGUUID, index=True)
    chain_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    resource_id: Mapped[Optional[str]] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(20), default="success")
    severity: Mapped[str] = mapped_column(String(20), default="info")
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    audit_metadata: Mapped[Dict] = mapped_column("metadata", JSONB, default=dict)

    __table_args__ = (
        Index("idx_audit_tenant_chain_id", "tenant_id", "chain_key", "id"),
    )
