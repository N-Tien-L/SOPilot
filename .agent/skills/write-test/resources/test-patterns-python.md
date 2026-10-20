# Python / FastAPI Test Patterns

## 1. Unit Test (pytest)
Use `pytest` and `unittest.mock` for isolating pure functions and logic.

```python
import pytest
from unittest.mock import Mock, patch
from ingestion_service.services.deduplication import DeduplicationService

def test_deduplicate_ShouldReturnTrue_WhenDocumentExists():
    # Arrange
    mock_db = Mock()
    mock_db.document_exists.return_value = True
    service = DeduplicationService(db=mock_db)

    # Act
    result = service.is_duplicate("doc_hash_123")

    # Assert
    assert result is True
    mock_db.document_exists.assert_called_once_with("doc_hash_123")
```

## 2. FastAPI Endpoint Test (httpx.AsyncClient)
Use `pytest-asyncio` and `httpx` to test endpoints.

```python
import pytest
from httpx import AsyncClient
from ai_qa_service.main import app

@pytest.mark.asyncio
async def test_health_ShouldReturn200_WhenServiceIsUp():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
```

## 3. Parametrized Tests for Edge Cases
```python
import pytest
from ingestion_service.utils.validation import is_valid_document

@pytest.mark.parametrize("content, expected", [
    ("Valid text content", True),
    ("", False),
    (None, False),
    ("a" * 100000, False) # too large
])
def test_is_valid_document(content, expected):
    assert is_valid_document(content) == expected
```

## 4. Fixtures (conftest.py)
```python
import pytest
from httpx import AsyncClient
from ai_qa_service.main import app

@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```
