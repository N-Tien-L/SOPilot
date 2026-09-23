import pytest
import asyncio
import os
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("JWT_SECRET", "test-jwt-secret-minimum-32-chars-long")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("RABBITMQ_URL", "amqp://test:test@localhost:567")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("EMBEDDING_URL", "http://localhost:80")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

from src.main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
