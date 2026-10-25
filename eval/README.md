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

## Readiness review 2026-10-24

Tiếp nối 2026-10-25: acquisition có khóa hash/kiểm PDF không OCR ở `sopilot_eval.acquire`; pilot truy xuất thật VI/EN ở [datasets/sop-pilot](datasets/sop-pilot/README.md), corpus PDF ở [../datasets/extraction/pilot](../datasets/extraction/pilot/README.md). Hai bộ có phiếu duyệt, vẫn draft; chưa có kết quả Docling/RQ. Scorer từ chối dùng nhãn từng trang như gold toàn tài liệu và không gộp ca từ chối vào điểm cấu trúc.

The current `run` CLI labels results `document_page_proxy` and character chunking
as exploratory. `chunking.mode: docproc` fails until V2-22/V2-07 implements the
shared adapter; never silently use the old splitter for official RQ numbers.
Repeated chunks from the same target earn nDCG relevance once. Threshold sweeps
include a refuse-all endpoint even when scores tie.

Cache identity includes model revision and endpoint for OpenAI-compatible
providers. Use `api_key_env: YOUR_CREDENTIAL_ENV_NAME`, never inline `api_key`,
because nonsecret configuration is persisted in `run.json`. Local transformer
inputs remain capped at 512 tokens; truncation mapping is V2-07/V2-22 work.

Contracts and draft examples: [retrieval labels](datasets/README.md),
[extraction labels](../datasets/extraction/README.md). Validators do not certify
human correctness or make the current scorer span-aware.

Commands from `eval/` with dependencies already installed:

```powershell
./.venv/Scripts/python.exe -m pytest -q --basetemp .cache/pytest-readiness-local
./.venv/Scripts/python.exe -m sopilot_eval.plan_check
./.venv/Scripts/python.exe -m sopilot_eval.infra_check
```

Use a fresh `--basetemp` path each time: pytest clears that exact directory.
`infra_check` uses V2 source images/scripts/migrations with random credentials,
a unique project, tmpfs and no host ports. It does not read `.env` or mount existing
volumes. Only its own project is stopped without `-v`; owner's persistent V2 DB
and V1 services are outside this check.
