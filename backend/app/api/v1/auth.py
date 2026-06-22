"""Auth endpoints."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from app.core.auth.deps import get_current_user, get_current_tenant
from app.db import get_db
from app.db.models import User, Tenant

logger = logging.getLogger(__name__)

router = APIRouter()


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    role: str
    tenant_id: str
    tenant_name: str
    plan: str

    class Config:
        from_attributes = True


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Get current authenticated user info."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        role=user.role,
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
        plan=tenant.plan,
    )


@router.post("/sync")
async def sync_user(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync user data from Clerk (called on login)."""
    return {
        "status": "synced",
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
    }
