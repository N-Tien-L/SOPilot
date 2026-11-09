import json
from pathlib import Path

import numpy as np
import pytest
import sopilot_eval.run as runner
import yaml
from sopilot_eval.corpus import Chunk, split_text
from sopilot_eval.embedders import OpenAICompatibleEmbedder
from sopilot_eval.infra_check import disposable_config
from sopilot_eval.metrics import refusal_sweep, retrieval_metrics
from sopilot_eval.retrievers import retrieve
from sopilot_eval.run import run

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def test_ndcg_duplicate_chunks_do_not_inflate_score():
    # Arrange
    chunks = [Chunk("a", 1, "repeated")] * 10
    # Act
    result = retrieval_metrics(chunks, [{"doc": "a"}])
    # Assert
    assert result["ndcg@10"] == 1.0


def test_recall_chunk_covers_all_matching_targets():
    # Arrange
    targets = [{"doc": "a"}, {"doc": "a", "pages": [1]}]
    # Act
    result = retrieval_metrics([Chunk("a", 1, "text")], targets)
    # Assert
    assert result["recall@1"] == 1.0
    assert 0 <= result["ndcg@10"] <= 1


@pytest.mark.parametrize("size,overlap", [(0, 0), (10, 10), (10, -1)])
def test_chunk_invalid_windows_fail_instead_of_hanging(size, overlap):
    # Arrange / Act / Assert
    with pytest.raises(ValueError):
        split_text("long content" * 100, size, overlap)


def test_chunk_large_paragraph_respects_size():
    # Arrange / Act
    chunks = split_text("abcde" * 100, 40, 5)
    # Assert
    assert chunks and all(len(chunk) <= 40 for chunk in chunks)


def test_refusal_sweep_includes_refuse_all_for_tied_scores():
    # Arrange / Act
    rows = refusal_sweep([0.5], [0.5])
    # Assert
    assert rows[0]["false_answer"] == 1
    assert rows[-1]["threshold"] > 0.5
    assert rows[-1]["false_refusal"] == 1 and rows[-1]["false_answer"] == 0


def test_embedding_cache_identity_distinguishes_endpoints():
    # Arrange / Act
    left = OpenAICompatibleEmbedder("http://localhost:8001", "same-model")
    right = OpenAICompatibleEmbedder("http://localhost:8002", "same-model")
    # Assert
    assert left.name != right.name


def test_retrieval_invalid_mode_fails_before_using_index():
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="retriever"):
        retrieve(None, "query", {"retriever": "hybird"}, None)


def test_hybrid_sparse_only_winner_still_has_dense_gate():
    # Arrange
    class Index:
        def dense(self, _):
            return np.array([0.8, 0.1])

        def sparse(self, _):
            return np.array([0.0, 5.0])

    # Act
    ranked = retrieve(
        Index(), "query", {"retriever": "hybrid", "weights": [0, 1]}, None
    )
    # Assert
    assert ranked[0] == (1, pytest.approx(0.1))


def test_run_does_not_silently_fallback_from_docproc(tmp_path):
    # Arrange
    config = tmp_path / "docproc.yaml"
    config.write_text(
        "chunking: {mode: docproc}\nconfigs: [{name: dense, retriever: dense, embedder: {provider: hash}}]",
        encoding="utf-8",
    )
    # Act / Assert
    with pytest.raises(ValueError, match="no silent fallback"):
        run(ROOT / "datasets/smoke", config, tmp_path)


def test_reranker_shared_configs_load_model_once(tmp_path, monkeypatch):
    # Arrange
    loads = []

    class FakeReranker:
        def __init__(self, model, revision):
            loads.append((model, revision))

        def score(self, query, texts):
            return np.ones(len(texts))

    monkeypatch.setattr(runner, "CrossEncoder", FakeReranker)
    config = {
        "configs": [
            {
                "name": name,
                "retriever": "hybrid",
                "embedder": {"provider": "hash"},
                "rerank": {"model": "synthetic-reranker", "revision": "fixture"},
            }
            for name in ("rerank-one", "rerank-two")
        ]
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    # Act
    output = run(ROOT / "datasets/smoke", path, tmp_path)
    # Assert
    assert len(loads) == 1
    assert (
        json.loads((output / "run.json").read_text(encoding="utf-8"))["metric_scope"]
        == "document_page_proxy"
    )


def test_disposable_infrastructure_uses_tmpfs_for_image_volumes(tmp_path):
    # Arrange
    source = yaml.safe_load(
        (REPO / "docker-compose.v2.yml").read_text(encoding="utf-8")
    )
    # Act
    config = disposable_config(source, "sopilot-v2-fixture", tmp_path)
    # Assert
    assert "volumes" not in config
    assert config["services"]["minio-init"]["tmpfs"] == ["/data"]
    assert all(
        "ports" not in service and "container_name" not in service
        for service in config["services"].values()
    )


def test_modal_rerank_config_builds_remote_reranker(monkeypatch):
    # Arrange
    from sopilot_eval.retrievers import RemoteCrossEncoder, build_reranker

    monkeypatch.setenv("SOPILOT_RERANK_BASE_URL", "https://x.modal.run/v1")
    monkeypatch.delenv("SOPILOT_LLM_API_KEY", raising=False)
    # Act
    reranker = build_reranker({"provider": "modal", "model": "m", "revision": "r"})
    # Assert
    assert isinstance(reranker, RemoteCrossEncoder)
    assert reranker.score("q", []).shape == (0,)
