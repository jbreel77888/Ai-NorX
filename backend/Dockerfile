# Ai NorX Backend Dockerfile - optimized for Railway
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# Install Python dependencies (full list for production)
RUN pip install --upgrade pip && \
    pip install \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.32.0 \
    gunicorn>=23.0.0 \
    python-multipart>=0.0.12 \
    sqlalchemy[asyncio]>=2.0.35 \
    asyncpg>=0.30.0 \
    psycopg2-binary>=2.9.10 \
    alembic>=1.14.0 \
    pgvector>=0.3.6 \
    redis>=5.2.0 \
    upstash-redis>=1.2.0 \
    python-jose[cryptography]>=3.3.0 \
    passlib[bcrypt]>=1.7.4 \
    PyJWT>=2.10.0 \
    cryptography>=43.0.0 \
    httpx>=0.28.0 \
    pydantic>=2.10.0 \
    pydantic-settings>=2.6.0 \
    email-validator>=2.2.0 \
    openai>=1.55.0 \
    anthropic>=0.40.0 \
    litellm>=1.55.0 \
    tiktoken>=0.8.0 \
    numpy>=1.26.0 \
    pypdf>=5.1.0 \
    python-docx>=1.1.2 \
    openpyxl>=3.1.5 \
    markdown>=3.7 \
    beautifulsoup4>=4.12.3 \
    trafilatura>=2.0.0 \
    boto3>=1.35.0 \
    aioboto3>=13.3.0 \
    sentry-sdk[fastapi]>=2.18.0 \
    structlog>=24.4.0 \
    opentelemetry-api>=1.28.0 \
    opentelemetry-sdk>=1.28.0 \
    opentelemetry-instrumentation-fastapi>=0.49b0 \
    celery>=5.4.0 \
    python-dotenv>=1.0.1 \
    tenacity>=9.0.0 \
    orjson>=3.10.11 \
    websockets>=14.0 \
    python-dateutil>=2.9.0 \
    pyyaml>=6.0.2

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run the application with migrations
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
