import aio_pika
from aio_pika import Message, DeliveryMode
from typing import Optional
import structlog

from .settings import settings

logger = structlog.get_logger()


class RabbitMQPublisher:
    def __init__(self):
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        try:
            self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                settings.rabbitmq_exchange,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            logger.info("rabbitmq_connected", exchange=settings.rabbitmq_exchange)
        except Exception as e:
            logger.error("rabbitmq_connection_failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("rabbitmq_disconnected")

    async def publish(self, routing_key: str, message: dict) -> None:
        if not self._exchange:
            await self.connect()

        await self._exchange.publish(
            Message(
                body=message.encode() if isinstance(message, str) else str(message).encode(),
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT
            ),
            routing_key=routing_key
        )
        logger.debug("message_published", routing_key=routing_key)

    async def publish_json(self, routing_key: str, payload: dict) -> None:
        if not self._exchange:
            await self.connect()

        import json
        body = json.dumps(payload).encode()
        await self._exchange.publish(
            Message(
                body=body,
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT
            ),
            routing_key=routing_key
        )
        logger.debug("json_message_published", routing_key=routing_key)


publisher = RabbitMQPublisher()