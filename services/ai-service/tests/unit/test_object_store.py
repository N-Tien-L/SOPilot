"""The read-only MinIO credential has no ``s3:GetBucketLocation``: the store must not need it."""
from __future__ import annotations

from sopilot_ai.ingest.storage import MinioObjectStore


def test_region_is_explicit_so_no_bucket_location_lookup() -> None:
    store = MinioObjectStore("localhost:1", "ai-key", "ai-secret", "bucket", region="eu-west-1")
    # Resolved from the constructor: no HTTP call (nothing listens on :1).
    assert store._client._get_region("bucket") == "eu-west-1"  # noqa: SLF001


def test_region_defaults_to_core_api_default() -> None:
    store = MinioObjectStore("localhost:1", "ai-key", "ai-secret", "bucket")
    assert store._client._get_region("bucket") == "us-east-1"  # noqa: SLF001
