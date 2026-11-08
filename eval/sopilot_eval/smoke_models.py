"""V2-07 feasibility smoke: load time, embed/rerank time and peak RAM of one model on ~50 docproc chunks.

Run one model per process so peak RAM belongs to that model alone::

    python -m sopilot_eval.smoke_models --dataset datasets/sop-main --kind embed \\
        --model BAAI/bge-m3 --revision <sha> --out results/smoke-models/bge-m3.json

``--kind rerank`` scores ``--n`` (query, chunk) pairs with a cross-encoder, using the bge-m3
tokenizer for chunking. Every timed step runs ``--repeats`` times (first one includes warm-up).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

from .docproc_chunks import load_docproc_chunks
from .run import ROOT, _peak_rss_mb

BGE_M3 = ("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181")


def _sample(items: list, n: int) -> list:
    step = max(1, len(items) // n)
    return items[::step][:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--kind", choices=["embed", "rerank"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--tokenizer-model", help="chunking tokenizer for rerank (default bge-m3)")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--structured", type=Path, default=ROOT / "results/extraction-clean/structured")
    ap.add_argument("--pilot", type=Path, default=ROOT / "datasets/sop-pilot")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    rss_start = _peak_rss_mb()
    t0 = time.perf_counter()
    if a.kind == "embed":
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(a.model, revision=a.revision)
        model.max_seq_length = min(model.max_seq_length or 512, 512)
        tok = (a.model, a.revision)
    else:
        from .retrievers import CrossEncoder

        model = CrossEncoder(a.model, a.revision)
        tok = BGE_M3
    load_s = time.perf_counter() - t0
    rss_loaded = _peak_rss_mb()

    chunks, info = load_docproc_chunks(a.dataset, *tok, a.structured, a.pilot)
    sample = _sample(chunks, a.n)
    texts = [c.index_text for c in sample]
    times = []
    for _ in range(a.repeats):
        t = time.perf_counter()
        if a.kind == "embed":
            model.encode(texts, batch_size=a.batch_size, normalize_embeddings=True, show_progress_bar=False)
        else:
            # two questions x n/2 candidates, the shape of rerank_pool = 25 per question
            half = len(texts) // 2
            model.score("Ai phê duyệt kế hoạch đánh giá nội bộ?", texts[:half])
            model.score("Who approves a deviation report?", texts[half:])
        times.append(time.perf_counter() - t)
    tok_counts = [c.index_text for c in sample]
    result = {
        "kind": a.kind,
        "model": a.model,
        "revision": a.revision,
        "n_items": len(texts),
        "corpus_chunks_with_this_tokenizer": len(chunks),
        "chunking": {k: v for k, v in info.items() if k != "sources"},
        "load_s": round(load_s, 2),
        "batch_s": [round(x, 2) for x in times],
        "per_item_ms_warm_mean": round(float(np.mean(times[1:] or times)) / len(texts) * 1000, 1),
        "per_item_ms_warm_sd": round(float(np.std(times[1:] or times)) / len(texts) * 1000, 1),
        "mean_chars": round(float(np.mean([len(t) for t in tok_counts])), 1),
        "peak_rss_mb_start": rss_start,
        "peak_rss_mb_after_load": rss_loaded,
        "peak_rss_mb_end": _peak_rss_mb(),
        "torch_threads": __import__("torch").get_num_threads(),
        "cpu_count": os.cpu_count(),
        "machine": platform.platform(),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
