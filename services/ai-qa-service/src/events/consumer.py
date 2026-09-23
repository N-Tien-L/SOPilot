import aio_pika
import json
import structlog
from typing import Optional

from ..config.settings import settings

logger = structlog.get_logger()


class RabbitMQConsumer:
    def __init__(self):
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None

    async def connect(self) -> None:
        try:
            self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            self._channel = await self._connection.channel()
            
            # Declare exchange
            exchange = await self._channel.declare_exchange(
                settings.rabbitmq_exchange,
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            # Declare queue for user status changes
            queue = await self._channel.declare_queue(
                "ai_qa.user_status_changes",
                durable=True
            )
            
            # Bind queue to exchange
            await queue.bind(exchange, routing_key="user.status.changed")
            
            # Start consuming
            await queue.consume(self._handle_user_status_changed)
            
            logger.info("rabbitmq_consumer_started", queue="ai_qa.user_status_changes")
        except Exception as e:
            logger.error("rabbitmq_consumer_connection_failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        if self._connection:
            await self._connection.close()
            logger.info("rabbitmq_consumer_disconnected")

    async def _handle_user_status_changed(self, message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                payload = json.loads(message.body.decode())
                event_type = payload.get("event_type")
                user_id = payload.get("payload", {}).get("user_id")
                new_status = payload.get("payload", {}).get("status")
                
                logger.info(
                    "user_status_changed_received",
                    event_type=event_type,
                    user_id=user_id,
                    new_status=new_status
                )
                
                # Logic per Option 2: Just log the change for now.
                # In the future, we could invalidate caches or close active conversations here.
                
            except Exception as e:
                logger.error("error_processing_user_status_event", error=str(e))


consumer = RabbitMQConsumer()
