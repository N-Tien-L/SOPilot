---
id: RESEARCH-02-dataset-and-labeling
title: "Workstream 02: the GitLab corpus and an evidence-labelled EN/VI eval design"
status: final
type: research
scope: research
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
refs:
  - docs/research/research-01-scope-and-rqs.md
  - docs/archive/handoffs/HANDOFF-research-workstreams-2026-10-18.md
  - eval/README.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. This is the design of 2026-10-19; the dataset actually built is `sop-main`/`sop-main-v2` (see AUDIT-eval-rq1-rq3), with a bilingual corpus rather than this EN-only GitLab design. The former agent instructions file is as it was at the time.

# Proposed corpus and eval set for SOPilot

## 1. Final recommendation and level of completion

**Choose a subset of the GitLab Handbook, native English SOPs: 8 public pages, starting with the 24 heading-bounded sections in §3. Build 120 distinct question intents, each with one EN and one VI question: 240 query rows; dev 30 intents/60 rows, test 90 intents/180 rows.** In each language: 72 single-passage questions, 24 multi-passage questions, 24 unanswerable questions. Preselect an answer-level subset of 32 intents/64 rows, using one fixed API generator, two conditions with rerank off/on, and human reviewers. Do not translate the corpus and do not mix in other companies' handbooks.

This is the proposed implementation following the owner's request to prioritize speed, without an extra round of ordinary source selection. RQ1–3 are the core; RQ5 uses two embeddings chosen by workstream 03, run sequentially on CPU/32 GB RAM; RQ4 is outside the core. Generation is not needed for the whole retrieval eval or for both embeddings. Workstream 01's claim limits are kept: EN/VI queries on an EN corpus; a VI corpus or two-way cross-lingual is not verified.

`final` means workstream 02's selection and design document is complete. **There is no downloaded/SHA-pinned corpus, no 120 intents, no gold labels and no reviewed answer outputs yet.** The numbers below are pre-experiment design, not an inventory of data created or evidence of statistical power. It does not claim the owner has approved the PRD/ADR/PLAN or that reviewers have been assigned.

## 2. What was checked in the repo

`git status --short` was checked before reading content; the current branch `fix/auth-google-roster-admission` has many pre-existing staged/unstaged/untracked changes, including `eval/`. The workstream 02 target file did not exist at the start. Read the former agent instructions file, `docs/README.md`, the whole workstream 01 handoff and the workstreams handoff; `.env` not read. Only this report was added; no branch, code, PRD/ADR/PLAN/ticket or other sessions' files changed. Workstreams 03–04 run in parallel; their results are neither awaited nor assumed.

| File/input read | State on disk | Consequence for the design |
|---|---|---|
| `eval/README.md`, `datasets/smoke/` | 3 Markdown files, 9 queries; 7 answerable, 2 unanswerable; 8 VI, 1 EN. The smoke corpus mixes EN/VI; only one VI question has `cross_lingual: true` | Tool smoke only; not reused as a corpus/new research or added to the 120 intents |
| `questions.jsonl` | Fields in use: `id`, `question`, `lang`, `cross_lingual`, `answerable`, `expected: [{doc, pages?}]`, `reference_answer`; unanswerable has `expected: []` | Missing split, meaning group, source version, section/span, label checks and an unanswerable log |
| `sopilot_eval/corpus.py` | Only reads files directly in `corpus/`, MD/TXT/PDF extensions; `\f` is a page break in text; MD without it is one page. Chunks have only `doc/page/text`, the SHA of the text | Do not assume DOCX, recursive folders or offsets are supported. A lone text SHA does not distinguish two locations with the same content |
| `split_text` | Windows by characters/paragraphs; default 800 characters, overlap 100; may split long passages | Labels must be independent of the chunk configuration; characters are not tokens |
| `metrics.py` | Hits by file/page, `is_hit` returns the first target; Recall counts covered targets. DCG adds each hit chunk, the ideal by target count | A long MD file can be scored correct even when the wrong section is retrieved. Two targets in the same file/page may be ambiguous; duplicate chunks can push nDCG above 1. Do not use this metric as a finished span-level one |
| `run.py`, `retrievers.py` | Runs every row in `questions.jsonl`, without split/group filtering; outputs do not yet have enough chunks/offsets to compare spans. The refusal sweep is a score proxy and does not call a generator | Separate dev/test exports and mapping artifacts are needed from workstream 04; do not run test to choose a threshold and then report it as independent verification |
| `configs/rq1-rq3-bge-m3.yaml`, `embedders.py`, `tests/test_eval.py` | The model config does not pin revisions; embedder/reranker capped at 512 tokens; tests are mostly smoke, file/page and fusion | The config name does not prove answer-level RQ2–3 have been done; check truncation/mapping before the research run |

This document specifies an offline eval dataset; it does not change the application's DB schema, endpoints, events or RBAC. The artifacts expected in §8 are a handover contract, not files created.

## 3. Corpus source, take list and boundaries

### 3.1. Why GitLab

GitLab has public procedures and the owner has used this source before. [Content Websites](https://handbook.gitlab.com/handbook/about/maintenance/) identifies the public handbook repo; [View page source of Onboarding](https://gitlab.com/gitlab-com/content-sites/handbook/blob/main/content/handbook/people-group/general-onboarding/_index.md) gives the Markdown path. This makes it easy to pin a shared version and keep the heading structure. The web tool currently returns only `Loading` on the GitLab source page: **the Markdown bytes or an immutable SHA are not verified**; the source link does not count as data obtained.

The only comparison: the [Added Bytes Handbook](https://handbook.addedbytes.com/) has onboarding, offboarding, holidays and remote work sections, small and possibly easier to read; the home page says CC BY-SA 4.0 except images/logos, and it partly derives from GitLab. Neither enough question intents nor a public immutable revision of this source have been inventoried. **Keep GitLab** for familiarity, a clear source path and many operational sections to get enough distinct questions; do not mix Added Bytes into the same corpus to make up numbers or call it an independent domain.

### 3.2. Initial allowlist: 8 pages, 24 section units

The pages and headings below were read from the official source on **19/10/2026**. This is the concrete take list; section names must be checked again on the pinned snapshot before assigning IDs. Each unit takes one continuous region under a heading, keeping whole condition/exception sentences and related lists; scattered passages are not taken to pre-fit a question.

| Code / units | Official source URL | Sections to take | Excluded scope |
|---|---|---|---|
| ONB / 3 | [GitLab Onboarding](https://handbook.gitlab.com/handbook/people-group/general-onboarding/) | The introduction before `TaNewKi Welcome Call`; `TaNewKi Welcome Call`; `Managers of New Team Members` with its subsections | No internal issue templates, engineering/sales/support or contractor onboarding |
| BUD / 2 | [Onboarding Buddies](https://handbook.gitlab.com/handbook/people-group/general-onboarding/onboarding-buddies/) | `Buddy Responsibilities`; `Managers: Who should I pick as an Onboarding Buddy?` | No org charts, long email examples or personal profiles |
| OFF / 2 | [Offboarding FAQ](https://handbook.gitlab.com/handbook/people-group/offboarding/faq/) | `Timing`; `Your Laptop and Account steps` | Drop payroll, benefits and country-specific rules |
| AWAY / 4 | [Time Away Philosophy](https://handbook.gitlab.com/handbook/people-group/time-off-and-absence/time-away-philosophy/) | In planned time away: the continuous region from `Communication Essentials` to the end of `Communication Checklist`; `Calendar and Meeting Management`; `Knowledge Transfer and Work Continuity`; plus `Communicating Unplanned Time Away` | Drop the general essay, personal data and job aids needing sign-in |
| PTO / 3 | [Time Off Types](https://handbook.gitlab.com/handbook/people-group/time-off-and-absence/time-off-types/) | In `Flexible Paid Time Off (PTO)`: the region from `Overview` to the end of `PTO Protocols (Planning and Coordination)`; `How to Prepare for PTO`; in `Sick Time`: `Reporting Procedures` | Do not open country subpages, statutory benefit levels, medical schemes or long-term leave |
| COM / 3 | [GitLab Communication](https://handbook.gitlab.com/handbook/communication/) | `Asynchronous communication`; `Indicating availability`; `Emergency chat` with its subsections | Drop everything else, personal information, tool guides outside the allowlist |
| MEET / 3 | [All-Remote Meetings](https://handbook.gitlab.com/handbook/company/culture/all-remote/meetings/) | In `How to run an effective meeting at GitLab`: `What to do before the meeting`, `What to do during the meeting`, `What to do after the meeting` | Drop repeated tip/FAQ lists and videos/images |
| EXP / 4 | [Global Travel and Expense Policy](https://handbook.gitlab.com/handbook/finance/expenses/) | `2. Responsibilities`; `3. General Guidelines` with subsections; `Equipment` with subsections in non-travel expenses; `4.4 Reimbursement Payout Timelines` with subsections | Do not take all of airfare/hotel, procurement, gifts, legal and linked Drive documents |

**Corpus coverage:** responsibilities/steps/timing in the employee lifecycle, preparing for leave and handover, remote communication/meetings, responsibilities and reimbursement of work expenses. This is a subset of one company's operational procedures/policies; not every page is called an "SOP", and it does not represent industrial SOPs or Vietnamese labour law. Questions must name GitLab and the subject conditions where needed; keep US/non-US or entity-type distinctions if the chosen part contains them, and do not apply figures to every employee.

**Take limits:** the 24 sections are editorial units, not 24 web pages or 24 chunks. Store 8 canonical documents by page, with the section allowlist; only allowlisted content is indexed. Expected about **15,000–30,000 EN words**, a few hundred chunks at the current character configuration; not measured, so this is an estimate. Do not add text to reach a word count. If it is smaller but has enough independent intents, keep the corpus small. If there are fewer than 120 intents after deduplication, open adjacent sections of the same 8 pages (preferring operational content), recording the change before creating/freezing test; do not make up the shortfall with paraphrases or translations. If still not enough, report the shortfall and do not pass the data gate; do not lower the ≥100 mark.

Whatever the public content says can be used exactly as said. For example, the public Onboarding page describes when an issue is opened; that sentence is not removed just because it links to something internal. But **do not infer issue contents, step lists in Compass/Workday/Drive/Slack or video content from link names alone**. Record unreadable links in `excluded_dependencies`, not as evidence. Questions needing the content of those links should be removed from the core eval to reduce ambiguity; if kept as unanswerable, state "missing from the chosen corpus".

### 3.3. License and version pinning

[GitLab Handbook Usage, External use](https://handbook.gitlab.com/handbook/about/handbook-usage/#external-use-of-the-handbook) states the handbook content is under **CC BY-SA 4.0**. Do not infer the content license from the repo's software LICENSE. Per [Creative Commons BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), distribution requires attribution of the source/authors, a license link, a statement of changes and ShareAlike compliance for adaptations. The extracted/reformatted corpus package and data derived from the chosen content are CC BY-SA 4.0; the whole repo's code license is not changed. Take only text, dropping logos, images, unnecessary personal data and third-party assets with their own terms; a public page does not automatically license every linked file.

The acquisition procedure for the later execution step:

1. Resolve **one full commit SHA** of `gitlab-com/content-sites/handbook`, using that shared SHA to take all 8 pages and the includes actually needed. Do not use the `main` branch, an access date or the differing "Last modified" SHAs of individual pages as a consistent snapshot.
2. From `View page source`, record the exact path at that commit; store the raw bytes, `sha256_raw`, the reader-facing source URL, the immutable source URL and `retrieved_at` UTC. Do not guess the path from the URL and treat it as verified. If the Markdown has templates/includes, resolve them at the same SHA and store dependency hashes; if they cannot be resolved, do not use the missing region for gold.
3. Extract exactly the allowlist into canonical UTF-8, Unicode NFC, LF newlines, keeping the heading/list/sentence order and anchors. Drop navigation/footers and non-rendered HTML/templates; keep link labels as text but do not load target pages. Store `normalization_version`, `sha256_canonical`, source ranges and the attribution/license notice. Chunk exactly this canonical text.
4. Derive `corpus_version` from the source SHA + manifest/allowlist + canonical hash + normalization version. The same source SHA with different section selection/normalization is a different corpus version. When publishing, keep the notice "GitLab Handbook, GitLab and contributors", the source URL, SHA, license, retrieval date and a description of what was dropped/reformatted.
5. If the source repo cannot be read at download time, use a public HTML snapshot with a raw hash and capture time for **all** 8 pages, recording `pin_mode: web-snapshot`, and store a reproducible content copy; do not claim a git pin. Recheck content/headings/labels before freezing. Prefer git; do not let an acquisition failure become fake source evidence.

No fake SHA is filled in and no claim is made that the corpus has been downloaded in this report. The source check date does not guarantee the policies are the same at the commit that will be chosen.

## 4. Question scale, splits and sample limits

### 4.1. Counting by intent and by query row

An `intent_id` is one information need with the same conditions and answer, with exactly two language variants. 120 intents **do not mean 120 fully independent observations**, since they share policies/sources; but they meet the expected ≥100 mark even without counting translations as new questions. If the proposal later requires ≥100 separate **test** intents, the 90-intent test design does not meet it: the sample must be increased before freezing, not recounted. The 01 handoff currently says ≥100 questions in total, not ≥100 test.

| Intent type | Dev: intents | Test: intents | Total intents | Total EN + VI rows |
|---|---:|---:|---:|---:|
| Answerable, single passage | 18 | 54 | 72 | 144 |
| Answerable, multi-passage | 6 | 18 | 24 | 48 |
| Unanswerable, near the topic | 6 | 18 | 24 | 48 |
| **Total** | **30** | **90** | **120** | **240** |

| Split / query→evidence direction | Single passage | Multi-passage | Unanswerable | Total rows |
|---|---:|---:|---:|---:|
| Dev EN→EN | 18 | 6 | 6 | 30 |
| Dev VI→EN | 18 | 6 | 6 | 30 |
| Test EN→EN | 54 | 18 | 18 | 90 |
| Test VI→EN | 54 | 18 | 18 | 90 |

For unanswerable questions, the arrow describes the language of the corpus searched, not that evidence exists. `lang=vi`, `corpus_lang=en`, `direction=vi_to_en`; for compatibility with the current flag, `cross_lingual=true` for every VI question, with this convention stated. Unanswerable questions have no positive retrieval gold; do not assign Recall=0 and mix them into the answerable mean.

A single passage is one short paragraph/list containing the full conditions and answer; multi-passage needs at least two separate evidence regions, in the same section or different sections/pages. Do not call it multi-passage just because the splitter cut one passage into two chunks. Of the 24 multi-passage intents, aim for 12 within one page and 12 across pages, dev 3/3, test 9/9; this is a quota to check during preparation, without forcing unnatural synthesis questions. At most three essential passages per question to keep the review effort low.

Cover every topic cluster in §3; at most 20% of intents from one source page, so the long EXP/COM sources do not dominate. Prefer questions about actions, roles, conditions/timing, exceptions and simple synthesis. Do not create dozens of variants changing one number/name of the same rule. The VI version must be natural and keep all conditions, numbers, units and negations; tool names/identifiers may stay in EN. The corpus must not include translations or reference answers.

### 4.2. Splitting before using models, and preventing leakage

1. Build a `policy_family_id` by shared rule/procedure and repeated source, not only by URL. Join sections expressing the same fact (for example preparing for PTO and announcing absence), paraphrases, EN/VI pairs and question revisions into the same `leakage_group_id` with connected components.
2. Assign content groups to dev/test before comparing models; the same fact/evidence or positive/near-negative variants must be on the same side. Multi-passage questions only take evidence from families in the same split; if they connect both sides, move the whole component and rebalance the quota before freezing. Do not split the 240 rows randomly.
3. Check normalized text, lexical near-duplicates and meaning in both EN and VI. Embeddings may suggest duplicate pairs, but an evaluated model must not be the sole decider. A VI version changing a condition must be fixed or split into a separate intent, not treated as equivalent automatically.
4. Every configuration indexes **the same whole EN corpus**, including the sections used to write both dev and test questions. This is query-held-out eval within a known corpus, not document-held-out evaluation. A public corpus may be in LLM pretraining: do not claim contamination is eliminated; check that outputs are grounded in the supplied context.
5. Dev is used for the pilot and for choosing thresholds and configurations. Lock `split_version`, the allocation seed, query IDs and hashes before test; do not put test/test gold into prompts generating dev questions, tuning or model selection. If the label builder also runs the models, state that there is no independent test steward.
6. Fix gold after test only for annotation errors, with a before/after/reason/reviewer log; bump the dataset version and rerun **every** affected condition. Do not replace questions a model got wrong with easier ones.

Report sample counts by language and question type, and paired differences on the same queries; bootstrap/CIs should cluster EN/VI pairs and policy families per workstream 03, not bootstrap the 240 rows as independent. Test has only 18 unanswerable and 18 multi-passage intents per language; one error shifts that cell by about 5.6 percentage points. Do not use the large total row count to hide uncertainty, and do not infer representativeness of industry SOPs or symmetry between the two languages.

## 5. Stable evidence labels and chunk mapping

### 5.1. Canonical evidence is the gold, chunks are derived products

| Proposed object / field | Definition |
|---|---|
| `doc_id`, `source_path`, `source_commit`, `corpus_version` | A stable logical page ID and the specific version; a changed source path gets an alias table, never reassigning an ID to another source |
| `section_id`, `heading_path`, `anchor`, `section_sha` | The section ID within the corpus version, the heading tree and the text hash; the anchor is for opening the source and does not by itself guarantee stability |
| `span_id`, `doc_id`, `section_id`, `start_char`, `end_char`, `quote_sha`, `quote` | 0-based, end-exclusive Unicode code point offsets over the whole canonical document; the quote is the minimal EN text sufficient to support the claim, including essential conditions/exceptions. Byte offsets, web Markdown line numbers or chunk ordinals are not gold |
| `required_claims`, `evidence_sets` | Short claims/answers by condition. Each evidence set is a list of spans needed **together** (AND); the sets are alternative sufficient evidence (OR), confirmed by reviewers |
| `chunk_id`, `chunking_version`, `doc_id`, `source_intervals`, `text_sha` | An ID made of corpus version + doc/location + splitter/config hash; mapping from the chunk's text back to the canonical text. Chunks with identical text in two places still get different IDs |
| `annotation_status`, `reviewer_id`, `reviewed_at`, `label_version` | Use `draft`, `reviewed`, `adjudicated`, `excluded` for labels (not ticket statuses); only reviewed labels go into the locked set |

A structural example, **not a real question/label**: `evidence_sets=[[s1,s2],[s3]]` means s1+s2 are needed, or just s3 if s3 alone contains equivalent content. Hitting s1 is not finding the full answer. The EN and VI references rest on the same claims/evidence, not on the answers of the model being scored.

When normalization or the source changes, old span IDs still refer only to the old version; create a new mapping/review rather than shifting offsets and assuming the labels remain correct. Keep the quote hash so wrong offsets fail. Do not put annotator explanations or references into the index.

### 5.2. Mapping rules and evidence completeness

- The splitter must output offsets or a passage mapping into the canonical text; the current code strips/joins/overlaps text, so it cannot be recovered by finding the first string match if a quote repeats. Heading context added to chunks needs its own mapping; automatically added metadata must not create new evidence.
- For top-k, take the union of source intervals **actually present in the retrieved text**. A span is covered when all its essential content is within that union, ignoring the specified whitespace differences. Two adjacent chunks may cover one span together; touching a few characters does not earn full credit. Overlapping chunks covering the same span count once.
- For each evidence set, `evidence_recall@k = spans covered / spans required`; with several alternative sets, take the max per set, never mixing half of one set with half of another. `complete_evidence@k=1` when at least one set is fully covered. Report this and the at-least-one-span hit; for multi-passage questions, a hit cannot replace complete.
- This is evidence-sufficiency relevance, not a judgement that every on-topic passage is relevant. `hard_negative_span_ids` records sections very close in meaning but with the wrong condition/subject or missing a claim; they do not become positives because a retriever ranks them high. When a valid equivalent source is found missing, reviewers add an alternative set through a versioned process for every configuration.
- Before the research run, every gold span must resolve correctly in the canonical text and be coverable by the full chunk index. After tokenizer/context truncation, remeasure the evidence still visible at embed/rerank/generator time; record at which step evidence is lost. Do not silently drop hard questions or change gold to fit a chunking that favours a model.

**Harness compatibility:** file/page `expected` can be exported for smoke, keeping flat file names since the loader is not recursive yet. Merely adding group/split columns does not make the current scorer understand spans. Do not fake each span as a "page" or a tiny file to get nice scores; that changes the retrieval context. Workstream 04 needs a sidecar loader/adapter and an evidence-aware scorer. Until there is a mapping, file/page scores are only a proxy and must be labelled as such; do not publish them as the main result of this gold set. nDCG needs a relevance/rank-depth definition and de-duplication of counts settled with workstreams 03–04; do not apply the current formula directly to evidence sets.

## 6. Answerability and corpus-wide unanswerable checks

Answerable means there is enough information to answer the required claims within **the whole locked corpus version, under the same access scope**. If the source gives only part, a question requiring the missing part is unanswerable; record `reason=missing_required_detail` and the claims that do exist, to check partial answers. Links outside the allowlist are not part of the corpus, even if the internet has the answer. Do not label a question unanswerable because the top-k retriever missed.

The 24 unanswerable intents consist of 12 missing a near-topic detail/procedure; 6 changing a condition/subject the corpus does not regulate; 6 requiring synthesis with a missing part. Dev 3/1/2, test 9/5/4 respectively. Do not use meaningless/clearly off-topic questions, personal accounts or undefined "this year" deadlines. A question directly contradicting the corpus that can be refuted with evidence **is answerable as a premise correction**, not unanswerable by default. Ambiguous questions where asking back would be reasonable should be clarified or removed, not forced into a binary label.

The mandatory procedure for each unanswerable intent, reapplied whenever the corpus changes:

1. Write down the missing information, the EN/VI keywords, synonyms and policy family; point out the nearest near-negative and why it is not enough. The EN/VI pair must ask for the same missing detail.
2. Search **the whole canonical corpus** with exact/keyword search and synonyms, and read the related sections; also check off-topic sections that might contain the answer. Store the corpus hash, search terms and candidate section IDs. Web search is only for verifying sources, never for silently adding to the corpus.
3. When the tooling is ready, take the union of BM25 and both dense models, at most top-10 per branch, deduplicate, and have reviewers read the candidates not yet seen. This detects missed labels; it does not prove absence because every model missed. Without models, labels can still be prepared by word search/reading the whole scope; do not freeze the final labels before the candidate comparison step.
4. The reviewer confirms there is no sufficient evidence set in any valid section. Store an `unanswerable_audit` with the reason, candidates checked, the whole-corpus scope, person/date and conclusion. If an answer exists, move it to positive and add spans, or replace the question before freezing, then rebalance the quota by group; do not keep a negative label to preserve the ratio.
5. Independently review **all 24 negative intents** again if there is a second reviewer; on disagreement, mark `excluded/pending` and resolve it with the source, not by voting on LLM output. A single person re-reviewing after a break must record it as self-review, not as two-person agreement.

Do not mine candidates to pick questions only one model fails and then call the test "neutral". The questions are chosen in advance; the model pool in step 3 only finds gold errors. If an error is discovered through test results, apply the versioned label-fix procedure in §4.2.

## 7. The answer-level subset and review effort

### 7.1. Fixed scale before generation

Choose with stratification and a public seed **32 intents = 64 rows** from the 120, keeping the split and EN/VI pairs. Choose by question type/topic before seeing outputs or the winning model; cover the topic clusters, not only easy questions or those rerank does well on.

| Answer subset | Single passage | Multi-passage | Unanswerable | Total intents / rows |
|---|---:|---:|---:|---:|
| Dev | 4 | 2 | 2 | 8 / 16 |
| Test | 14 | 4 | 6 | 24 / 48 |
| **Total** | **18** | **6** | **8** | **32 / 64** |

Run one retriever/dense baseline and a fixed candidate pool chosen by workstream 03, rerank off/on, **with the same generator, prompt, context budget and citation policy**. Two conditions × 64 queries = at most **128 answer outputs** (32 dev, 96 test) to read; do not multiply by the two embeddings for answer-level RQ5. Answer in the query's language. Store the input context verbatim, the chunk order, output, citations and any spontaneous refusals by the generator; the context must not contain the reference answer.

RQ3 uses a gate fixed before generation: outputs of the same context/prompt above may be reused for questions the gate lets through; questions the gate blocks are deterministic refusals. Compare with no gate on **the same queries**, without calling the API again for each threshold. Reuse is valid only if the gate does not change the prompt/context/generator. Evaluating a different refusal prompt is a different generation condition needing more outputs and review effort; do not infer it from scores only. Lock the threshold on dev per workstream 03; test only applies the locked threshold. The 60-row dev set can calibrate the score proxy, but only 16 dev rows have output labels, so it is not enough to claim the threshold optimizes real answer risk on every question.

The answer-level test set has only 24 intents, of which 6 negative and 4 multi-passage per language; one error shifts the refusal rate of the negative group by about 16.7 percentage points. Report it as exploratory, with denominators, uncertainty and error examples; do not claim a product quality threshold is certainly met from this sample. If firmer conclusions are needed, enlarge the subset by the same rule before test; prefer adding review effort over adding models.

### 7.2. Short reviewer checklist

**Dataset review (each intent, both languages):**

1. The question states its conditions clearly and needs operational information; EN/VI mean the same and do not hint at the answer; in the right split/family, not sharing a fact with the other side.
2. The answerability label is correct over the whole corpus; positives have enough EN spans and exceptions; negatives have an audit, not just a retrieval miss.
3. The EN and VI references/required claims are supported by the source, with numbers/units/subjects unchanged; quotes/offsets/hashes resolve. Record reviewer, date, decision and the reason for any edit.

**Output review (config names hidden, order shuffled, IDs kept for pairing):**

1. `decision`: answered / refused / partial / invalid; for positives, were all claims answered with the right conditions? `correctness`: 0 wrong, 1 partially right, 2 complete/right; negatives are not scored for correctness against an empty reference string.
2. `faithfulness`: is each factual claim supported by **the context actually given to the generator**? Record supported claims/total claims and the wrong claims; a right answer from knowledge outside the context is still not grounded.
3. `citation`: does the link/ID open the right doc/section/span; does each citation support the claim attached to it; how many claims needing citations have valid ones? Store counts to compute precision/completeness; a 0 denominator is recorded as N/A. A question with claims needing citations but none given: completeness 0.
4. `refusal`: a refused positive is a false refusal; a negative given a decisive answer for the missing part is a false acceptance. Answering the grounded part and stating clearly what is missing is `partial`; workstream 03 must set the counting rule before test; not every partial is a correct refusal.
5. The output language is as required, the VI natural/understandable; quoting evidence in EN is valid. Record the main error briefly: retrieval missing, context/truncation loss, wrong synthesis, dropped condition, wrong citation or wrong refusal.

Keep correctness against gold, faithfulness against context and citation per claim separate. Reviewers may use the claims instead of a long model answer to reduce style comparison effort. LLMs only help with drafts/candidates/query translation; reviewers must open the source, and an LLM judge is not gold.

### 7.3. Estimated workload and the disagreement mechanism

| Task | Estimated person effort (not measured) |
|---|---:|
| Narrowing/reading the 24 sections, checking extraction and the manifest | 3–5 hours |
| Drafting/reviewing 120 intents, claims/spans and negative audits, 5–8 minutes per intent on average | 10–16 hours |
| Drafting/reviewing 120 VI variants, 1–2 minutes per intent on average | 2–4 hours |
| Reading 128 outputs, 3–5 minutes per output on average | 6.4–10.7 hours |
| Second reviewer: all 24 negative intents + 24 stratified positive intents; 32 outputs covering every language/type | 4–7 hours |
| **Expected total** | **About 26–43 person-hours**, excluding time to resolve disagreements/run inference |

These are total person-hours, not a deadline; a pilot of 12 dev intents (6 single-passage, 3 multi-passage, 3 negative, both EN/VI) and 8 dev outputs replaces the estimate with real time. The main reviewer reads 100% of the data and outputs; the second reviewer independently checks the parts above, every unclear case and serious citation/claim errors. On disagreement: store both initial labels, the disputed span/claim and the adjudication decision; unresolved items do not enter the locked gold. Report agreement on the double-scored set, without extrapolating to the whole dataset.

If only the owner reviews, it can still be done in two passes separated in time, with model names hidden; record `single_reviewer/self_review` and the lack of independent checking. Do not assume extra people or extra owner time. Do not cut effort by keeping LLM labels unchanged or skipping the negative questions. If the effort exceeds the estimate, keep the 120 retrieval intents and the chosen 32-intent subset first, and cut secondary models/configs; any subset change after freezing needs a reason/version and must not depend on good/bad results.

## 8. Handover contract for workstreams 03–04 and points to resolve

The paths below are **artifacts expected for a later authorized implementation**, not created in this session. Workstream 04 may choose equivalent file names but must keep the semantics and linking hashes.

| Expected artifact under `eval/datasets/gitlab-sop-en-v1/` | Minimum fields/meaning |
|---|---|
| `manifest.json` and the raw/canonical corpus | Source repo/commit or web-snapshot, 8 URLs/paths, allowlist, raw/canonical hashes, normalizer, license/attribution, excluded dependencies, corpus version; `corpus/` contains only indexed text, no gold |
| `sections.jsonl`, `evidence.jsonl` | doc/section IDs and heading paths, canonical ranges; span IDs, quotes/hashes, required claims and alternative evidence sets |
| `questions.master.jsonl` | `id`, `intent_id`, `policy_family_id`, `leakage_group_id`, `split`, `question`, `lang`, `corpus_lang`, `direction`, `cross_lingual`, `answerable`, `evidence_sets`, `reference_answer`, `type`, `review_status`, `label_version` |
| `review.jsonl` | Person/date/draft provenance, whole-corpus negative audits, candidate IDs, review/edit/adjudication decisions; kept separate from model input |
| `dev/questions.jsonl`, `test/questions.jsonl` or equivalent exports | 60/180 rows in the right groups; exports for the current CLI need an adapter to resolve the same corpus. Do not assume `run.py` already uses the split field or the parent folder's corpus |
| `chunk-map.jsonl` | Corpus/chunking version, chunk ID/location/hash, source intervals, truncation/effective text and the span mapping, complete in the run artifacts |
| `answer-subset.json`, `answer-review.jsonl` | The 32 preselected intent IDs/seed/split; run/output IDs, prompt/context/model version, claim/citation counts, rubric labels, reviewers and disagreements |

Never put test gold into the generator payload or the index; when using an API, send only the query/context needed. The dataset manifest hash + label version + split hash + subset hash must accompany every run. Both embeddings use **the same corpus/chunks/gold**; a different model must not silently change the chunking.

| Reconciliation point | Workstream 02's default handover | Who resolves / impact |
|---|---|---|
| Workstream 03's relevance may be using doc/page/chunk | Gold by span, AND/OR evidence sets; Recall and complete-evidence with the §5 semantics | Workstreams 03–04 settle the scorer; the current file/page is only a proxy. This disagreement must be resolved before test, without changing labels to suit a convenient metric |
| k, pool, token budget and the 512 cap | Workstream 02 does not settle the model/k; the mapping must keep positions after normalization and record evidence lost to truncation | Workstream 03 chooses, workstream 04 outputs artifacts; not every span is guaranteed visible in the context |
| ≥100 questions | 120 intents total/240 rows, test 90 intents | If the proposal requires ≥100 independent test items, enlarge the sample before freezing; do not raise n with translations |
| RQ2 subset/CPU rerank | Retrieval gold for all 240 rows; a fixed answer subset of 64 rows, rerank off/on | If workstream 03 needs to reduce retrieval rerank after the pilot, preselect a stratified subset and report the true sample size; do not narrow it after seeing test |
| RQ3 partial and gate score | Store answered/refused/partial separately; do not call the score sweep answer quality | Workstream 03 sets the false acceptance/false refusal rule before test; workstream 04 keeps dense/RRF/rerank/gate scores and outputs separate |
| RQ5 provider and models | One fixed generator for the subset; two retrieval embeddings, API quota not verified | Workstreams 03–05 check at run time; on running out of quota, checkpoint, never mixing providers/models within one condition |
| Rights/tenants | The core corpus is public EN under one access scope; unauthorized content is not mixed with unanswerable corpus questions | Isolation is a separate system test for workstreams 04/06, even though RQ4 is outside the core |
| Approval and data status | The report completes the design; no gold, runs or research sign-off yet | Do not edit the PRD/ADR/PLAN to reflect an acceptance that has not happened |

This is an assumption/contract so the two workstreams can work in parallel, not confirmation that they agreed. The source recommendation and review effort are settled without waiting for workstreams 03–04; before running test, these points must be reconciled once against locked documents/versions.

## 9. Concrete steps and the parts needing reviewers

| Step | Work / output | Completion gate |
|---|---|---|
| 1 | Obtain exactly the 8 pages/24 sections per §3, resolve the SHA, canonical text and manifest | Source readable, usage rights/attribution clear, original EN text without missing conditions/includes; real word/section statistics |
| 2 | Reviewer reads the inventory, identifies policy families and source overlap; builds spans/claims for a 12-intent dev pilot and the two variants | Questions are useful, quotes/offsets correct; pilot effort measured and the mapping does not confuse doc/page with evidence |
| 3 | Split families into dev/test, draft all 120 intents/240 rows per the table, check duplicates and the whole corpus for negatives | 30/90 intents, EN/VI balanced, no meaning/fact pairs across splits, complete audits and reviewers; otherwise not yet called gold |
| 4 | Workstream 04 builds the export/mapping/scorer; reconcile with workstream 03 on evidence, partial, k/context | Every span resolves/is coverable, duplicates earn no bonus, test is not used to choose thresholds; measurements correctly labelled |
| 5 | Choose the 32-intent answer subset before running, freeze corpus/labels/split/subset with hashes | Review log present, adjudication done, both sides use the same version; no test outputs used to choose samples |
| 6 | Run dev, then lock config/gate; run test and the generation subset per workstreams 03–05; people read outputs per §7 | At most 128 outputs for the two conditions, or failures/quota clearly logged; no silent model changes; sample sizes/CIs and limits reported |

**The parts that truly need people:** confirming spans are sufficient proof and conditions are right; checking the VI is equivalent to the EN; verifying the 24 intents lack a sufficient answer across the whole corpus; resolving disagreements; reading correctness/faithfulness/citation/refusal for the 128 outputs. Download/normalization/hashing, duplicate detection, mapping, quotas and table exports can be automated; they do not replace content judgement. This design does not need the owner to reselect sources, deadlines or hardware to start preparing.

## 10. Verification evidence and session limits

- Read the schema/call paths in `eval/`, verified the smoke set of 3 documents/9 questions, and recorded which fields/functions do not exist yet; no benchmark, model or API generation run.
- Looked up the official sources linked in §3 directly (8 pages, Handbook Usage, Content Websites, Creative Commons; Added Bytes for a short comparison). The GitLab source link shows only `Loading`, so acquisition/an immutable revision remains an execution gate, not evidence that the corpus exists.
- Only this workstream 02 HANDOFF file was written; no code or progress docs changed, `.env` not read, no commit/push. Since the change is only a report, the appropriate checks are content, frontmatter, counts/distributions and the target file's diff; no full stack/build/test suite was run, as those do not verify a dataset design.
- Final conclusion: **GitLab, 8 pages/24 EN sections, 120 intents/240 EN–VI queries, dev/test 30/90 intents, answer subset 32 intents/64 queries**. Implement per the gates in §9; there is no basis to call the dataset gold or conclude which method/model wins before real data and review exist.
