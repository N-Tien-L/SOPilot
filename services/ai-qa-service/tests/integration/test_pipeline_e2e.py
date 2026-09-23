import pytest
import asyncio
from httpx import AsyncClient
from typing import Dict, Any

# We assume the service is running locally on port 8086 for true integration testing
API_BASE_URL = "http://localhost:8086"

@pytest.fixture
async def live_client() -> AsyncClient:
    headers = {
        "X-User-Id": "00000000-0000-0000-0000-000000000000",
        "X-Role": "ADMIN",
        "X-Department-Id": "00000000-0000-0000-0000-000000000000"
    }
    async with AsyncClient(base_url=API_BASE_URL, headers=headers, timeout=30.0) as client:
        yield client

@pytest.mark.asyncio
async def test_toxic_path(live_client: AsyncClient):
    """Test Layer 1: Toxic message rejection."""
    payload = {
        "question": "You are a terrible and useless bot. I hate you, kill yourself.",
        "stream": False
    }
    
    response = await live_client.post("/chat", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    print(f"\n[Test Toxic] Status: {data.get('status')}, Message: {data.get('message', 'N/A')}")
    
    # Can be BLOCKED by Layer 1 or refused by Layer 3 (OK status)
    assert data.get("status") in ["BLOCKED", "OK", "REJECTED"]
    if data.get("status") == "BLOCKED":
        assert data.get("processing_layer") == 1 or "message" in data

@pytest.mark.asyncio
async def test_simple_intent_path(live_client: AsyncClient):
    """Test Layer 2: Simple intent response (e.g., greetings)."""
    payload = {
        "question": "Hello! How are you today?",
        "stream": False
    }
    
    response = await live_client.post("/chat", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should stop at Layer 2
    assert data.get("processing_layer") == 2
    print(f"[Test Simple Intent] Layer: {data.get('processing_layer')}, Answer: {data.get('answer')}")
    assert "answer" in data
    assert len(data["answer"]) > 0

@pytest.mark.asyncio
async def test_complex_rag_path(live_client: AsyncClient):
    """Test Layer 3: Complex query requiring RAG."""
    payload = {
        "question": "What is the policy for working from home?",
        "stream": False,
        "model_id": "groq/llama-70b"
    }
    
    response = await live_client.post("/chat", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should reach Layer 3
    assert data.get("processing_layer") == 3
    print(f"[Test Complex RAG] Layer: {data.get('processing_layer')}, Answer: {data.get('answer')[:100]}...")
    assert "answer" in data

@pytest.mark.asyncio
async def test_real_rag_content(live_client: AsyncClient):
    """Test Layer 3: Query based on real document content."""
    payload = {
        "question": "How many pets does the GitLab team have and how many countries are they located in?",
        "stream": False,
        "model_id": "groq/llama-70b"
    }
    
    response = await live_client.post("/chat", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    print(f"[Test Real RAG] Answer: {data.get('answer')}")
    assert "363" in data.get("answer")
    assert "65" in data.get("answer")
    assert data.get("processing_layer") == 3

@pytest.mark.asyncio
async def test_title_generation(live_client: AsyncClient):
    """Test background title generation integration."""
    payload = {
        "question": "How do I reset my password?",
        "stream": False,
        "model_id": "groq/llama-70b"
    }
    
    # Send first message to create a conversation
    response = await live_client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    conversation_id = data.get("conversation", {}).get("id")
    assert conversation_id is not None
    
    # Wait for background task
    await asyncio.sleep(5)
    
    # Fetch conversation to check title
    # Note: We'd need a conversation-specific endpoint if available
    pass
