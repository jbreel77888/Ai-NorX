"""API v1 module."""
from fastapi import APIRouter

from .auth import router as auth_router
from .agents import router as agents_router
from .chat import router as chat_router
from .conversations import router as conversations_router
from .models import router as models_router
from .health import router as health_router
from .webhooks import router as webhooks_router
from .files import router as files_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
api_router.include_router(models_router, prefix="/models", tags=["models"])
api_router.include_router(files_router, prefix="/files", tags=["files"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])

__all__ = ["api_router"]
