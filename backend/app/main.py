"""
Ai NorX - FastAPI Main Application
Multi-tenant Cloud AI Agent Platform
"""
import logging
import re
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import settings
from app.api import api_router
from app.db import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize Sentry
if settings.SENTRY_DSN_BACKEND and settings.is_production:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN_BACKEND,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
        ],
        traces_sample_rate=0.1,
        environment=settings.ENVIRONMENT,
    )


def get_cors_origins() -> List[str]:
    """Get CORS origins - allow all Vercel preview URLs and configured origins."""
    origins = list(settings.CORS_ORIGINS)
    # Always allow localhost for development
    if "http://localhost:3000" not in origins:
        origins.append("http://localhost:3000")
    if "http://localhost:8000" not in origins:
        origins.append("http://localhost:8000")
    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info(f"🚀 Starting {settings.PROJECT_NAME} API...")
    logger.info(f"   Environment: {settings.ENVIRONMENT}")
    logger.info(f"   CORS Origins: {get_cors_origins()}")

    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")

    # Initialize tools
    try:
        from app.agents.tools import init_default_tools
        tools = init_default_tools()
        logger.info(f"✅ Tools initialized: {len(tools.list_all())} tools")
    except Exception as e:
        logger.error(f"❌ Tools init failed: {e}")

    yield

    logger.info(f"👋 Shutting down {settings.PROJECT_NAME} API...")


# Create FastAPI app
app = FastAPI(
    title=f"{settings.PROJECT_NAME} API",
    description="منصة الوكلاء الأذكياء العربية - Cloud AI Agent Platform",
    version="0.1.0",
    docs_url="/docs",  # Always enabled for debugging
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ━━━ Custom CORS Middleware (handles wildcards) ━━━
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse


class WildcardCORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware that supports wildcard origins like *.vercel.app"""

    def __init__(self, app, origins: List[str]):
        super().__init__(app)
        self.origins = origins
        # Compile regex patterns for wildcards
        self.patterns = []
        for origin in origins:
            if "*" in origin:
                # Convert wildcard to regex: *.vercel.app -> .*\.vercel\.app
                pattern = re.escape(origin).replace(r"\*", ".*")
                self.patterns.append(re.compile(f"^{pattern}$"))
                logger.info(f"  CORS pattern: {pattern}")
            else:
                self.patterns.append(re.compile(f"^{re.escape(origin)}$"))

    def _origin_allowed(self, origin: str) -> bool:
        return any(p.match(origin) for p in self.patterns)

    async def dispatch(self, request: StarletteRequest, call_next):
        origin = request.headers.get("origin", "")

        # Handle preflight OPTIONS
        if request.method == "OPTIONS":
            response = StarletteResponse(status_code=204)
        else:
            response = await call_next(request)

        # Add CORS headers if origin is allowed
        if origin and self._origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Requested-With, X-Tenant-Id, Idempotency-Key"
            response.headers["Access-Control-Expose-Headers"] = "*"
            response.headers["Access-Control-Max-Age"] = "600"
            response.headers["Vary"] = "Origin"

        return response


app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(WildcardCORSMiddleware, origins=get_cors_origins())


# ━━━ Exception handlers ━━━
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
        },
    )


# ━━━ Routes ━━━
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.PROJECT_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "api": "/api/v1",
    }


# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
    )
