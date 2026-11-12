FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official image (pinned; 0.9.26 is the version used locally in this repo)
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup -d /home/appuser -m appuser

WORKDIR /app

# Copy dependency specifications first for layer caching
COPY pyproject.toml uv.lock ./

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies for the active configuration (config/models.yaml): local bge-m3 embeddings (local extra,
# also provides the tokenizer for chunking) and Docling PDF ingest (pdf extra, ADR-008).
# [tool.uv] package = false, so the project itself is never installed: the app runs from /app/src via PYTHONPATH.
RUN uv sync --frozen --no-dev --extra local --extra pdf --no-install-project

# Copy application source and config
COPY src/ ./src/
COPY config/ ./config/

# Set ownership
RUN chown -R appuser:appgroup /app /opt/venv

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH="/app/src"

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "--app-dir", "src", "sopilot_ai.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
