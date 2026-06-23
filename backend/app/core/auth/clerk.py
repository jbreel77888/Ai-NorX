"""
Clerk authentication integration.
Properly verifies Clerk JWT tokens using JWKS.
"""
import logging
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
import httpx
import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Tenant, User

logger = logging.getLogger(__name__)

# Clerk's JWKS URL (per-instance, fetched from Clerk API)
# For development instance, the issuer URL is typically: https://<frontend-api>.clerk.accounts.dev
# We'll discover it dynamically from the JWT issuer claim

# Cache JWKS clients per issuer
_jwks_clients: dict[str, PyJWKClient] = {}


def _get_jwks_client(issuer: str) -> PyJWKClient:
    """Get or create a JWKS client for the given issuer."""
    if issuer not in _jwks_clients:
        jwks_url = f"{issuer}/.well-known/jwks.json"
        _jwks_clients[issuer] = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
        logger.info(f"Initialized JWKS client for {jwks_url}")
    return _jwks_clients[issuer]


async def verify_clerk_token(token: str) -> Optional[dict]:
    """
    Verify a Clerk JWT token using JWKS.

    Clerk session tokens are JWTs signed with RS256.
    We verify them using Clerk's public keys from JWKS.
    """
    try:
        # First, decode without verification to get the issuer
        unverified = jwt.decode(token, options={"verify_signature": False})
        issuer = unverified.get("iss")
        if not issuer:
            logger.warning("Token missing 'iss' claim")
            return None

        # Get JWKS client for this issuer
        jwks_client = _get_jwks_client(issuer)

        # Get the signing key
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Verify the token
        verified = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,  # Clerk tokens may have different audiences
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
            },
        )

        return verified

    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {e}", exc_info=True)
        return None


async def get_clerk_user(user_id: str) -> Optional[dict]:
    """Fetch a user from Clerk's Backend API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.clerk.com/v1/users/{user_id}",
                headers={
                    "Authorization": f"Bearer {settings.CLERK_SECRET_KEY}",
                },
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Clerk API returned {response.status_code} for user {user_id}")
            return None
    except Exception as e:
        logger.error(f"Failed to fetch Clerk user: {e}")
        return None


async def get_or_create_user_from_clerk(
    db: AsyncSession,
    clerk_claims: dict,
) -> Optional[tuple[User, Tenant]]:
    """
    Get or create a user from Clerk JWT claims.
    Each user gets their own tenant (single-user tenant for MVP).
    """
    # JWT claims contain 'sub' (user_id) and metadata
    clerk_user_id = clerk_claims.get("sub")
    if not clerk_user_id:
        logger.warning("Token missing 'sub' claim")
        return None

    # Try to find existing user by clerk_user_id
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Update last login time (use naive datetime to match DB schema)
        user.last_login_at = datetime.utcnow()
        await db.flush()

        # Get tenant
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one()
        return user, tenant

    # New user - fetch details from Clerk API
    clerk_user = await get_clerk_user(clerk_user_id)
    if not clerk_user:
        logger.error(f"Failed to fetch user data from Clerk for {clerk_user_id}")
        return None

    email = ""
    if clerk_user.get("email_addresses"):
        email = clerk_user["email_addresses"][0].get("email_address", "")

    name = ""
    if clerk_user.get("first_name") or clerk_user.get("last_name"):
        name = f"{clerk_user.get('first_name', '')} {clerk_user.get('last_name', '')}".strip()
    elif clerk_user.get("username"):
        name = clerk_user["username"]

    avatar_url = clerk_user.get("image_url", "") or ""

    # Generate unique subdomain from email
    subdomain_base = email.split("@")[0] if email else f"user-{clerk_user_id[:8]}"
    subdomain = subdomain_base.lower().replace(".", "-").replace("_", "-")[:50]

    # Ensure unique subdomain
    existing = await db.execute(
        select(Tenant).where(Tenant.subdomain == subdomain)
    )
    if existing.scalar_one_or_none():
        subdomain = f"{subdomain}-{uuid4().hex[:6]}"

    # Create tenant
    tenant = Tenant(
        name=f"{name or email}'s Workspace",
        subdomain=subdomain,
        plan='free',
        is_active=True,
        clerk_org_id=clerk_user.get("organization_id"),
    )
    db.add(tenant)
    await db.flush()

    # Create user
    user = User(
        tenant_id=tenant.id,
        clerk_user_id=clerk_user_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
        role="admin",  # First user is admin
        is_active=True,
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()

    # Create default agent
    await _create_default_agent(db, tenant.id, user.id)

    logger.info(f"✅ Created new user: {email} (tenant: {subdomain})")

    return user, tenant


async def _create_default_agent(db: AsyncSession, tenant_id: UUID, user_id: UUID):
    """Create the universal 'NorX' agent - a general-purpose assistant like Manus AI."""
    from app.db.models import Agent, AgentVisibility

    default_agent = Agent(
        tenant_id=tenant_id,
        owner_id=user_id,
        name="NorX",
        description="وكيل ذكي عام ينفذ جميع المهام - مثل Manus AI",
        llm_provider="nvidia",
        llm_model="meta/llama-3.1-70b-instruct",
        system_prompt="""أنت "NorX" - وكيل ذكي عام قادر على تنفيذ أي مهمة يطلبها المستخدم، تماماً مثل Manus AI و Claude.

## هويتك
أنت مساعد ذكي سحابي عربي أولاً، تتحدث العربية بطلاقة وتساعد المستخدمين في أي مهمة.

## قدراتك
- **التفكير المنطقي**: حل المشكلات المعقدة خطوة بخطوة
- **البحث**: يمكنني البحث في الويب للحصول على معلومات حديثة
- **الكتابة**: كتابة محتوى عربي احترافي (مقالات، رسائل، أكواد، إلخ)
- **التحليل**: تحليل البيانات والنصوص والملفات
- **البرمجة**: كتابة وتصحيح الكود بلغات متعددة
- **الترجمة**: ترجمة دقيقة بين العربية واللغات الأخرى

## مبادئك
- **الدقة**: كن دقيقاً ومفيداً في كل رد
- **الوضوح**: استخدم اللغة العربية الفصحى ما لم يطلب المستخدم لهجة معينة
- **الصدق**: إذا لم تعرف الإجابة، اعترف بذلك بصراحة
- **التكيف**: كن مختصراً أو مفصلاً حسب حاجة المستخدم
- **التنسيق**: استخدم Markdown لجعل ردودك سهلة القراءة
- **التفكير**: فكّر خطوة بخطوة قبل الإجابة على الأسئلة المعقدة

## الأسلوب
- ابدأ بتحية ودية عندما يبدأ المستخدم المحادثة
- استخدم العناوين الفرعية (##) والقوائم لتنظيم الإجابات الطويلة
- استخدم كتل الكود (\`\`\`) للكود
- استخدم **النص العريض** للمصطلحات المهمة
- اختم بـ"هل تريد المزيد من المساعدة؟" عند الحاجة

أنت جزء من منصة "Ai NorX" - منصة الوكلاء الأذكياء العربية الأولى.""",
        temperature=0.7,
        max_tokens=4096,
        tools=["web_search", "web_fetch"],
        conversation_starters=[
            "مرحباً! كيف يمكنني مساعدتك اليوم؟",
            "اكتب لي مقالاً عن الذكاء الاصطناعي",
            "ساعدني في كتابة بريد إلكتروني",
        ],
        visibility=AgentVisibility.PRIVATE,
    )
    db.add(default_agent)
    await db.flush()
