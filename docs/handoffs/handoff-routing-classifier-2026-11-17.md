---
title: "Handoff: query routing classifier experiments (eval)"
status: draft
created: 2026-11-17
updated: 2026-11-17
author: "Owner"
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-27-semantic-router.md
  - docs/research/research-decision-layer-context-2026-11-16.md
---

# Handoff: query routing classifier experiments

Written so that a new session can continue without the old conversation. Not acceptance evidence (use a test report).

## Goal and done condition

Replace the patchwork of routing rules + semantic router (ai-service `qa/router.py`, TECH-V2-ai-service §7) with a trained intent classifier that routes more non-SOP questions correctly with **zero costly errors** (no `sop_question` / `followup` routed away from retrieval).

Done for this phase when the final SetFit model is trained on `train-pool.jsonl`, its test metrics for the `flat` and `two_group` designs are reported next to the 187-row pool run, the model files are downloaded locally, CPU latency is measured on the owner's machine, and an ADR plus ticket for the integration are drafted for owner review.

## Update (same day, later session)

The Kaggle run died (the session was stopped, nothing saved), so the pool-447 model was trained again on **Modal** instead: `uv run --with modal python -m sopilot_eval.routing_setfit_remote --modal --with-history --save` (worker `eval/experiments/routing/modal_setfit_app.py`, 5 folds and the final model in parallel on A100-40GB, about 6 minutes). Model on the Modal volume `sopilot-setfit` (`setfit-router/`), downloaded to `eval/results/routing/setfit-router-model/` (git-ignored). Results, the ADR and the ticket are in [ADR-012](../architecture/decisions/adr-012-setfit-routing-classifier.md) (draft) and [V2-44](../execution/initiatives/v2-sopilot-mvp/tickets/V2-44-ai-service-setfit-router.md) (todo). Summary: `two_group+` (also deferring `abuse_with_question` and `about_source`) routes 86 of 101 correctly with 0 costly errors on the frozen test split; a confidence threshold and temperature scaling do not help (`sopilot_eval/routing_setfit_calibrate.py`); the downloaded model reproduces the job's probabilities and runs at about 100 ms p50 on CPU with about 2.9 GB of memory (`experiments/routing/local_setfit_check.py`). **Later the same day:** a probe showed the first model reads any previous message as a follow-up (213 of 213 test rows flipped); it was retrained with `--augment-history` (`setfit-bge-m3-pool447-histaug-test`; the Modal volume `sopilot-setfit` now holds this version, local copy in `eval/results/routing/setfit-router-model-histaug/`; the older `setfit-router-model/` is the shortcut model and can be deleted). See ADR-012 §5. Steps 1 to 3 below are done; steps 4 and 5 remain, and the Kaggle "running" paragraph above is history.

## State now

- Branch `feat/eval-routing-classifier`, created from `develop` at `1ad6d74` (V2-17 merged). **Nothing from this work is committed.** The three tracked edits (`CLAUDE.md` learned rule, `.claude/skills/{project-docs,excalidraw-visualize}/SKILL.md`) are the 2026-11-17 owner diagram-size rule from the same session; they can be committed separately from the eval work.
- **Running when this was written:** the owner is training SetFit on Kaggle (pool 447 + 60 router exemplars, `--with-history --save`, default 20 iterations, both T4 GPUs; about 1.5–2.5 h; GPU memory was 14/15 GB, so rerun with `--batch-size 8` if it fails with OutOfMemoryError). Its output lands in `eval/results/routing/setfit-bge-m3-pool447-hist-test/` (`metrics.json`, `per_question.jsonl`). The model is saved on Kaggle in `/kaggle/working/setfit-router/` (`body/` sentence-transformers folder, `head.npz` with `coef`, `intercept`, `classes`, `labels.json`) and must be downloaded from the Output panel before the session stops.
- Training config: SetFit defaults (20 iterations, 1 epoch), batch 16, max_seq_length 128, AMP; the trainer uses both T4 GPUs. Compare training configs only on `dev_oof`, never on test.

### Results so far (frozen `test.jsonl`, 233 rows, 169 non-RAG; thresholds picked on dev unless noted)

| Candidate | Training rows | Routed OK /169 | Costly | 14-class acc | Latency |
|---|---|---|---|---|---|
| Rules + semantic router (current service) | – | 44 | 0 | – | ~120 ms CPU |
| GLiNER2.5-multi-Decide, tuned `two_task` | none (zero-shot) | 60 | 2 | 0.49 | 37 ms T4 |
| LR on bge-m3 vectors + history | dev+dev-extra (187) + exemplars | 121 | 1 | 0.86 | ~0 if the retrieval vector is reused |
| Same LR, pool 447 | 447 + exemplars | 111 @ 0.6 | 2 | 0.87 | same |
| **SetFit bge-m3 + history** | 187 + exemplars | **150** | 3 | **0.90** | 23 ms T4 |
| LiquidAI d1-2B zero-shot | none | 120 | 8 | 0.72 | 200 ms T4 fp32 |
| d1-2B tuned `two_task` | none | 122 | 6 | 0.74 | 329 ms T4 |
| d1-2B + stacked LR on its probabilities | dev 157 | 116 | **0** | 0.75 | 200 ms T4 |

`two_group` design (corpus-dependent labels left to retrieval), SetFit 187-row run re-scored offline: **110/126 routed OK, costly 0**; d1 + stacked LR: 84/126, costly 0. The 3 SetFit costly errors were unaccented HR questions predicted as `legal_medical` / `personal_data`.

Caveats: `test.jsonl` SOP rows are mostly HR-style, while the new candidate SOP rows follow the real corpus (lab SOP, ISO, Kubernetes, GitLab, state documents), so pool-447 scores are not comparable one-to-one with pool-187 scores. Rows 036, 076/082, 193/196/201 of the candidates are still unchecked. d1 float16 was not measured (OOM came from `compile()`; the notebook now has compile off).

## Owner decisions already made

- 2026-11-17: skip LLM classifiers (Qwen) for routing: too slow.
- 2026-11-17: the 260 accepted rows of `candidates-2026-11-17.jsonl` are merged into `train-pool.jsonl` (447 rows); `test.jsonl` stays frozen and is never used for training or tuning.
- 2026-11-17: **SetFit bge-m3 is the chosen classifier**; no further candidates (JEV not tested).
- 2026-11-17: train on Kaggle, **serve locally** (CPU, like bge-m3 for retrieval). Kaggle is only for experiments.
- Open, proposed by the agent: the `two_group` design (route corpus-independent labels before retrieval; `off_topic`, `legal_medical`, `personal_data` decided after retrieval). The owner agreed that SOP/off-topic depend on the corpus but has not approved the design.
- Open: a second, corpus-specific test set (owner: depends on the user's corpus).

## Read first

1. This file.
2. `docs/research/research-decision-layer-context-2026-11-16.md` (architecture evaluation, recommended flow §7).
3. `eval/datasets/routing/README.md` (splits, train-pool, candidate rows).
4. `eval/sopilot_eval/routing_setfit_remote.py` (client: CV threshold per design, `--save`).
5. `eval/kaggle/setfit_server.ipynb` (server: `/train`, `/job/{id}`, `/predict`, `/save`).
6. `eval/sopilot_eval/routing.py` (labels, `EXPECTED`, costly definition) and `services/ai-service/src/sopilot_ai/qa/router.py`.

Other experiment files: `eval/sopilot_eval/routing_remote.py` + `routing_remote_tune.py` (GLiNER/d1 client and tuner), `eval/kaggle/{gliner2_decide_server,d1_decide_server}.ipynb`, `eval/experiments/routing/` (bge-m3 LR, d1 stacking, notebook generators). Results: `eval/results/routing/` (gitignored).

## Next steps

1. Read `eval/results/routing/setfit-bge-m3-pool447-hist-test/metrics.json`: report `designs.flat` and `designs.two_group` (min_conf, dev_oof, test) against the 187-row run (`setfit-bge-m3-hist-test`), with row counts per source (`pool_sources`). If the owner wants a clean before/after, rerun with `--no-candidates --iterations 10`.
2. Check the downloaded model locally: load `body/` with `sentence-transformers` (eval extra `local`), apply `head.npz` with numpy (`softmax(emb @ coef.T + intercept)`), confirm it reproduces the server probabilities on a few test rows, and measure CPU latency p50/p95 and RAM. Keep the model files out of git (2.2 GB).
3. Draft an ADR (new routing classifier, model artifact storage, `config/models.yaml` entry) and a ticket for ai-service integration (replace or wrap `SemanticLayer`, keep the rules for harmful/PII, the `two_group` design if approved). Owner review before any code.
4. Ask the owner whether to commit the eval files (clients, notebooks, `experiments/routing/`, dataset README change, `train-pool.jsonl` and `dev-extra.jsonl` need `git add -f` because `datasets/` is gitignored).
5. Close the Kaggle sessions: tokens were pasted in chat.

## Verify with

```powershell
cd eval
uv run pytest -q tests/test_routing_eval.py                       # 18 passed (dataset hygiene)
uv run ruff check sopilot_eval/routing_remote.py sopilot_eval/routing_remote_tune.py sopilot_eval/routing_setfit_remote.py experiments/routing
cd ..; ./scripts/docs/check-docs.ps1                               # docs check passed
```
