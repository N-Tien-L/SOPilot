# sopilot-eval

Retrieval-only evaluation harness (PRD-V2 FR-18, ADR-006 §4.2). No LLM and no running stack needed, so it can be rerun freely.

```powershell
cd eval
uv sync --extra dev                       # harness + tests
uv run pytest -q
uv run python -m sopilot_eval.run --dataset datasets/smoke --config configs/smoke.yaml   # offline smoke run

uv sync --extra local                     # + sentence-transformers (downloads bge-m3, ~2 GB)
uv run python -m sopilot_eval.run --dataset datasets/<your-set> --config configs/rq1-rq3-bge-m3.yaml
```

Output: `results/<run_id>/{run.json, metrics.json, per_question.jsonl, report.md}`. `run.json` records git commit, config, chunk/question counts and machine.

## Dataset format

```
datasets/<name>/corpus/*.md|txt|pdf     # form feed (\f) = page break in md/txt
datasets/<name>/questions.jsonl         # one JSON per line:
{"id": "q1", "question": "...", "lang": "vi", "cross_lingual": false, "answerable": true,
 "expected": [{"doc": "file.pdf", "pages": [3]}], "reference_answer": "..."}
```

`lang` is the question language; `cross_lingual` is true when the answer lives in a document of another language. `report.md` groups answerable-question metrics by `lang=<x>` and `cross_lingual` (a cross-lingual question is counted in both its language group and the cross-lingual group).

`pages` is optional (omit for document-level relevance). Unanswerable questions use `"answerable": false, "expected": []`.

## What it measures

| RQ | Config knob |
|---|---|
| RQ1 | `retriever: dense \| bm25 \| hybrid` |
| RQ2 | `rerank: {model: ...}` (latency p50/p95 included) |
| RQ3 | refusal sweep in `report.md`: false refusal vs false answer by top-1 score threshold. This is a retrieval-level proxy; answer-level refusal needs the LLM layer. |
| RQ5 | change `embedder.model` |

## Caveats

- `datasets/smoke` and the `hash` embedder only validate the harness. Never report their numbers.
- Pin `revision` (HF commit hash) in the config before reporting results.
- Hybrid gates the refusal threshold on dense cosine, because RRF scores are rank-based and not comparable across queries.
- RQ4 (tenant filter latency) needs Postgres + RLS and is not covered yet.
- LLM-drafted questions must be human-reviewed and the process stated in the report.
