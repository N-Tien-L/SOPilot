---
id: RESEARCH-01-scope-and-rqs
title: "Workstream 1: scope, questions and conclusion criteria for the SOPilot research"
status: final
type: research
scope: research
created: 2026-10-18
updated: 2026-11-13
author: "Owner"
refs:
  - docs/archive/handoffs/HANDOFF-research-workstreams-2026-10-18.md
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/architecture/decisions/adr-006-free-tier-providers-and-environments.md
  - docs/execution/initiatives/v2-sopilot-mvp/PLAN.md
  - docs/research/audit-retrieval-stack-research-2026-10-18.md
  - docs/research/audit-v2-baseline-analysis-2026-10-17.md
  - temp/De_cuong_NCKH_sinh_vien_2026.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. This is the scope of 2026-10-18/19; the language scope later widened to a bilingual corpus (see AUDIT-eval-rq1-rq3, `sop-main`). `AGENTS.md` and the `docs/03-plans/` and `docs/04-reports/` paths are as they were at the time.

# SOPilot research scope and questions

## 1. Direction and handover status

**The language scope the owner clarified on 19/10/2026:** the corpus loads only native English SOPs; the eval set has English and Vietnamese questions, i.e. EN→EN and VI→EN. The corpus need not be translated into Vietnamese. Study evidence retrieval with dense, BM25 and hybrid RRF; evaluate the effect of one reranker and a refusal threshold on a human-reviewed Q&A subset. Comparing embeddings is a bounded secondary question to establish how far the hybrid conclusion depends on the dense model. CPU is a resource measurement constraint, not a reason to drop comparisons or assume a winning model.

Keep RQ1–RQ3 from the PRD as the core. RQ1b is a mandatory analysis within RQ1 if the cross-lingual commitment stays; RQ5 is secondary and can shrink to one baseline and one challenger. RQ4 on tenant overhead is a technical extension; checking that data does not leak is still mandatory for the system even if RQ4 is not done. This document does not settle models, providers, the final shortlist or the detailed experiment matrix.

**Owner update on 19/10/2026:** agreed to QĐ-01 and QĐ-02 (decisions 01 and 02), including RQ1–3 with an answer-level subset, RQ5 starting with two embeddings and RQ4 outside the core. The owner has a 32 GB RAM machine without a GPU, wants to combine local runs with free LLM APIs and prioritizes finishing quickly. The corpus source is proposed in §8.4 and not yet chosen by the owner. The owner asked to skip the generator details and the proposal's review status in this Q&A round; they are not treated as verified.

The owner's next clarification replaced the earlier proposal of four directions and corpus translation with two directions, EN→EN and VI→EN. The expected claim is **supporting VI/EN queries over EN documents**, within the limits of measured results; a VI corpus or two-way cross-lingual is not evaluated. The PRD and the overall handoff still have a wider scope; this log records the decision for the current research without editing the upstream documents.

`status: final` only closes workstream 1's survey document; it does not certify that the whole scope is locked, that the execution workstreams are done, quality acceptance or PRD/ADR/PLAN approval. The decision log in §8.3 separates what is settled from the remaining proposals. No PRD/ADR/PLAN edited, no ticket created and no code implemented.

## 2. Basis, inheritance and current gaps

### 2.1. What was checked in the workspace

| Input | Inherited content / check result | Consequence for workstream 1 |
|---|---|---|
| `AGENTS.md`, `docs/README.md` | Check Git first; keep existing work; progress docs only in `docs/03-plans/`; reports use `draft/final` | Only this HANDOFF file was added; `.env` not read, no commit/push, no status inferred from scaffolding |
| PRD-V2 §4, §6–8 | `draft`, updated 17/10; RQ1–3 primary, RQ4 secondary, RQ5 proposed; CPU without GPU; VI/EN and cross-lingual | The quality targets are still targets, not measurements or approvals |
| ADR-004/005/006, PLAN-V2 | All still `draft`; the PLAN records 0 tickets `done`, 1 `review` | The two-service and workspace architecture is a proposed target, not the current runtime |
| Workstreams handoff 18/10 | Prioritize research/reporting before deployment; reopen the embedding choice | Authority to survey and write the handover; no stack settled from the source report |
| Retrieval audit 18/10 | A conditional recommendation; BGE-M3 considered only as dense when the lexical side is a separate BM25 | Unused sparse/ColBERT does not count as a contribution; no winning model on SOPs |
| The proposal at `temp/De_cuong_NCKH_sinh_vien_2026.md` | An integrated system, data, tooling and experiments; a minimum of 100 questions expected, adjustable; calibration separate from evaluation | Do not lower the data requirement; do not claim a new algorithm. The proposal's submission/approval status has no evidence at this reading |
| `eval/README.md`, config, smoke JSONL, `metrics.py`, `run.py`, `embedders.py` | A retrieval-only harness; a smoke corpus of 3 documents, 9 questions; no EN→VI in smoke; every SentenceTransformer capped at 512 tokens; the research config does not pin revisions | Smoke only checks tooling. No human-reviewed labels or results enough to answer the RQs; EN→VI is no longer a missing condition under the scope the owner clarified on 19/10 |
| Runtime `chunk_repo.py`, `api/routes/chat.py`, `pipeline_orchestrator.py` | `bm25_search` uses `ts_rank`; chat creates `PipelineOrchestrator()`; the reranker depends on dependencies/settings in the orchestrator | Eval BM25 is not representative of the runtime; a rerank configuration is not evidence that default chat reranks |

Checked the list `docs/04-reports/HANDOFF-research*`: before writing there was only the shared handoff, no workstream 1–6 output to inherit, and the target file did not exist. No newer approval documents were found among the PRD/ADR/PLAN and the reports checked. This does not replace the owner's confirmation of decisions made outside the repo.

Git is on `fix/auth-google-roster-admission`, with many pre-existing staged/unstaged/untracked changes. This document does not claim those changes as this session's work. No branch switch or code edit to serve the survey.

### 2.2. Evidence reading rules

- **Verified:** content and state on disk, and the original sources in §10.
- **Inherited direction:** research before deployment, CPU without GPU, no assumed best model; not the same as all of V2 being approved.
- **Hypotheses:** hybrid, rerank or another embedding may improve results; results that do not support them must be allowed.
- **Resources confirmed by the owner on 19/10:** a machine with 32 GB total RAM and no GPU; combining local runs with free LLM APIs; prioritizing quick implementation, with no detailed run-hour budget required. Free RAM, the specific CPU, the real corpus, reviewers and the final generator are not verified. No project latency/quality numbers have been measured.

## 3. Research problem, subject and contributions

### 3.1. The problem to solve

A user asks about a procedure or policy in VI/EN; the evidence is in accessible documents, possibly in a different language from the question. Keyword matching may miss different phrasings; dense may find passages close in meaning but with the wrong conditions, figures or policy. Adding rerank may improve the order but costs CPU. Raising the refusal threshold may reduce ungrounded answers while also blocking questions that have answers. These are **failure mechanisms to verify**, not known SOPilot error rates.

The overarching question: **For VI/EN questions over an English SOP corpus with checked evidence labels, which retrieval and refusal configuration balances finding the right evidence, grounded answers and CPU resources?** The goal is not to prove hybrid always beats dense, or to find the best model for every document type.

### 3.2. Units and subject limits

- Corpus: native English SOPs, work instructions and policies in text form that may be used; PDFs with a text layer, DOCX, MD/TXT as extraction allows after checking. The corpus is not translated into VI. OCR and complex images/tables are outside the minimal scope.
- Main task: independent one-turn questions needing evidence in the workspace's current corpus. Follow-up conversational questions are a secondary feature check, not part of the core comparison, since they add a query-rewriting variable.
- Two directions: EN→EN and VI→EN; the arrow goes from the question's language to the evidence's language. Answers are in the question's language. VI→EN tests one-way cross-lingual retrieval; an eval set with both directions allows conclusions about VI/EN queries over an EN corpus according to the measured results. VI→VI and EN→VI are outside the current research scope.
- Definition of answerable: there is **enough** evidence to answer within the fixed corpus/version and access scope. A question whose answer exists in another workspace is still not answerable for the asking workspace; access is handled by a separate test suite.
- For each question, reviewers record which document, version and page or section contains the answer; then identify the small pieces the system split off (chunks) containing that evidence. Example: the question "Xin nghỉ phải báo trước bao lâu?" (how much notice is needed to request leave?) has its answer on page 3 of "Quy định nghỉ phép" (Leave regulation), version v2. Finding the right file but only the passage about the annual leave allowance is not enough to answer. Workstream 2 settles how finding the right evidence is scored, including when several passages are needed; do not store only chunk ordinals, since they may change when documents are re-split.
- The question set mainly contains questions answerable from one passage and questions close to the topic whose answer the documents do not contain, to test refusal. Example: a document stating "12 ngày phép/năm" (12 leave days per year) can answer a question about the number of leave days, but must refuse "Phép chưa dùng đổi được bao nhiêu tiền?" (how much money can unused leave be converted to?) if the document does not regulate it. Add a small group of questions needing several passages, such as combining the leave and unpaid leave rules to answer "Hết phép thì xin nghỉ thế nào?" (how do I request time off once leave runs out?). For now only Vietnamese/English and simple synthesis are evaluated, not complex multi-step reasoning or other languages.

### 3.3. Expected contributions and the conditions to claim them

| Contribution | Minimum evidence needed | Wording limits |
|---|---|---|
| An EN SOP corpus and VI/EN questions labelled for answerability and evidence | Source/license, a version manifest, query language, reviewers, splits and disagreement handling | Call it only a project-scale evaluation set; not an industry-representative benchmark or a VI corpus. If the corpus cannot be published, state the limited reproducibility |
| A controlled experimental analysis of hybrid/rerank/refusal on CPU | Fixed configurations, separate dev/test, paired outputs, uncertainty, error analysis and measured resources | An experimental contribution characterizing trade-offs; no claim of proposing RRF, BM25 or a new model architecture |
| A demonstration system and a reproduction package | The final pipeline really wired, verifiable citations, refusal, tenant tests and enough artifacts to rerun | System integration serving the research; quality is not inferred from a running demo or from retrieval-only results |

The scientific value comes from falsifiable questions, checkable data and factor analysis; assembling existing tools without ablation/evidence is not enough for an experimental contribution.

## 4. RQs, hypotheses and conclusion criteria

The PRD's RQ codes are kept so later workstreams can cross-reference. The table below is a proposed operationalization and does not change the official wording/priority in the PRD.

| RQ / proposed priority | Question and testable hypothesis | Comparison / evidence needed | When a conclusion can be drawn |
|---|---|---|---|
| **RQ1 — primary** | On the same corpus/chunks and a fixed dense model, how does hybrid RRF change evidence retrieval compared with dense and BM25? **H1:** improves Recall@5 over each branch alone thanks to complementarity | Dense, BM25, hybrid; the same questions and output budget; Recall@5 by evidence targets, candidate recall, a checked ranking metric, CPU cost | Report paired differences against each baseline, confidence intervals and questions won/tied/lost. Say H1 is supported only when the result is clear enough; beating BM25 but losing to dense does not mean hybrid beats both |
| **RQ1b — mandatory secondary analysis by query language** | How does the RQ1 difference change between EN→EN and VI→EN? **H1b:** dense/hybrid have a relative advantage over lexical for VI→EN; the size of the difference relative to EN→EN must be measured | The same EN corpus; report sample sizes, results and uncertainty separately for EN and VI queries. Same-meaning question groups must be identified for paired analysis and handling dependence | Do not let an overall mean hide a weak VI group. If the sample is too small, report it as exploratory/insufficient evidence; BM25 is not assumed to be 0, since names, numbers and loanwords exist. No conclusions for a VI corpus or two-way cross-lingual |
| **RQ2 — primary, two-level evaluation** | How does rerank change the evidence order, citations, faithfulness and time? **H2:** improves quality at the top of the list and may improve answers, at the cost of latency | One fixed retriever/candidate pool, the same reranker on/off; the retrieval level on the defined set; the answer level on the same subset, with a fixed generator/prompt/budget | Keep ranking conclusions separate from answer conclusions. Citation/faithfulness improvements are accepted only with answer evaluation labels, not inferred from Recall/MRR. If ranking improves but answers do not, state that H2 is only partly supported |
| **RQ3 — primary** | How does changing the refusal threshold change answer errors and false refusals? **H3:** there is an operating point on dev that reduces unsupported answers while keeping useful coverage, and the trade-off holds on test | The same pipeline, a threshold chosen on dev, compared with always answering; answerable/unanswerable labels and output quality; coverage and errors by class/language | Lock the threshold before test. Report both false refusals on answerable questions and accepted answers on unanswerable ones, plus errors among questions actually answered. If safety is reached only by blocking almost everything, H3 is not accepted as practically useful |
| **RQ5 — bounded secondary** | Does an alternative dense model improve dense alone and its contribution to hybrid, within the CPU budget? **H5:** model rankings in dense alone may differ within hybrid; no specific model is assumed to win | At least a baseline and one challenger if resources allow; fixed chunks and lexical; each model with a dense and a hybrid path; time/RAM and errors by direction | Conclusions within the corpus/configurations tried; never "best on the market". If quality is equivalent within the uncertainty, prefer resources within the limits the owner set; do not claim statistical equivalence just because there is no significant difference |
| **RQ4 — optional extension** | How much does adding RLS on top of application filtering change retrieval latency? No speed hypothesis before measuring | The same DB/data/queries/load and indexes, comparing the filter conditions; isolation checked before measuring | Conclude overhead only for the measured environment. Not doing RQ4 does not mean isolation may be dropped; never put an unprotected mode on a public environment |

### 4.1. Separating metrics and avoiding inference beyond the evidence

- **Retrieval:** Recall@5 is computed over the evidence units workstream 2 settles; report both finding at least one piece of evidence and finding all the evidence for multi-passage questions. Workstream 3 settles k/pool and secondary metrics; nDCG/MRR need correct relevance and ranking depth, not just a column name in the harness.
- **Citation:** separate pointing to the right source/location, the source actually supporting the claim (precision), and the claims needing citations having supporting sources (completeness). Citing the right document_id does not prove the answer content is correct.
- **Faithfulness:** whether each claim is supported by the supplied context; evaluated independently of matching the reference answer. A grounded answer that leaves out a condition may still fail the requirement.
- **Refusal:** the retrieval proxy is "the score-based decision to answer", not evidence that the LLM answered wrongly. Separate definitions: false refusal = answerable questions refused / total answerable; false acceptance = unanswerable questions accepted / total unanswerable; coverage = questions accepted / total questions. The real answer risk is computed on labelled outputs, including answerable questions answered wrongly. When a denominator is 0, report not applicable; never assign a 0% error.
- **Resources:** separate one-off corpus embedding, query embedding, retrieval, rerank and generation; warm/cold and cache differ. Offline CPU latency does not prove public warm TTFT meets the NFR.

RRF merges by rank and does not turn scores into a probability of having an answer [S1]. Thresholds are not reused unchanged across dense, hybrid and rerank, or after changing the embedding. "Not found" may be because the corpus has no answer, retrieval missed, a passage was lost when cutting context, or the model generated wrongly; workstreams 5–6 must classify the cause rather than lumping them into one rate.

### 4.2. Conclusion rules before looking at test

1. Workstream 3 must record the primary metric, the practically meaningful difference, the resource constraints and how uncertainty is quantified before test. There is no basis yet to make a 5% gain or a few-second budget an approved standard.
2. Compare paired on the same questions; translated/paraphrased questions or shared sources need dependence handling when splitting and computing uncertainty. Analyses of many models/languages are secondary or need multiple-comparison control; do not cherry-pick favourable results.
3. There are three valid conclusions: supporting the hypothesis within the sample; not supporting it/reversed results; insufficient evidence because of the sample/uncertainty/data gates. No improvement is still a research result if the measurement is valid.
4. Distinguish **an RQ being answered** from **meeting a product target**. The PRD sets Recall@5 ≥ 0.80, citation precision ≥ 0.85, correct refusal on unanswerable ≥ 0.80. These are initial draft targets, not results, not effect sizes, and not enough to accept a system that refuses every question.
5. If targets are adjusted after the baseline, use only the permitted dev/baseline; record the reason and freeze before test. Do not change thresholds/targets after seeing test and then call the old test independent verification.

## 5. Minimal scope and what is not expanded

| Kept in the research core | Kept as system verification requirements | Outside the core / only when conditions allow |
|---|---|---|
| Native EN corpus, VI/EN queries (EN→EN, VI→EN), a fixed corpus and human-reviewed labels; answerable/unanswerable | Workspace filtering and data leak prevention; mappable citations; a really wired pipeline | A VI corpus, EN→VI/VI→VI, other languages, every document type or long multi-turn questions |
| Dense/BM25/hybrid to answer RQ1; one reranker on/off; a refusal threshold with dev/test | Upload/extraction enough to serve the corpus, view sources and rerun experiments | Trying every embedding/reranker, fine-tuning, new fusion algorithms, BGE sparse/ColBERT |
| One embedding control for RQ5 when feasible; measured CPU resources | End-to-end smoke, tracing config/model/version and artifacts | Optimizing providers/free tiers, public deployment, comparing quotas or uptime as a main contribution |
| A fixed answer-level subset and reviewers for RQ2–3 | Tenant isolation is mandatory if a multi-workspace system is claimed | The RQ4 tenant overhead benchmark, large load tests, proving absolute security, product analytics |

**No silent cuts to save CPU:** within the clarified two-direction scope, do not drop the BM25 branch, the unanswerable questions, EN→EN/VI→EN, or keep only questions rerank does well on. The number of models, configuration trials and preselected generation questions per class may be reduced. If answer-level has to be dropped, the output is only retrieval/proxy research; the owner must accept narrowing the RQ2–RQ3 claims and the proposal must be reconciled, without calling the current goal complete.

## 6. CPU feasibility and principled load reduction

Feasible **conditionally**; there is not enough data to promise a completion time or choose a model. Parameter counts or leaderboards do not replace measurements on the owner's CPU. Retrieval needs no generator; generation is a separate binding constraint.

| Component | Cost / unknowns | How to keep the research feasible | Condition to move on |
|---|---|---|---|
| Dense embedding | Depends on CPU, RAM, vector dimension, tokenizer, length, batch and runtime | Embed one model after another; a cache with provenance; shared corpus/chunks | Workstream 5 measures a pilot once workstreams 2–4 meet their gates; estimate full-set time and peak RAM within the budget |
| BM25 + RRF | Usually far less inference cost than transformers, but not measured on this corpus | Use a lexical baseline with a clearly defined tokenizer/scorer; no large fusion matrix | Check the scorer and run artifacts; the runtime `ts_rank` must be separated or brought to parity before system conclusions |
| Rerank | Pairs ≈ queries × candidate pool; long contexts raise cost | One reranker, a fixed pool and a stratified subset if needed; the same candidate IDs on/off | Enough candidate recall and a pilot within budget; report the subset limitation |
| Generation / answer review | Local CPU may be too slow; APIs depend on quota; reviewers take time | One fixed generator on a preselected subset; APIs considered later, not called in this session; human reviewers are the anchor | A permitted generation path and reviewers; otherwise answer-level RQ2–3 are not ready |
| Analysis / reproduction | Not only inference: outputs, config, data and labels must be kept | Prefer paired artifacts and sequential runs; separate cold/warm/cache | Hash/revision/runtime/hardware and run commands; not only the commit when the working tree is dirty |

Relations for workstream 5's estimates: embedding time per model ≈ chunk count / pilot throughput; rerank ≈ queries × pool × average cost per pair (adjusted for batching); generation ≈ subset queries × conditions × time per turn. This is budgeting, **not a benchmark**. Run models sequentially to avoid adding peak RAM; never shrink the test corpus after seeing which model loses.

The proposal expects at least 100 questions, but splitting by dev/test, two query languages and answerability can still make each cell small. 100 is not a guarantee of statistical power; workstream 2 must give the real question count per cell and the review workload, and workstream 3 sets the matching conclusion levels. If there is only one reviewer, record self-review and prioritize some independent checking; do not call those labels two-person agreement.

## 7. Small steps to settle workstream 1

This is a research checklist, not a PLAN/ticket, and does not update the execution counters.

| Step | Work / participants | Depends on | Concrete output | Completion criterion |
|---|---|---|---|---|
| 1. Reconcile commitments | The analyst reads the PRD, the proposal, the handoff and new decisions | Existing documents | The inheritance table in §2 and the RQ map in §4 | Can state what is draft/direction/measured; no inferred approval. Done in this document |
| 2. Settle the problem statement | The owner confirms the SOP subject, VI/EN, one-turn questions and evidence-grounded QA | Step 1 | A scope charter paragraph based on §3 | Has corpus/task/languages, generalization limits and the type of contribution; records the confirmation rather than only a proposal |
| 3. Settle priorities | The owner, with the supervisor if university requirements affect scope | Step 2 | A list of primary/secondary/out-of-scope RQs | RQ1–3 kept or changed with reasons; RQ5 and RQ4 do not accidentally become conditions blocking the whole study |
| 4. Define concepts | Workstream 1 hands over, workstreams 2–3 finish relevance/metrics | Steps 2–3 | A glossary of answerable/evidence/citation/refusal and an RQ→evidence table | Retrieval proxies, citation mapping, faithfulness and answer correctness are not conflated; multiple evidence is handled |
| 5. Confirm resources | The owner provides available CPU/RAM, run hours, deadline, reviewers, corpus source | Step 3 | A resource envelope and the missing list in §8 | Quantitative limits, or explicitly pending; without them, no full model sweep is committed |
| 6. Check data/method feasibility | Workstreams 2–3 respond within scope, without long benchmarks | Steps 4–5 | Expected sample counts per class, usage rights, subset options and decision criteria | Not only smoke; a dev/test and label review plan; identify which scope must narrow before locking test |
| 7. Lock the scope version | The owner reviews the scope charter and the choices in §8 after the feedback round | Step 6 | A decision log: who/when/what/why/what remains open | No conflict remains between the contribution claims and the expected data/resources; PRD/proposal changes are made only when separately requested |

Workstreams 2 and 3 can start surveying from this version with a **provisional** status. Workstream 1 counts as "scope settled" only after step 7; no winning model or benchmark is needed to complete the scope decision.

## 8. Choices for the owner to settle and missing inputs

### 8.1. The choices that really affect scope

| Decision | Recommendation for the owner to consider | If chosen differently | Status |
|---|---|---|---|
| QĐ-01: the research commitment level | Keep RQ1–3, with an answer-level subset for RQ2–3; conclude only for VI/EN queries on the chosen EN SOP corpus | Retrieval-only reduces effort but does not fully answer the proposal/PRD on answers, citations and refusal | Owner agreed 19/10/2026; corpus language clarified later per QĐ-03 |
| QĐ-02: how far to compare embeddings | RQ5 secondary, a baseline + one challenger first; a third model is an extension after the pilot | Three mandatory models increase embedding runs and analysis review; dropping RQ5 leaves no comparative evidence for the dense model choice | Owner agreed 19/10/2026; RQ4 outside the core, isolation still mandatory |
| QĐ-03: application scope and corpus language | A native EN corpus; VI/EN eval queries, two directions EN→EN and VI→EN; no corpus translation. Proposed: a GitLab subset on employee procedures/remote work; Added Bytes as the alternative | Conclusions only support VI/EN queries on an EN corpus; a VI corpus or two-way cross-lingual not evaluated | Owner clarified the language on 19/10/2026; the specific source and topic boundaries are still proposals |
| QĐ-04: the research and answer evaluation budget | A 32 GB RAM machine, no GPU; local + free LLM APIs; prioritize finishing quickly | A small matrix, sequential runs and a short pilot; no promise of time or of specific models running | Direction settled 19/10/2026; no extra run-hour/deadline table required in workstream 1; the generation and review path need checking at execution |

The owner need not decide now on the deployment provider, Java version, thread/batch counts, the full model list, or each k/threshold in workstream 1. Workstreams 3–5 propose those details within the settled limits. RQ4 defaults to an extension under this proposal; the owner only needs to decide more if they want to make it a research goal.

### 8.2. Assumption register and missing inputs

| Code | Working assumption | Input needed / provider | Impact if wrong |
|---|---|---|---|
| A1 | Research/report before deployment; the owner asked on 19/10 to go as fast as possible | No specific deadline yet; use a small scope and reuse existing tooling | Free tiers are not turned into scientific model criteria or an unmeasured completion date |
| A2 | A native EN corpus and a VI/EN question set per the owner's clarification | Workstream 2: check the sources in §8.4, sharing rights, versions, labels and question languages | No VI corpus/translation required; representativeness beyond the chosen source cannot be promised |
| A3 | Keep human reviewers for labels and outputs per QĐ-01 | No reviewer names/review hours yet; workstreams 2–3 propose a small workload, without requiring a schedule to continue surveying | Without reviewers there is no gold/answer-level evidence; self-review by one person must be stated |
| A4 | The owner's machine has 32 GB RAM, no GPU; local runs for retrieval/embedding/rerank per the pilot | Workstream 5 records the CPU, free RAM and pilot time when running; no further detailed budget questions in workstream 1 | 32 GB total is not free RAM or evidence that a specific model runs fast enough |
| A5 | The owner wants to use free LLM APIs together with local runs | The generator details were asked to be skipped; the executing workstream chooses one fixed generator/model and checks the real quota at the start | No provider/quota verified; if the quota runs out, checkpoint and wait, or rerun the affected conditions when the model changes |
| A6 | The owner agreed to QĐ-01–02; the corpus source not yet chosen | The owner asked to skip the question about the proposal's review status; not asked again in this round | Not inferred as PRD/ADR/proposal approved; the unverified parts stay within the report's limits |

### 8.3. Owner decision log, 19/10/2026

Basis: the owner answered "đồng ý 1 và 2" (agree to 1 and 2); had not looked for sources yet, had used the GitLab Handbook before and asked for a recommendation; a local machine with 32 GB RAM and no GPU, combined with free LLM APIs; wants a quick implementation without spending much time; asked to skip items 6–7 of the previous Q&A round (generator details and the proposal).

- **Settled:** RQ1–3 primary, with a human-reviewed answer-level subset; RQ5 secondary with a baseline + one challenger, a third model only as an extension after the pilot; RQ4 outside the core, isolation checks still mandatory.
- **Resource direction settled:** local + free LLM APIs; prioritize reducing data preparation effort and the number of configurations. No further round asking for the CPU model/run hours/deadline as a condition for starting workstreams 2–3.
- **Language clarified next:** the owner asked for the corpus to contain only native EN, adding VI queries to test/eval to verify multilingual queries. Apply EN→EN and VI→EN; drop the earlier proposal's corpus translation/four directions. This narrows the evaluation scope to the owner's goal; it is not cutting experiments after seeing results.
- **Still open:** the specific corpus source and topic boundaries. GitLab/Added Bytes in §8.4 are the agent's recommendation, not a source confirmed by the owner.
- **Moved to execution-time checks:** the available generator and the real review process. The skip request drops the current detailed Q&A round; it does not certify that quota, reviewers or an approved proposal exist. No model/API run or bulk label generation in this update.

### 8.4. Corpus recommendation for a quick implementation

Official sources looked up on 19/10/2026. Recommended: **keep using a subset of the GitLab Handbook**, since the owner already knows the source; narrow it to employee procedures and remote work, rather than collecting the whole handbook or mixing several companies from the start. Proposed starting point: about 20–30 pages/sections with clear procedures, conditions or responsibilities; this number is a data-preparation level for workstream 2 to check, not a guarantee of enough questions or statistical power.

| Source | Content checked | Proposed use / limits |
|---|---|---|
| **GitLab Handbook — preferred** | [Onboarding](https://handbook.gitlab.com/handbook/people-group/general-onboarding/) has roles and steps; [Travel and Expense](https://handbook.gitlab.com/handbook/finance/expenses/) is an operational policy. [Handbook Usage, External use](https://handbook.gitlab.com/handbook/about/handbook-usage/#external-use-of-the-handbook) states the content license is CC BY-SA 4.0 | Choose public pages within the same procedural domain; take the original Markdown, pin a commit/snapshot and keep URLs/sections. Remove unreadable internal links from evidence; check the separate terms of third-party assets. Do not infer the content license from the repo's software LICENSE |
| **Added Bytes — a more compact alternative** | The [home page](https://handbook.addedbytes.com/) lists onboarding, holidays, offboarding, remote/flexible working; publishes CC BY-SA 4.0 except images/logos. Read [Onboarding](https://handbook.addedbytes.com/employment/onboarding) and [Holidays](https://handbook.addedbytes.com/employment/holidays) | Convenient for a handbook with few sections to read/review. The number of possible questions is not inventoried; may be too small for the expected eval set. The source says it derives from GitLab, so the two handbooks are not fully independent domains |

Per the owner's clarification, **load only native EN documents; do not translate the corpus**. Eval questions are written in EN and VI, and same-meaning pairs may be used to compare the effect of query language. Evidence labels for VI questions still point to EN documents/passages; VI reference answers are checked against the same evidence.

Minimum rules when workstream 2 designs the data:

1. Create a manifest for EN documents/versions and same-meaning question groups; split dev/test by content/related-question group, so EN/VI pairs or corresponding paraphrases never fall on two sides.
2. Keep both EN→EN and VI→EN on the same EN corpus and the same access scope for the compared methods. VI questions should be phrased naturally; if translated from EN questions they must be reviewed, keeping the meaning and the conditions to be answered.
3. Keep near-topic answerable and unanswerable questions in both query languages; check unanswerable questions across the whole valid corpus. Do not merely switch a question's language and count it as an independent observation.
4. Report retrieval and answer level separately for EN/VI queries. Finding the right EN passage from a VI query shows VI→EN retrieval ability within the eval set; a conclusion about Vietnamese QA also needs the correctness, grounding and citations of VI outputs to be reviewed. No conclusions for a VI corpus or two-way cross-lingual. The question count and the answer-level subset are proposed by workstreams 2–3 before test, keeping the proposal's expected ≥100 mark as an existing input.

The proposed quick path: one source, a bounded subset, easily obtained text data; local runs for retrieval and the two embeddings sequentially; one reranker; one fixed free API generator for the answer-level subset. No provider comparison or heavy local LLM by default. API availability/quota must be checked at execution; no provider chosen and no time promised. If the generator must change, do not mix outputs from different models into the same comparison as one fixed condition.

## 9. Completion criteria and handover to the following workstreams

### 9.1. Document completion versus a settled study

- [x] Read AGENTS, the handoff, the PRD/RQs/limits and the existing inputs; checked the target file and Git status.
- [x] Recorded the problem, expected contributions, primary/secondary RQs, hypotheses, limits, conclusion rules and CPU risks.
- [x] Separated proposals from source findings, measurements, approvals and technical requirements; listed small steps, outputs and dependencies.
- [x] The owner confirmed QĐ-01–02 on 19/10/2026; recorded in the log in §8.3.
- [x] The owner gave the QĐ-04 direction: 32 GB RAM, no GPU, local + free LLM APIs, prioritize speed; operating details checked at execution.
- [x] The owner clarified QĐ-03 on language: a native EN corpus, VI/EN eval queries; no corpus translation.
- [ ] The owner chooses the specific source and the final scope charter; GitLab/Added Bytes and the topic boundaries in §8.4 are still recommendations.
- [ ] Workstreams 2–3 confirm the corpus/labels/dev-test and methods are enough to verify the RQs within the resources; no output yet.
- [ ] A decision record exists for later workstreams to use as the locked scope; this HANDOFF's `final` does not replace it.

### 9.2. Input/output contract for the following workstreams

| Receiving workstream | Usable from this version | To finish / not to assume |
|---|---|---|
| **2 — dataset** | A native EN SOP corpus; EN/VI queries, two directions EN→EN and VI→EN; answerability by corpus/access, multiple evidence, the proposal's expected ≥100 commitment | A valid corpus and relevance unit; sample counts per class/dev-test, reviewers, same-meaning EN/VI question groups and near-duplicates; no corpus translation, smoke or LLM drafts are not gold |
| **3 — methods/models** | RQ1–3 core, RQ5 secondary, conclusion criteria and the separation of retrieval/answer/resources | The final shortlist, primary/secondary metrics, effect sizes, pool/chunking/instructions, uncertainty, subset; must be settled before test |
| **4 — tooling** | The gaps causing wrong claims: lexical parity, the 512-token cap, revision/cache provenance, reranker injection and the refusal proxy | Check the duplicate relevance in `metrics.py`: DCG currently adds each chunk hitting the same target while the ideal uses the target count; verify nDCG stays within its standard domain and has enough rank depth before use. This is a warning from code reading; no fix or failing test has been run |
| **5 — runs/analysis** | Staged budgets, paired comparisons, negative results allowed, no choices after test | The CPU/RAM pilot, data/tooling gates, stop rules and real measurement artifacts; expected latency is not recorded as a result |
| **6 — validation/report** | Contributions and claim levels, the evidence/citation/refusal rubric, isolation separated from RQ4 | Answer-level human review, system call path/parity, leak tests and the reproduction package; no end-to-end inference from offline retrieval |

## 10. Sources and inference limits

Sources checked on **18/10/2026**. These sources provide the methodological basis; none proves which model/configuration wins on the SOPilot corpus.

- **[S1] Cormack, Clarke and Büttcher (SIGIR 2009), Reciprocal Rank Fusion.** Describes rank fusion and experiments on the authors' IR collections. **Inference for the project:** RRF is a suitable fusion baseline to study complementarity, but the original results do not guarantee VI/EN hybrid will win. [The authors' original paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf).
- **[S2] Thakur et al. (NeurIPS 2021), BEIR.** Evaluates retrieval across many domains, showing BM25 is a strong baseline and reranking has cost trade-offs. **Inference for the project:** the SOP domain must be tested and resources measured rather than choosing by overall leaderboards; BEIR scores are not SOP measurements. [The BEIR paper](https://arxiv.org/abs/2104.08663).
- **[S3] Gao et al. (EMNLP 2023), ALCE.** Evaluates answer generation with citations, distinguishing correctness from citation quality. **Inference for the project:** finding the right source is not enough to confirm answer quality; the VI/EN rubric needs human checkers, without assuming an automatic judge validated for SOPs. [The ALCE paper](https://aclanthology.org/2023.emnlp-main.398/).
- **[S4] Rajpurkar, Jia and Liang (ACL 2018), Know What You Don't Know: Unanswerable Questions for SQuAD.** Adds near-topic unanswerable questions to reading comprehension evaluation. **Inference for the project:** unanswerable questions must be hard enough to avoid merely detecting off-topic ones. SQuAD's setting is reading a given passage, not whole-corpus search; SOPilot must redefine answerability by corpus and access scope. [The SQuAD 2.0 paper](https://aclanthology.org/P18-2124/).

The 18/10 survey only read code/docs and public sources and created the handover file. The 19/10 update recorded the owner's decisions in §8.3 and checked corpus sources in §8.4. No model downloaded/run, no benchmark or full stack run, no keyed API called, `.env` not read, no progress edits, commit/push or deployment. There is no evidence yet to conclude H1–H5 are true, that the system meets the NFRs or that the data has been reviewed; the scope is only partly settled, per the log, and the corpus is not locked.
