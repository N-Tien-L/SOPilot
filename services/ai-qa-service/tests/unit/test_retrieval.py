import pytest
from uuid import uuid4
from src.services.retrieval.hybrid_search import HybridSearchService
from src.models.retrieval import RetrievalChunk


@pytest.fixture
def hybrid_search():
    return HybridSearchService()


def test_rrf_logic():
    """Test Reciprocal Rank Fusion logic in HybridSearchService."""
    service = HybridSearchService()
    
    # Mock some chunks
    chunk_a = RetrievalChunk(
        id=uuid4(),
        document_id=uuid4(),
        content="Chunk A content",
        similarity_score=0.9
    )
    chunk_b = RetrievalChunk(
        id=uuid4(),
        document_id=uuid4(),
        content="Chunk B content",
        similarity_score=0.8
    )
    
    # Simple fusion: result_a has [A, B], result_b has [B, A]
    results_a = [chunk_a, chunk_b]
    results_b = [chunk_b, chunk_a]
    
    fused = service._reciprocal_rank_fusion(results_a, results_b, k=60)
    
    # Both should have the same combined score
    assert len(fused) == 2
    assert fused[0].id in [chunk_a.id, chunk_b.id]
    
    # Test with different ranks
    # A is rank 1 in both
    # B is rank 2 in both
    results_a = [chunk_a, chunk_b]
    results_b = [chunk_a, chunk_b]
    fused = service._reciprocal_rank_fusion(results_a, results_b, k=60)
    assert fused[0].id == chunk_a.id
    assert fused[1].id == chunk_b.id
