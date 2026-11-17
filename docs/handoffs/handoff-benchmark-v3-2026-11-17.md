---
title: "Handoff: full-system benchmark on sop-main-v3 and the routing contribution (eval)"
status: draft
created: 2026-11-17
updated: 2026-11-17
author: "Owner"
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-45-eval-corpus-expansion-sop-main-v3.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-18-research-report-and-handover.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-27-semantic-router.md
  - docs/handoffs/handoff-routing-classifier-2026-11-17.md
  - docs/research/research-decision-layer-context-2026-11-16.md
---

# Handoff: full-system benchmark on sop-main-v3

Written so a new session can run the benchmarks and draft the report without the old conversation. Not acceptance evidence (use a test report).

## State

- `develop` holds the V2-45 tooling (merge `87464cd`). V2-45 is `review`, not `done`. Nothing is pushed.
- The dataset `eval/datasets/sop-main-v3` is **gitignored and local only**. Copy the folder if you work on another machine. It is frozen (`test_sha256` in its `manifest.json`); `sop-main` and `sop-main-v2` are unchanged.
- **No human has read the 290 new rows** (generator Sonnet 5.5, verifier Opus 5.5, same family). Read `eval/datasets/sop-main-v3/README.md` first. Do the 30-row check in `owner-spotcheck.md` before publishing numbers; if more than 3 of 30 are wrong, re-review.
- Known gaps against the V2-45 quotas: single-passage 76/80, negatives 28/30, no OR-alternative intents, no no-diacritics probes.
- Preview already run (retrieval only, test split): `eval/results/v3-preview/20261117-221436-08f3dd70`; per-stratum table in the dataset's `preview-strata.md`.

## Rules for every number

1. Use v3 for all tiers so tiers are comparable. Do **not** compare with V2-07 numbers (60 more distractor documents).
2. Report with and without translated documents (tag `translated_corpus`), and cross-lingual versus same-lingual. Hybrid on cross-lingual rows is weak in the preview; that is a finding.
3. Do not drop questions because they are easy or hard. Report the share every configuration answers perfectly per stratum.
4. Say who reviewed what (no human on new rows) in the report's limits section.

## Tier 1: retrieval (RQ1, RQ2, RQ5)

```
cd eval
uv run --extra local python -m sopilot_eval.run --dataset datasets/sop-main-v3 --config configs/rq1-rq3-bge-m3.yaml --split test --repeats 3 --out results/v3-rq1
```

Add `--split dev` only to choose parameters. Rerank configs (`configs/rq2-rerank-modal.yaml`) and the embedding bake-off (`configs/rq5-models.yaml`) need the Modal services; check each config's header for its extra requirements. Output per run: `report.md`, `metrics.json`, `per_question.jsonl`.

## Tier 2: answers and refusals (RQ2 faithfulness, RQ3)

Warm the Modal endpoint first (a cold start takes minutes; the client times out after 120 s). Put `SOPILOT_RERANK_BASE_URL` and `SOPILOT_LLM_API_KEY` in your shell environment; do not paste them anywhere.

```
cd eval
uv run --extra local python -m sopilot_eval.answers answers --dataset datasets/sop-main-v3 --config configs/answers-matrix.yaml --name hybrid-rerank --split test --judge judge --concurrency 8
```

Repeat for `dense`, `hybrid`, `dense-rerank`. Take quality from the concurrent run and latency only from `--concurrency 1`. Details and caveats: `eval/README.md` (answers section). Output: `results/answers-answers-<config>-test/report.json`.

## Tier 3: tenant filter latency (RQ4)

`eval/rq4_rls_latency.py` needs the local Postgres stack (`docker compose up -d postgres flyway-core flyway-rag minio minio-init`). Never run `down -v`. This tier does not use v3 questions.

## Tier 4: routing (supplementary contribution, not in RQ1-RQ5)

What exists: the rules + semantic router, and the SetFit/LR classifier experiments, are measured on their own 390-question set (`eval/datasets/routing/`, gitignored), not on v3. Frozen test split 233 rows (169 non-RAG), from the routing handoff:

| Candidate | Routed OK /169 | Costly errors | Latency |
|---|---|---|---|
| Rules + semantic router (current service) | 44 | 0 | ~120 ms CPU |
| LR on bge-m3 vectors + history | 121 | 1 | ~0 if the retrieval vector is reused |
| SetFit bge-m3 + history | 150 | 3 | 23 ms T4 |

Open items before it can be reported:
- The owner has reviewed the 390-question routing set (stated 2026-11-17; the V2-27 ticket text still says "owner review open", so update it when you record evidence).
- All routing code and configs (`eval/sopilot_eval/routing*.py`, `eval/configs/routing-*.yaml`) are already tracked on `develop`. The routing datasets (`eval/datasets/routing/`) and model outputs are gitignored and stay in this working copy. The SetFit pool-447 retrain on Modal is in `docs/handoffs/handoff-routing-classifier-2026-11-17.md`; branch `feat/eval-routing-classifier` has no commits beyond `develop`.
- Not measured: router on/off effect on answer quality and refusal on v3 (run Tier 2 twice, router off and on, if the report needs it).

**Framing decision (owner):** the PRD defines RQ1-RQ5 only; routing is in none of them. Either add a secondary RQ (for example "RQ6: can a trained intent classifier replace the rules + semantic router with no costly errors, and at what latency?") or list it as an additional contribution in V2-18. Tie it to RQ3: the router decides which questions skip retrieval, so it changes wrong refusals. Until decided, describe it only as supplementary work.

## Report outline (V2-18)

1. Dataset: v3 construction, quotas against actuals, review basis and limits.
2. RQ1/RQ5 retrieval by language group and translated/native; RQ2 rerank gain and latency; RQ3 gate trade-off; RQ4 tenant filter.
3. Routing as supplementary contribution (if the owner agrees).
4. Threats: same-family generator and verifier, machine-translated pages, local single-machine runs, gaps listed above.

## Do not

Edit `sop-main`, `sop-main-v2` or the frozen v3 test split; read `.env` files; compare v3 numbers with V2-07; mark V2-45 or V2-18 `done` without owner acceptance.
