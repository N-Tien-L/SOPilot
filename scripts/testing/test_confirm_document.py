#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:3001"

# Login
print("1. Logging in...")
login_resp = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    json={"username": "admin", "password": "Admin@123456"}
)
token = login_resp.json()["accessToken"]
headers = {"Authorization": f"Bearer {token}"}

# Confirm the first test document
doc_id = "ca638e25-b94e-410f-a7de-ed690f2e588c"
print(f"\n2. Confirming document: {doc_id}")

confirm_data = {
    "title": "Test Document for Extractor",
    "description": "Testing document extraction and processing",
    "categorySlug": "general",
    "tags": ["test", "extraction"],
    "isPolicy": False
}

confirm_resp = requests.post(
    f"{BASE_URL}/api/v1/documents/{doc_id}/confirm",
    json=confirm_data,
    headers=headers,
    timeout=30
)

print(f"Confirm response: {confirm_resp.status_code}")
print(f"Response: {confirm_resp.text[:500]}")

if confirm_resp.status_code == 200:
    print("\n3. Document confirmed! Waiting for processing...")
    
    # Wait a bit for processing to start
    import time
    time.sleep(3)
    
    # Check status
    docs_resp = requests.get(
        f"{BASE_URL}/api/v1/documents",
        headers=headers,
        timeout=30
    )
    if docs_resp.status_code == 200:
        docs = docs_resp.json()
        for doc in docs.get("data", {}).get("items", []):
            if doc.get("id") == doc_id:
                print(f"\nDocument status after confirmation: {doc.get('status')}")
                break
else:
    print(f"Confirm failed: {confirm_resp.text[:300]}")

print("\n=== Test Complete ===")
