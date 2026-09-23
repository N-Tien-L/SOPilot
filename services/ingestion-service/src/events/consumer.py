import json
import structlog
from aio_pika import IncomingMessage
from src.config.rabbitmq import get_channel
from src.config.settings import settings

logger = structlog.get_logger()


async def on_ingestion_requested(message: IncomingMessage) -> None:
    """
    Handle ingestion.requested event from RabbitMQ.
    Starts the extraction pipeline for a document.
    """
    async with message.process():
        try:
            payload = json.loads(message.body.decode("utf-8"))
            job_id = payload.get("payload", {}).get("job_id")
            document_id = payload.get("payload", {}).get("document_id")
            version_id = payload.get("payload", {}).get("document_version_id")
            document_version = payload.get("payload", {}).get("document_version")
            file_key = payload.get("payload", {}).get("file_key")
            bucket_name = payload.get("payload", {}).get("bucket_name", "poliwise-documents")
            metadata = payload.get("payload", {}).get("metadata", {})

            logger.info(
                "ingestion_requested",
                job_id=job_id,
                document_id=document_id,
                version_id=version_id,
                document_version=document_version,
            )

            from uuid import UUID
            from src.services.pipeline import pipeline

            result = await pipeline.process(
                document_id=UUID(document_id),
                version_id=UUID(version_id),
                document_version=int(document_version),
                job_id=UUID(job_id),
                bucket_name=bucket_name,
                file_key=file_key,
                metadata=metadata,
            )

            logger.info("ingestion_completed", job_id=job_id, result=result)

        except Exception as e:
            logger.error("ingestion_failed", error=str(e))
            raise


async def on_document_deleted(message: IncomingMessage) -> None:
    """
    Handle document.deleted event from RabbitMQ.
    Soft-deletes all chunks for the document.
    """
    async with message.process():
        try:
            payload = json.loads(message.body.decode("utf-8"))
            document_id = payload.get("payload", {}).get("document_id")

            logger.info("document_deleted", document_id=document_id)

            from uuid import UUID
            from src.db.session import async_session
            from src.db.repositories.chunk_repo import ChunkRepository

            async with async_session() as session:
                chunk_repo = ChunkRepository(session)
                deleted_count = await chunk_repo.soft_delete_chunks(UUID(document_id))
                await session.commit()
                logger.info("chunks_soft_deleted", document_id=document_id, count=deleted_count)

        except Exception as e:
            logger.error("deletion_failed", error=str(e))
            raise  # Re-raise for retry


async def setup_consumers() -> None:
    """Setup RabbitMQ consumers for ingestion events."""
    channel = await get_channel()

    # Declare ingestion requests queue
    queue = await channel.declare_queue(
        "ingestion.requests",
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": "ingestion.requests.dlq",
        },
    )

    # Bind to exchange
    from src.config.rabbitmq import declare_exchange
    exchange = await declare_exchange()
    await queue.bind(exchange, routing_key="ingestion.requested")

    # Start consuming
    await queue.consume(on_ingestion_requested)

    # Declare document deleted queue
    deleted_queue = await channel.declare_queue(
        "ingestion.document.deleted",
        durable=True,
    )
    await deleted_queue.bind(exchange, routing_key="document.deleted")
    await deleted_queue.consume(on_document_deleted)

    logger.info("consumers_setup_complete")
