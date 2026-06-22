"""Health check endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import httpx
import asyncio

from app.core.config import settings
from app.db import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "ok",
        "service": "Ai NorX API",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


@router.get("/health/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    """Database health check."""
    try:
        result = await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}


@router.get("/health/redis")
async def health_check_redis():
    """Redis health check."""
    try:
        # Use Upstash REST API for ping
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.UPSTASH_REDIS_REST_URL}/ping",
                headers={"Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"},
            )
            if response.status_code == 200:
                return {"status": "ok", "redis": "connected"}
            return {"status": "error", "redis": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "redis": str(e)}


@router.get("/health/llm")
async def health_check_llm():
    """LLM providers health check."""
    return {
        "status": "ok",
        "providers": {
            "nvidia": "configured" if settings.NVIDIA_API_KEY else "missing",
            "opencode": "configured" if settings.OPENCODE_API_KEY else "missing",
            "huggingface": "configured" if settings.HUGGINGFACE_TOKEN else "missing",
        },
    }
