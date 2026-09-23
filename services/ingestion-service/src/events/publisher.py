import json
from datetime import datetime, timezone
import aio_pika
import structlog
from src.config.rabbitmq import get_channel, declare_exchange
from src.config.settings import settings

logger = structlog.get_logger()


async def publish_event(event_type: str, payload: dict) -> None:
    """
    Publish an event to the poliwise.events exchange.

    Args:
        event_type: Event routing key (e.g., "document.uploaded")
        payload: Event payload dict
    """
    channel = await get_channel()
    exchange = await declare_exchange()

    event = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "payload": payload,
    }

    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(event).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=event_type,
    )

    logger.info("event_published", event_type=event_type)
