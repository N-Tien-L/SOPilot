FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --default-timeout=1000 --no-cache-dir .

RUN useradd -r -s /bin/false appuser

COPY src/ ./src/

USER appuser

EXPOSE 8086

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8086"]