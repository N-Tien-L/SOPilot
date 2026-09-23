import os
import tiktoken

os.environ.setdefault("INTERNAL_API_KEY", "test-internal-api-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("RABBITMQ_URL", "amqp://test:test@localhost:5672")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")


class _MockTokenizer:
    """Offline deterministic mock tokenizer for testing."""

    def encode(self, text: str) -> list[int]:
        return [ord(c) for c in text]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(t) for t in tokens if 0 <= t < 0x110000)


# Prevent tiktoken from making external HTTP requests to Azure Blob in tests
tiktoken.get_encoding = lambda *args, **kwargs: _MockTokenizer()
