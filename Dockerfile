# Stage 1: Install Python dependencies (cached unless pyproject.toml changes)
FROM python:3.11-slim AS deps

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN python -c "\
import tomllib, pathlib; \
data = tomllib.loads(pathlib.Path('pyproject.toml').read_text()); \
deps = data['project']['dependencies']; \
pathlib.Path('requirements.txt').write_text('\n'.join(deps))" && \
    pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y pip setuptools 2>/dev/null; \
    find /usr/local/lib/python3.11/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
    find /usr/local/lib/python3.11/site-packages -name "*.pyc" -delete 2>/dev/null; \
    true

# Stage 2: Production image
FROM python:3.11-slim AS production

WORKDIR /app

# Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup alembic/ ./alembic/
COPY --chown=appuser:appgroup alembic.ini ./
COPY --chown=appuser:appgroup .env.example ./.env.example

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=3000

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:3000/api/v1/health/live')" || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3000"]
