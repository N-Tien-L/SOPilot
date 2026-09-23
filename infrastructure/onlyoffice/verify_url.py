#!/usr/bin/env python3
"""Verify MinIO presigned URL signature from OnlyOffice container perspective."""
import hmac
import hashlib
import urllib.parse
from datetime import datetime

# The presigned URL
url_str = "http://minio:9000/poliwise-documents/documents/21051730-04a9-45a6-af41-c7eff87e8be3/1779140875137.docx?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=minioadmin%2F20260519%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260519T003507Z&X-Amz-Expires=3600&X-Amz-SignedHeaders=host&X-Amz-Signature=d53cc2084a0db32784567337cf0a8ff9ca65996d40160fd3ec46d5b78ff78ab7"

parsed = urllib.parse.urlparse(url_str)
# Strip the scheme/host to get the path and query
path = parsed.path
query = parsed.query
print(f"Path: {path}")
print(f"Query: {query}")

# Check if the URL is valid (expiry check)
date_str = "20260519T003507Z"
date = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ")
now = datetime.utcnow()
print(f"URL date: {date}")
print(f"Now (UTC): {now}")
print(f"URL is from: {(now - date).total_seconds():.0f}s ago")
print(f"Expires in: {3600 - (now - date).total_seconds():.0f}s")
