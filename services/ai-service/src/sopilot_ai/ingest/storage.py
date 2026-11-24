"""Read-only object storage access for the worker (TECH-V2-core-api §8.3)."""
from __future__ import annotations

from typing import Protocol


class ObjectNotFound(Exception):
    """The object key does not exist (transient: ``OBJECT_NOT_FOUND``, §5.1)."""


class StorageUnavailable(Exception):
    """Connection or server error; transient, recorded without a failure code."""


class ObjectStore(Protocol):
    def get(self, key: str) -> bytes: ...


class MinioObjectStore:
    """S3 API through the ``minio`` SDK with the read-only ai-service credential."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str,
                 secure: bool = False, region: str = "us-east-1") -> None:
        from minio import Minio

        # An explicit region skips the GetBucketLocation call that the read-only policy denies.
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure,
                             region=region)
        self._bucket = bucket

    def get(self, key: str) -> bytes:
        from minio.error import S3Error

        try:
            resp = self._client.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code in ("NoSuchKey", "NoSuchBucket", "NoSuchObject"):
                raise ObjectNotFound(key) from exc
            raise StorageUnavailable(exc.code) from exc
        except Exception as exc:  # noqa: BLE001 - network errors of urllib3 and friends
            raise StorageUnavailable(type(exc).__name__) from exc
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()
