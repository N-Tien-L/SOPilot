import aio_pika
from src.config.settings import settings

# Module-level connection pool
_connection: aio_pika.Connection | None = None
_channel: aio_pika.Channel | None = None


async def get_connection() -> aio_pika.Connection:
    """Get or create RabbitMQ connection."""
    global _connection
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    return _connection


async def get_channel() -> aio_pika.Channel:
    """Get or create RabbitMQ channel."""
    global _channel
    if _channel is None or _channel.is_closed:
        connection = await get_connection()
        _channel = await connection.channel()
        await _channel.set_qos(prefetch_count=10)
    return _channel


async def declare_exchange() -> aio_pika.Exchange:
    """Declare the main poliwise.events exchange."""
    channel = await get_channel()
    exchange = await channel.declare_exchange(
        settings.rabbitmq_exchange,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )
    return exchange


async def close() -> None:
    """Close RabbitMQ connection gracefully."""
    global _connection, _channel
    if _channel and not _channel.is_closed:
        await _channel.close()
        _channel = None
    if _connection and not _connection.is_closed:
        await _connection.close()
        _connection = None
