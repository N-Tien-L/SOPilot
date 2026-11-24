from pathlib import Path

from sopilot_eval.corpus import Chunk
from sopilot_eval.metrics import refusal_sweep, retrieval_metrics
from sopilot_eval.retrievers import rrf
from sopilot_eval.run import run

ROOT = Path(__file__).resolve().parents[1]


def test_metrics_first_hit_rank_2():
    chunks = [Chunk("b", 1, "x"), Chunk("a", 1, "y")]
    m = retrieval_metrics(chunks, [{"doc": "a"}], ks=(1, 3))
    assert m["recall@1"] == 0.0 and m["recall@3"] == 1.0 and m["mrr"] == 0.5


def test_page_constraint():
    m = retrieval_metrics([Chunk("a", 2, "x")], [{"doc": "a", "pages": [1]}], ks=(1,))
    assert m["recall@1"] == 0.0


def test_rrf_prefers_consensus():
    fused = rrf([[1, 2, 3], [2, 1, 3]], [1.0, 1.0])
    assert fused[1] == fused[2] > fused[3]


def test_refusal_sweep_extremes():
    rows = refusal_sweep([0.9, 0.8], [0.1, 0.2])
    assert rows[0]["false_refusal"] == 0.0 and rows[-1]["false_answer"] == 0.0


def test_smoke_run_end_to_end(tmp_path):
    out = run(ROOT / "datasets/smoke", ROOT / "configs/smoke.yaml", tmp_path)
    assert (out / "metrics.json").exists() and (out / "run.json").exists()
    assert "bm25" in (out / "report.md").read_text(encoding="utf-8")
