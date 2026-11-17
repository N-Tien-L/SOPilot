"""Reference probabilities of the saved SetFit artifact (V2-44), written next to it.

The saved ``setfit-router-model-histaug`` does not equal the model that scored
``setfit-bge-m3-pool447-histaug-test`` (ADR-012 §5), so the served artifact is its own source of
truth. This script encodes the frozen test split in batches with plain sentence-transformers and
applies ``head.npz`` with numpy, a path that shares no code with the service module (which encodes
one question at a time); ``services/ai-service/tests/unit/test_setfit_router.py`` compares the two.
Reproduction only, never tuning. Run from ``eval/``::

    uv run --extra local python experiments/routing/artifact_reference.py [artifact_dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sopilot_eval.routing import EVAL_ROOT, load_dataset
from sopilot_eval.routing_remote import model_input

DEFAULT = EVAL_ROOT / "results/routing/setfit-router-model-histaug/setfit-router"


def main() -> None:
    from sentence_transformers import SentenceTransformer

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    body = SentenceTransformer(str(root / "body"), device="cpu")
    body.max_seq_length = 128
    head = np.load(root / "head.npz")
    rows = load_dataset(EVAL_ROOT / "datasets/routing/test.jsonl")
    emb = body.encode([model_input(r, True)[:2000] for r in rows], batch_size=16,
                      convert_to_numpy=True)
    z = emb @ head["coef"].T + head["intercept"]
    z -= z.max(axis=1, keepdims=True)
    p = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
    out = np.zeros((len(rows), 14))
    out[:, head["classes"]] = p
    lines = [json.dumps({"id": r["id"], "proba": [round(float(x), 6) for x in row]})
             for r, row in zip(rows, out, strict=True)]
    (root.parent / "artifact_reference.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.write(f"{len(rows)} rows written\n")


if __name__ == "__main__":
    main()
