"""
Clerk authentication integration.
Verifies JWT tokens from Clerk and creates/updates users.
"""
import logging
from typing import Optional
from uuid import UUID, uuid4
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.tenant.context import TenantContext
from app.db.models import Tenant, User

logger = logging.getLogger(__name__)

# Clerk JWKS URL for token verification
CLERK_JWKS_URL = "https://api.clerk.com/v1/jwks"


async def verify_clerk_token(token: str) -> Optional[dict]:
    """Verify a Clerk JWT token and return claims."""
    try:
        # Use Clerk's Backend API for verification (simpler than JWT)
        # This calls Clerk to verify the session
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.clerk.com/v1/sessions/verify",
                headers={
                    "Authorization": f"Bearer {settings.CLERK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                json={"token": token},
            )
            if response.status_code == 200:
                return response.json()
            return None
    except Exception as e:
        logger.error(f"Clerk token verification failed: {e}")
        return None


async def get_or_create_user_from_clerk(
    db: AsyncSession,
    clerk_user_data: dict,
) -> Optional[tuple[User, Tenant]]:
    """
    Get or create a user from Clerk data.
    Each user gets their own tenant (single-user tenant for MVP).
    """
    clerk_user_id = clerk_user_data.get("id")
    if not clerk_user_id:
        return None

    email = ""
    if clerk_user_data.get("email_addresses"):
        email = clerk_user_data["email_addresses"][0].get("email_address", "")

    name = ""
    if clerk_user_data.get("first_name") or clerk_user_data.get("last_name"):
        name = f"{clerk_user_data.get('first_name', '')} {clerk_user_data.get('last_name', '')}".strip()
    elif clerk_user_data.get("username"):
        name = clerk_user_data["username"]

    avatar_url = clerk_user_data.get("image_url", "")

    # Try to find existing user by clerk_user_id
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Update user info
        user.email = email
        user.name = name
        user.avatar_url = avatar_url
        user.last_login_at = __import__("datetime").datetime.utcnow()
        await db.flush()

        # Get tenant
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one()
        return user, tenant

    # Create new tenant + user
    # Use part of email as subdomain
    subdomain_base = email.split("@")[0] if email else f"user-{clerk_user_id[:8]}"
    subdomain = subdomain_base.lower().replace(".", "-").replace("_", "-")[:50]

    # Ensure unique subdomain
    existing = await db.execute(
        select(Tenant).where(Tenant.subdomain == subdomain)
    )
    if existing.scalar_one_or_none():
        subdomain = f"{subdomain}-{uuid4().hex[:6]}"

    tenant = Tenant(
        name=f"{name or email}'s Workspace",
        subdomain=subdomain,
        plan=PlanType.FREE,
        is_active=True,
        clerk_org_id=clerk_user_data.get("organization_id"),
    )
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        clerk_user_id=clerk_user_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
        role="admin",  # First user is admin
        is_active=True,
        last_login_at=__import__("datetime").datetime.utcnow(),
    )
    db.add(user)
    await db.flush()

    # Create default agent
    await _create_default_agent(db, tenant.id, user.id)

    return user, tenant


async def _create_default_agent(db: AsyncSession, tenant_id: UUID, user_id: UUID):
    """Create a default assistant agent for new users."""
    from app.db.models import Agent

    default_agent = Agent(
        tenant_id=tenant_id,
        owner_id=user_id,
        name="مساعد NorX",
        description="وكيل ذكي افتراضي يتحدث العربية بطلاقة",
        llm_provider="nvidia",
        llm_model="meta/llama-3.1-70b-instruct",
        system_prompt="""أنت مساعد ذكي اسمك "NorX"، تتحدث العربية بطلاقة وتساعد المستخدمين في مهامهم المختلفة.

مبادئك:
- كن دقيقاً ومفيداً
- استخدم اللغة العربية الفصحى ما لم يطلب المستخدم لهجة معينة
- إذا لم تعرف الإجابة، اعترف بذلك بصراحة
- كن مختصراً عندما يكون ذلك مناسباً، ومفصلاً عندما يحتاج المستخدم تفصيلاً
- استخدم التنسيق (markdown) لجعل ردودك سهلة القراءة

أنت جزء من منصة "Ai NorX" - منصة الوكلاء الأذكياء العربية.""",
        temperature=0.7,
        max_tokens=4096,
        tools=["web_search"],
        conversation_starters=[
            "مرحباً! كيف يمكنني مساعدتك اليوم؟",
            "اكتب لي مقالاً عن الذكاء الاصطناعي",
            "ساعدني في كتابة بريد إلكتروني",
        ],
    )
    db.add(default_agent)
    await db.flush()


# Import here to avoid circular import
from app.db.models import PlanType  # noqa: E402
