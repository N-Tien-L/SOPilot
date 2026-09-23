from minio import Minio
from src.config.settings import settings


class MinIOService:
    """Service for MinIO object storage operations."""

    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    async def download_file(self, bucket_name: str, file_key: str) -> bytes:
        """
        Download file from MinIO.
        Returns file bytes.
        """
        response = self.client.get_object(bucket_name, file_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def file_exists(self, bucket_name: str, file_key: str) -> bool:
        """Check if file exists in MinIO."""
        try:
            self.client.stat_object(bucket_name, file_key)
            return True
        except Exception:
            return False


# Global service instance
minio_service = MinIOService()
