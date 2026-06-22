"""
Authentication dependencies for FastAPI.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.tenant.context import (
    TenantContext,
    get_current_tenant_id,
    get_current_user_id,
    get_current_user_role,
)
from app.core.auth import verify_clerk_token, get_or_create_user_from_clerk
from app.db import get_db
from app.db.models import User, Tenant

logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and verify the user from the request.
    Works with Bearer token from Clerk.
    """
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]  # Remove "Bearer "

    # Verify token with Clerk
    clerk_data = await verify_clerk_token(token)
    if not clerk_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Get or create user in DB
    result = await get_or_create_user_from_clerk(db, clerk_data.get("user", clerk_data))
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate user",
        )

    user, tenant = result

    # Set tenant context for this request
    request.state.tenant = tenant
    request.state.user = user

    return user


async def get_current_tenant(
    request: Request,
    user: User = Depends(get_current_user),
) -> Tenant:
    """Get current tenant from request state."""
    return request.state.tenant


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Require admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
