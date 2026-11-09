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

## Answer level (V2-10)

`sopilot_eval/answers.py` measures what the QA pipeline does with the retrieved chunks. It imports the ai-service context assembly, prompt, citation and number-check code, so the harness and the service run the same functions (token counts are those of `index_text`, as the service stores them).

```powershell
# No LLM: how much gold evidence reaches the prompt, context.expand on vs off (bge-m3 from the HF cache)
uv run --extra local python -m sopilot_eval.answers coverage --dataset datasets/sop-main --config configs/rq1-rq3-bge-m3.yaml --name hybrid --split test

# Needs the answer endpoint (V2-34) and a judge: citation precision, refusal accuracy (gate vs the model's own refusal),
# faithfulness on a fixed subset (temperature 0), expand on/off. Endpoint, model id and key come from the environment (SOPILOT_LLM_*).
uv run --extra local python -m sopilot_eval.answers answers --dataset datasets/sop-main --config configs/rq1-rq3-bge-m3.yaml --name hybrid --split test --judge judge
```

Output: `results/answers-<command>-<config>-<split>/report.json` (+ `per_question.jsonl` for `answers`). `--judge generate` lets the answer model judge itself; `report.json` then says `judge_is_the_answer_model: true`. Not measured here: the access filter (one in-memory workspace), the output guard, and the `code`/`rev`/`effective` attributes of `<source>` (the frozen corpus keeps no extracted metadata).

## What it measures

| RQ | Config knob |
|---|---|
| RQ1 | `retriever: dense \| bm25 \| hybrid` |
| RQ2 | `rerank: {model: ...}` (latency p50/p95 included) |
| RQ3 | refusal sweep in `report.md`: false refusal vs false answer by top-1 score threshold. This is a retrieval-level proxy; answer-level refusal needs the LLM layer. |
| RQ5 | change `embedder.model` |
| RQ4 | `rq4_rls_latency.py`: latency of one retrieval transaction (ai-service's own dense + BM25) with the application filter only vs the filter plus RLS, same data and queries, interleaved; needs Docker, no model. `uv run python rq4_rls_latency.py --workspaces 5 --chunks 2000 --queries 300` |

## Caveats

- `datasets/smoke` and the `hash` embedder only validate the harness. Never report their numbers.
- Pin `revision` (HF commit hash) in the config before reporting results.
- Hybrid gates the refusal threshold on dense cosine, because RRF scores are rank-based and not comparable across queries.
- The BM25 tokenizer, BM25 and fusion (RRF, cross-lingual factor, `gate_score`) are imported from `sopilot_ai.retrieval` (V2-09), so harness and ai-service rank with the same code. `python -m sopilot_eval.service_parity --dataset datasets/sop-main --config configs/rq1-rq3-bge-m3.yaml --split all` (Docker, `--extra local`) compares top-10 of the service through Postgres with the harness (TECH-V2-ai-service §6.5, target mean Jaccard ≥ 0.95) and writes `results/service-parity/<timestamp>.json`.
- RQ4 (tenant filter latency) needs Postgres + RLS and is not covered yet.
- LLM-drafted questions must be human-reviewed and the process stated in the report.

## Readiness review 2026-10-24

Tiếp nối 2026-10-25: acquisition có khóa hash/kiểm PDF không OCR ở `sopilot_eval.acquire`; pilot truy xuất thật VI/EN ở [datasets/sop-pilot](datasets/sop-pilot/README.md), corpus PDF ở [../datasets/extraction/pilot](../datasets/extraction/pilot/README.md). Hai bộ có phiếu duyệt, vẫn draft; chưa có kết quả Docling/RQ. Scorer từ chối dùng nhãn từng trang như gold toàn tài liệu và không gộp ca từ chối vào điểm cấu trúc.

Character chunking (`chunking.size/overlap`) is exploratory only and its results are
labelled `document_page_proxy`. Official numbers use `chunking.mode: docproc` (below).
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

## V2-07: official runs on `sop-main` (docproc chunks, span gold)

`uv sync --extra local --extra dev` also installs `services/ai-service` (path dependency) so the
harness chunks with `sopilot_ai.docproc` exactly as ai-service does: target 384 / max 512 tokens of
the measured model's tokenizer, `index_text` (title `doc_id` + section path + content) embedded and
BM25-indexed. The dataset keeps only canonical Markdown, so chunks are rebuilt from the cached
extraction (`results/extraction-clean/structured`, from `predict_extraction.py --clean`) and the
two Markdown pilot pages; the rebuild must match the frozen corpus byte for byte or the run fails.

```powershell
$env:HF_HUB_OFFLINE = "1"
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq1-rq3-bge-m3.yaml --split dev --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main --config configs/rq1-rq3-bge-m3.yaml --split test --repeats 3
./.venv/Scripts/python.exe -m sopilot_eval.analyze_v2_07 --dev results/<dev> --test results/<test> --out results/<test>/analysis
./.venv/Scripts/python.exe -m sopilot_eval.smoke_models --dataset datasets/sop-main --kind embed --model BAAI/bge-m3 --revision <sha> --out results/smoke-models/bge-m3.json
```

- `--split` is required for V2-06 datasets; the dataset validator (frozen `test_sha256`, reviews)
  runs first. `--repeats N` repeats the query pass for latency and checks ranks are identical.
- Metrics: `span_recall@k` (share of the required spans of the best OR alternative covered by the
  top k, a span counts when >= 50% of its characters are covered), `full@k` (all of them),
  `any@k`, `mrr_span`; `hit@k`/`recall@k` remain the document/page proxy.
- BM25 tokenizer is the final one of TECH-V2-ai-service §6.3 (`~` diacritic-free terms). The gate
  is `dense_score` for dense/hybrid (every candidate has it), `rerank_score` (sigmoid) with rerank,
  none for bm25. `cross_lingual_bm25_factor` scales the BM25 branch for chunks of another language.
- `configs/rq2-rerank-bge-m3.yaml` is separate because the cross-encoder needs ~16 s/question on CPU.

### `sop-main-v2` (harder extension, frozen 2026-11-05)

`sop-main` was too easy to separate configs: 57–65 of 70 test questions score 1.0 everywhere, 36 of 81
name the document code, there are only 5 cross-lingual questions and 4 dev negatives.
`datasets/sop-main-v2` keeps the frozen `sop-main` questions as `subset=v1` (byte-identical, same
reviews) and adds 96 drafted intents from `datasets/sop-main-v2/seed/*.json` as `subset=v2`. They
contain no document codes, are paraphrased, each intent has a same-lingual and a cross-lingual
phrasing, and there are near-miss negatives. Test grows to 200 answerable (70 cross-lingual) plus
39 negatives; dev to 40 plus 14. Protocol and counts: `datasets/sop-main-v2/README.md`.

```powershell
./.venv/Scripts/python.exe -m sopilot_eval.extend_dataset --base datasets/sop-main --dataset datasets/sop-main-v2
./.venv/Scripts/python.exe -m sopilot_eval.run --dataset datasets/sop-main-v2 --config configs/rq1-rq3-bge-m3.yaml --split test --allow-draft
```

- Frozen 2026-11-05 (`test_sha256 a568bf74…`). New questions were drafted by Claude, checked against the corpus by a
  Claude subagent (`REVIEW-claude.md`) and approved by the owner on that review (`review_basis=claude_review`).
  `--allow-draft` remains for future draft extensions; such runs record `dataset_info.reviewed=false`.
- Per-question rows carry `intent_id`, `subset` and `tags`. `analyze_v2_07` groups by them and
  bootstraps by `intent_id` cluster, because the two phrasings of one intent are not independent. It
  also reports the paired difference against `hybrid` with the number of questions won and lost.
