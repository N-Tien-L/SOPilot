#!/usr/bin/env python3
import requests
import json
import sys

BASE_URL = "http://localhost:3001"

# Login
print("1. Logging in...")
login_resp = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    json={"username": "admin", "password": "Admin@123456"}
)
if login_resp.status_code != 200:
    print(f"Login failed: {login_resp.status_code} - {login_resp.text}")
    sys.exit(1)

token = login_resp.json()["accessToken"]
print(f"Token obtained: {token[:50]}...")

headers = {"Authorization": f"Bearer {token}"}

# Upload a test document
print("\n2. Uploading test document...")
test_content = """Test Document for Extractor and Duplicate Detection

This is a unique test document to verify:
1. Document extraction works
2. Duplicate detection works
3. Processing pipeline is functional

Timestamp: 2026-06-26 20:03
"""

files = {
    "file": ("test_duplicate_2.txt", open("test_duplicate_2.txt", "r", encoding="utf-8").read(), "text/plain")
}

upload_resp = requests.post(
    f"{BASE_URL}/api/v1/documents/upload",
    files=files,
    headers=headers,
    timeout=60
)

print(f"Upload response: {upload_resp.status_code}")
print(f"Response: {upload_resp.text[:500]}")

if upload_resp.status_code in [200, 201]:
    data = upload_resp.json()
    doc_id = data.get("data", {}).get("id") or data.get("id")
    print(f"\nDocument ID: {doc_id}")
    
    # Check document status
    print("\n3. Checking document processing status...")
    if doc_id:
        status_resp = requests.get(
            f"{BASE_URL}/api/v1/documents/{doc_id}",
            headers=headers
        )
        print(f"Status response: {status_resp.status_code}")
        print(f"Status: {status_resp.text[:500]}")
        
        # Check for duplicates
        print("\n4. Testing duplicate detection...")
        dup_resp = requests.get(
            f"{BASE_URL}/api/v1/documents/check-duplicate",
            params={"filename": "test_extractor_api.txt", "contentHash": "test123"},
            headers=headers
        )
        print(f"Duplicate check response: {dup_resp.status_code}")
        print(f"Response: {dup_resp.text[:500]}")
else:
    print(f"Upload failed!")
    sys.exit(1)

print("\n=== Test Complete ===")
