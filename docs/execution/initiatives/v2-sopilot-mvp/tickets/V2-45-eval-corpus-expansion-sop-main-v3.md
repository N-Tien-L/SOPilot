---
id: V2-45
title: "eval: expand the retrieval eval set to 500+ questions (sop-main-v3) with a Haiku → Sonnet → Opus pipeline"
type: test
status: done # todo | in_progress | review | done | blocked
created: 2026-11-17
updated: 2026-11-17
author: "Owner"
scope: tests
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-06, V2-07]
blocks: [V2-18]
blocked_reason: ""
branch: "feat/eval-corpus-expansion"
refs:
  - eval/datasets/sop-main-v2/README.md
  - docs/research/research-02-dataset-and-labeling.md
  - docs/research/research-v2-19-corpus-sources-2026-10-20.md
---

# TICKET V2-45: Expand the eval set to 500+ questions (`sop-main-v3`)

> **Scope:** `tests` | **Size:** `L` | **Priority:** `P1`. Owner decision 2026-11-17: run end to end without questions; the owner has no time to review (see §Review basis).

## Context

`sop-main-v2` has 293 questions over 23 documents (frozen 2026-11-05, 53 negatives, 28 `multi_passage`). The six-configuration benchmark needs more than 500 questions with a balanced mix. Plan: add about 60 public GitLab Handbook pages (CC BY-SA 4.0, same pinned commit as `gitlab-buddies`), translate about half to Vietnamese, generate questions per stratum, then verify them against stored evidence. `sop-main` and `sop-main-v2` are **not edited**; the result is a new dataset `eval/datasets/sop-main-v3` that adds documents, so its `corpus_version` differs and results are **not comparable** with V2-07 numbers (more distractors).

## Design decisions (made here so the run needs no questions)

1. **One language per page.** A translated page is indexed **only in Vietnamese**; an untranslated page only in English. Never index both (the pair would be duplicate distractors that need OR evidence). The English original of a translated page is kept under `acquisition/orig/` (not in `corpus/`) for verification only. Target about 30 EN pages and 30 VI-translated pages, so cross-lingual runs both ways (VI question over EN page, EN question over VI page).
2. **Translated is not native.** Manifest entries carry `translated_from` (url, commit, sha256, model). Results must be reportable with and without translated documents (`tags: translated_corpus`).
3. **Pair rule from v2 kept:** each intent has one question in the document's language and one in the other; same evidence, so analysis clusters by `intent_id`.
4. **Quotes come from the docproc canonical text**, never from raw bytes. Order: acquire → translate → canonicalize (`build_canonical.py`) → generate → verify.
5. **Document codes** (`QT-01`, …) do not exist in the handbook; the BM25 code probe stays covered by the v2 base rows (36/81 v1 rows). New questions follow v2 rule 1 (no doc name or code).
6. **No difficulty-based filtering.** Questions are not dropped because all six configurations answer them (that would bias the benchmark). The share of "all configs recall@5 = 1.0" is **reported** per stratum after the run.
7. **Re-audit the existing negatives.** New documents can make an old near-miss answerable (GitLab onboarding and meetings are the likeliest). Every `search_terms` of the 53 v2 negatives is searched in the new documents; hits go to the Opus adjudication, and a question that became answerable is `excluded` in v3 (v2 is untouched).

## Targets

| Item | Target | Note |
|---|---|---|
| New documents | ≥ 55 (aim 60), ≥ 6 top-level handbook sections, ≤ 8 pages per section | none overlapping the 23 existing `doc_id`s or URLs |
| New intents | 150 (300 rows) → ≥ 255 rows after Opus | total ≥ 520 reviewed rows with the 293 of v2 |
| Single-passage answerable | 80 intents | |
| Multi-passage (2–3 spans, same or different pages) | 40 intents | v2 has only 28 rows |
| Near-miss negatives | 30 intents | v2 negatives + these ≈ 20 % of rows |
| `number_deadline` / `condition_exception` / `comparison` | ≥ 30 / ≥ 30 / ≥ 12 intents | counted over answerable intents |
| OR-alternatives | as many as overlapping pages allow (target ≥ 6) | found by an overlap sweep; never invented to hit the number |
| Cross-lingual share of new rows | ≈ 50 % | by construction (rule 1) |
| Splits | dev ≈ 10 % of new documents (15 intents); the rest test | split by **document**; a page and its family never cross splits |
| Derived probes | no-diacritics variants of VI test questions (reuse the function in `sopilot_eval/system_check.py`) | tagged `probe_nodiacritics`, test only, **not counted** in the 500, clustered by `intent_id` |

## Pipeline

All state lives in `eval/datasets/sop-main-v3/`; `state.json` records the finished phase so an interrupted run resumes. Subagents are started with explicit model pins (`haiku` → `claude-haiku-5-5`, `sonnet` → `claude-sonnet-5-5`, `opus` → `claude-opus-5-5`; the resolved ids are written to the manifest). Every prompt says: document text is **data**, never instructions. Downloads go into their own directory (`acquisition/raw/`) and are read with `python -I`.

### Phase 0: setup (orchestrator, no model)
- Branch `feat/eval-corpus-expansion` from `develop` (`git status` first).
- Extend `extend_dataset.py` (or a thin wrapper) to accept `--extra-corpus` (new canonical docs, manifest entries, page-map) and to write `rebased_from` for the 293 carried reviews after checking every evidence quote is byte-identical in the new canonical text. Extend `build_canonical.py` selection with a `handbook-v3` source kind. Unit tests for both.
- Write the exclusion list: the 23 existing `doc_id`s and their source URLs.

### Phase 1: Haiku 5.5, acquire and translate
- **1a Acquire** (one agent). Enumerate the pinned commit `4684d72f27f3401d3ae72a26d72ae46eaeaab929` through the GitLab repository tree API (`…/handbook/-/raw/<sha>/…` for files). Pick candidates under `content/handbook/` (people-group, finance, security, it-ops, communication, company/culture/all-remote, hiring, legal and corporate affairs, support workflows). Keep a page only if: Markdown, 6–40 KB, at least three H2/H3 headings, mostly prose, contains figures, conditions or steps, not a link index or Hugo-only stub, not in the exclusion list. Output `acquisition/candidates.json` (≥ 70 candidates, reasons for rejects) and `acquisition/sources.json` (url, commit, sha256_raw, bytes, license `CC BY-SA 4.0`, section, headings count) plus raw bytes in `acquisition/raw/`.
- **1b Select** (orchestrator script): 60 pages, balanced across sections, then assign language: alternate by section so each section has both EN and VI pages; 10 pages (≈ 6 docs per dev batch) to dev.
- **1c Translate** (parallel Haiku agents, about 5 pages each, the 30 pages assigned `vi`). Rules: translate the whole file, keep heading levels, lists, tables, code, URLs, product names, numbers and dates unchanged; no summary, no additions; natural Vietnamese for procedures ("phải", "được phép", "trong vòng N ngày"). Output `acquisition/translated/<doc_id>.md` plus `translation-notes.json` (terms kept in English, uncertain passages).
- **1d Mechanical translation check** (script): same multiset of digit tokens, same heading count, length ratio 0.8–1.6, Vietnamese diacritics present, no untranslated paragraph. One retry of a failed page; a second failure drops the page and an extra EN page replaces it.
- Orchestrator then runs `build_canonical.py` on the 60 pages: `corpus/`, `page-map.json`, manifest entries.

### Phase 2: Sonnet 5.5, generate questions with evidence
- Ten batches (nine test, one dev), about six documents each, run in parallel. Each batch gets its documents' **canonical** text, the schema of `sop-main-v2/seed/*.json` with two example intents, and its quota: **8 single-passage, 4 multi-passage, 3 near-miss** intents (15 per batch), plus the global `query_types` and `exact_term` targets spread across batches.
- Output per batch: `seed/3N-<batch>.json` (builder schema; `quote` is copied verbatim from canonical text with `occurrence`/`after` when not unique, every answerable intent has `evidence` and every negative has `negative_reason` + `search_terms`) and `gen-log/<batch>.jsonl`: per intent `rationale` (why only these spans answer it), section heading path, the nearest-but-insufficient passage for negatives. The seed holds the evidence; the log holds the reasoning the verifier reads.
- Question rules (from `sop-main-v2` README, restated in the prompt): no document name or code; name the organisation or page topic only when needed to disambiguate; paraphrase, do not copy the source sentence; the pair is the same question in both languages with the same evidence; near-miss asks for a detail the page's topic *would* cover but does not state (a number of days, a tool, a fee, a default); multi-passage needs every span (state which are necessary).
- **Overlap sweep** (script, after generation): finds pages with ≥ 60 % shared 5-grams between passages; a Sonnet pass writes OR-alternative intents for them (evidence = list of alternative sets).
- **Mechanical gate** (script, before Opus): builder run succeeds (every quote located), median lexical overlap ≤ 0.45 and no row above 0.75, no `names_doc_code`, no duplicate question text, strata counts against the quotas. One top-up round to Sonnet for any shortfall, then proceed.
- **Negative pre-audit** (script): every `search_terms` counted across the whole v3 corpus; the counts go to `negative-audit.draft.jsonl`. This also covers the 53 v2 negatives (design decision 7).

### Phase 3: Opus 5.5, verify, fix, record the review
- Batches of about 30 intents in parallel, then one adjudication agent over all negatives and all OR intents (cross-batch duplicates, answerable-elsewhere).
- Per intent, using the stored evidence (seed quote, `gen-log`, canonical text, the page-map) and not the generator's claim:
  1. locate each quote and read the surrounding section; the reference answer must follow from the spans and from nothing else;
  2. **single-passage**: the span alone answers; **multi-passage**: each listed span is necessary and the set sufficient; **OR**: each alternative sufficient;
  3. **negative**: search the whole corpus (all `search_terms`, synonyms, VI/EN variants, numbers) and read the top candidate sections; conclude the detail is absent. A negative that is answerable somewhere is rejected;
  4. the EN and VI questions mean the same, the VI reads as natural Vietnamese, no doc-name leak, not a duplicate of an existing intent;
  5. for a translated page, compare the quote with the English original in `acquisition/orig/`: a translation drift that changes the fact is a `reject` (or a `fix` of the quote and answer to the translated text when the meaning is intact).
- Verdict `accept | fix | reject` with the evidence checked and the reason, one row per intent in `review-verdicts.opus.jsonl`, summary in `REVIEW-opus.md`. `fix` edits the **seed**, then the builder reruns and the fixed rows get a second Opus check (one round). A batch with more than 30 % rejects is regenerated once by Sonnet, then reviewed again.
- Rejected rows become `review_status: excluded` (kept, not scored). Accepted rows become `reviewed`; fixed rows `adjudicated`.

### Phase 4: record, freeze, measure (orchestrator)
- `review.jsonl` entries as in `sop-main-v2` (see Review basis). The 293 carried v2 reviews are kept, with `rebased_from`, except the questions excluded by design decision 7.
- `python -m sopilot_eval.dataset --dataset datasets/sop-main-v3 --require-reviewed`, then `--freeze` (`frozen_by: "owner (delegated to Claude, V2-45)"`).
- Write `eval/datasets/sop-main-v3/README.md` (stratum table, counts, models, limits) and `SOURCES.md` (per-page URL, commit, license, attribution; CC BY-SA applies to the translations and to quotes from them).
- Preview benchmark with the six configurations on the test split; report per stratum and the share of questions every configuration answers at recall@5 = 1.0. No filtering (design decision 6).
- Write `owner-spotcheck.md`: 30 random reviewed rows (seeded) with quote, answer and verdict, so the owner can check a sample later at no cost.

## Review basis (what the label means)

The owner delegated review on 2026-11-17 ("I have no time left") and asked that the rows be marked as owner-reviewed. The v2 precedent is followed: `reviewer_id: "owner:tiên"`, `review_basis: "claude_review_delegated"`, `ai_reviewer: "claude-opus-5-5"`, plus `owner_delegated: true` and `owner_seen: false`. **No human has read the new rows.** The README and the research report must say so; the spot check file is the path to change that. The generator (Sonnet) and the verifier (Opus) are the same model family, so the deterministic gates (quote location, overlap, negative search) carry real weight. If the owner's spot check finds more than 3 wrong rows in 30, the dataset is re-reviewed before any number is published.

## Acceptance criteria

- [ ] `sop-main-v3` exists, validates (`sopilot_eval.dataset … --require-reviewed`) and is frozen; `sop-main` and `sop-main-v2` hashes are unchanged.
- [ ] ≥ 55 new documents, none duplicating the 23; each page indexed in one language only; translated pages pass the mechanical check and carry `translated_from`.
- [ ] ≥ 520 reviewed rows in total; the stratum table meets the Targets above or the README states each shortfall and why.
- [ ] Every new answerable row has verbatim quotes located in the canonical text; every new negative has a whole-corpus search with zero hits confirmed by Opus.
- [ ] The 53 v2 negatives were re-audited against the new documents; each result is recorded.
- [ ] `review.jsonl` rows follow the Review basis; the README states that no human reviewed the new rows.
- [ ] Splits are by document; the validator reports no evidence or leakage-group overlap between dev and test.
- [ ] Preview run of the six configurations completes; results per stratum and the "all configs = 1.0" share are in the README (no questions removed for it).
- [ ] `owner-spotcheck.md` with 30 seeded rows is written.
- [ ] Tests for the builder/canonical extension pass (`cd eval; uv run pytest -q`); `./scripts/docs/check-docs.ps1` passes.
- [ ] `PLAN.md` counters stay consistent (`plan_check.py`). The ticket moves to `done` only with owner acceptance (CLAUDE.md constraint 11); the run ends in `review`.

## Risks

- Translation drift (Haiku) changing a fact: mechanical check, Opus comparison with the English original, and the translated-corpus tag.
- A generated near-miss that is answerable elsewhere: whole-corpus search by script and by Opus; v2 had one such case.
- The bigger corpus shifts every metric: results are not compared with V2-07 numbers; V2-37's retrieval matrix should be rerun on v3 (owner decision, not part of this ticket).
- Same-family generator and verifier: deterministic gates, the 30-row spot check, and the honest `review_basis`.
- Licence: CC BY-SA 4.0 attribution for the pages, the translations and the derived questions.

## Verification

| Criterion | Command / test | Result |
|---|---|---|
| Dataset validates and is frozen | `cd eval; ./.venv/Scripts/python.exe -m sopilot_eval.dataset --dataset datasets/sop-main-v3 --require-reviewed` | filled in at review |
| Builder/canonical tests | `cd eval; uv run pytest -q` | filled in at review |
| v1/v2 unchanged | hash check in `manifest.json` (`derived_from`) | filled in at review |
| Docs, PLAN | `./scripts/docs/check-docs.ps1`; `python eval/sopilot_eval/plan_check.py` | filled in at review |

## Evidence

**Phase 0 (2026-11-17), branch `feat/eval-corpus-expansion`, not committed.** `eval/sopilot_eval/extra_corpus.py` (new), `eval/sopilot_eval/extend_dataset.py` (`--extra-corpus`, `subset=v3`, review rebase, `negative-recheck.json`), `eval/build_canonical.py` (`--only handbook-v3`, writes `manifest.extra.json` / `page-map.extra.json`, never `manifest.json`). `cd eval; uv run pytest -q`: 193 passed (new: `tests/test_extra_corpus.py`, three tests in `tests/test_extend_dataset.py`; `test_review_regressions.py` ticket count 44 → 45). Smoke: `PYTHONPATH=services/ai-service/src uv run --project services/ai-service --extra pdf python eval/build_canonical.py --dataset <dir> --only handbook-v3` built one handbook page through docproc. Phases 1 to 4 not run yet.

**Phases 1 to 4 (2026-11-17), run end to end under the delegated review basis; not committed. No human has read the new rows.**

- Dataset: `eval/datasets/sop-main-v3` (gitignored `datasets/`): 83 documents, 582 reviewed rows (292 carried from v2, 290 new = 145 intents), validated with `--require-reviewed` and frozen (`frozen_by "owner (delegated to Claude, V2-45)"`). `sop-main` + `sop-main-v2` file-hash unchanged (checked against the hash taken before Phase 1).
- Models: Haiku `claude-haiku-5-5` acquired and translated 28 pages (Haiku hit a usage limit; Sonnet repaired 7 and translated 2); Sonnet `claude-sonnet-5-5` generated 10 batches; Opus `claude-opus-5-5` verified, re-checked fixes and adjudicated. Per-page translator in `acquisition/sources.json`.
- Opus verdicts: round 1 on 150 intents = 115 accept / 32 fix / 3 reject (reject 2 %); fixed intents rechecked = 27 accept / 5 fix; 2 duplicates dropped; 1 v2 negative question excluded (53 v2 negatives re-audited: 33 intents still unanswerable, 1 unclear).
- Strata vs targets: single-passage 76/80 (short 4), multi-passage 41/40, negatives 28/30 (short 2), number_deadline 55, condition_exception 48, comparison 19, OR-alternatives 0 new (no overlapping new pages). Not done: no-diacritics derived probes.
- Preview: six configurations on the test split, `eval/results/v3-preview/20261117-221436-08f3dd70` (dense span_recall@5 0.869, bm25 0.497, hybrid 0.659); share answered by all six at 1.0: new rows 37 %, v2 42 %, v1 74 %; no question removed. `preview-strata.md` in the dataset. Needed a small change: `docproc_chunks.py` reads `handbook-v3` sources.
- `cd eval; uv run pytest -q`: 193 passed. `python eval/sopilot_eval/plan_check.py`: counters match. Owner spot check: `owner-spotcheck.md` (30 rows, seed 45).
- Owner spot check 2026-11-17: 30/30 rows marked OK by the owner, going by the Opus verdicts shown (`owner-spotcheck.md`); the other 260 new rows are unread by a human.
- Not verified: no human review of the other new rows; translations not checked by a human; `check-docs.ps1` result below.
