"""Models endpoint - list available LLM models."""
from fastapi import APIRouter, Depends

from app.core.auth.deps import get_current_user
from app.llm import get_all_available_models

router = APIRouter()


@router.get("")
async def list_models(user=Depends(get_current_user)):
    """List all available LLM models across providers."""
    return get_all_available_models()
