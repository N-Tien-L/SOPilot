import os

os.environ.setdefault("INTERNAL_API_KEY", "test-internal-api-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("RABBITMQ_URL", "amqp://test:test@localhost:5672")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
