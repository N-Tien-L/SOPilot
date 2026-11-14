---
id: AUDIT-ingestion-business-cases-2026-10-20
title: "Preliminary survey of SOP import and update business cases before designing ingestion"
status: draft
created: 2026-10-20
updated: 2026-11-13
author: "Owner"
type: audit
scope: ingestion
verdict: needs-user-validation
refs:
  - docs/product/prd-v2-sopilot-mvp.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-19-sop-extraction-corpus.md
  - docs/research/audit-ingestion-sop-data-2026-10-19.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged.

# SOP ingestion business-case survey

> **Note 2026-10-21:** the scope decisions drawn from this survey are now in PRD-V2 (FR-06..FR-09, FR-30, FR-31, UC-12); see [AUDIT-markdown-normalization](audit-markdown-normalization-and-preview-2026-10-21.md). The report body is unchanged; the customer questions in §7 are still unverified.

## 1. Purpose and limits

The owner asked to understand real-world usage before deciding on ingestion optimizations. This is a survey of public documents, not customer interviews or workload measurement. It does not change the PRD, TECH or PLAN, or conclude that incremental ingestion is needed.

There were staged changes in the two TECH-V2 documents and the V2-03 PLAN/ticket when the survey started; this report does not edit those files.

## 2. Evidence read

### S1 — A real procedure in Vietnam

[Vinh University, QT.HCTH.01, issued 20/09/2023](https://vinhuni.edu.vn/upload/files/hcth/quytrinhiso/qt10%20hcth1.pdf), sections 5.1, 5.2.4.4 and 5.2.7.2:

- There are steps for proposal, drafting/editing, checking, approval and distribution.
- Changing the content increments the issue number and updates the change history.
- When a new version is distributed, the old one is withdrawn; copies kept for reference are marked separately.

This is a university's procedure and does not represent every Vietnamese enterprise.

### S2 — A specific operational SOP

[EPA Microbiology Laboratory, ADM-02-05, revised 04-10-13](https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P10106NT.txt), sections 12.1, 12.5–12.7:

- The SOP code expresses identity and revision.
- A revision goes through review/approval before release; the old version is withdrawn from circulation.
- There are cases of withdrawing SOPs no longer used and restoring them with an appropriate revision.

This is one specific laboratory procedure, not data on upload frequency.

### S3 — Quality management guidance

[WHO, Documents and records](https://www.who.int/tools/quality-management-system-for-non-laboratory-settings/pillar-5-documents-and-records): documents must be approved before use, reviewed and updated, and obsolete versions removed from circulation. SOPs and short work instructions are separate document types in the guidance table.

[WHO LQSI, Master SOP](https://extranet.who.int/lqsi/node/75): has an example of an SOP code with a version and distinguishes related documents, forms and appendices.

## 3. Business inferences to verify

In organizations with document control, many draft saves can be distinguished from one official release. If SOPilot only accepts versions allowed into Q&A, the number of ingests may differ greatly from the number of times an author presses Save. There is no evidence yet that target customers work this way.

The size of a change does not decide its importance: changing one deadline or one condition can still change a business answer. The version allowed for use and the citation source need settling before discussing embedding savings.

## 4. Discovery case list

The cases below are survey questions, not behaviour observed at SOPilot customers. S1–S3 support the issue/revise/withdraw lifecycle; the upload operations are product hypotheses.

| Case | Situation to ask about or observe | What to settle with users |
|---|---|---|
| C01 | Loading the current SOP repository for the first time | How many files, pages/file, formats; are old/draft versions mixed in? |
| C02 | Adding a newly issued SOP | Who uploads, and how is the right document confirmed? |
| C03 | Changing one condition, deadline or responsible person | Which version does the new one replace, and when may it be used for answers? |
| C04 | Changing many steps or reorganizing the SOP | Still the same SOP code, or a new document? |
| C05 | Changing only the cover, logo, signatures, review date or layout | Does the issue number increase; how should the file/citation source be updated? |
| C06 | The same release exists as both Word and PDF | Which is the primary source; do both need keeping? |
| C07 | Someone else uploads the same file again, or a retry after a network drop | Point to the existing document or create a new version; do they know the previous attempt succeeded? |
| C08 | Uploading an old version or the wrong document as a replacement by mistake | How do users notice and correct it? |
| C09 | Withdrawing an SOP, or a new version not yet effective | When to stop answering from the old version; is scheduled effectiveness needed? |
| C10 | Forms/appendices changing separately | Managed as independent documents or as part of the SOP? |
| C11 | Changing only category, tags, description or read scope | Is the content file replaced; who may edit? |
| C12 | Many SOPs sharing a template | Are they mistaken for the same document; do managers rely on code, name or content? |

## 5. Information to collect before technical decisions

Interview document keepers and users; ask to see one recent update from the old version to the new one. For each example, record the actor, trigger, input file, code/issue number, effective time and expected outcome. Do not just ask users whether they want a feature.

Collect real numbers: number of current documents, size and page count, number of updates per period, number of concurrent uploaders, acceptable waiting time. Do not infer workload from review cycles prescribed in guidance documents.

V2-19 currently measures extraction structure per file. To survey updates, real old/new version pairs and the reasons for change are needed; this is not yet treated as a change to the approved acceptance criteria. Versions created by deliberately editing files must be labelled synthetic, not presented as real operating history.

## 6. Quotas and reasons to invest in optimization

Quotas can limit a customer's total resources. Paying creates an incentive for reasonable use but does not prove there are no mistaken operations or retries; provider costs also depend on the pricing model and shared resources.

Do not use abuse hypotheses as the default reason to build a complex pipeline. Consider further optimization only when valid cases are confirmed and measurements show waiting time/cost beyond acceptable levels. An embedding cache is already in the V2 design; this report does not assess its effectiveness or propose removing/adding a cache.

## 7. Open questions

1. Who is the first customer group, and who keeps the SOP repository?
2. Does SOPilot accept issued versions, or take part in drafting/editing/approval too?
3. Which parts are mandatory in V2: immediate replacement, effective dates, withdrawal, history or restoration?
4. Which real before/after SOP pairs can be seen, and what are the recent update numbers?

Only turn confirmed conclusions into PRD change proposals before adjusting TECH/tickets. Desk research is not yet enough to settle an ingestion design based on customer workload.

## 8. Multi-scale simulation at the owner's request

The owner asked for a survey across several scales. The numbers below are hypothetical scenarios to test the business logic, not market statistics or benchmarks that have been run. Headcount only describes the context; file counts, lengths and change rates are what directly create ingestion load.

### 8.1 Load phases

1. Initial repository load: choose the current sources, load in one or several batches.
2. Day-to-day operation: add documents, replace versions, edit metadata, withdraw.
3. Concentrated change rounds: opening a department/branch, changing templates, reviewing policies; can be large after onboarding.
4. Exception handling: broken files, mistaken uploads, resends after network drops.

Distinguish processing the new/changed documents within the repository from processing only the changed chunks within one file. These are two different optimization levels; needing the first does not automatically prove the second is needed.

### 8.2 Four hypothetical scenarios

| Scenario | Initial repository | One hypothetical month of operation | Special round | Needs to verify |
|---|---|---|---|---|
| A: individual, 1 person | 20 MD/PDF files, about 100 page-equivalents | Add 2 files, replace 3 files | Move in one more folder of documents | Simple operations, recognizing broken and duplicate files |
| B: wiki team, 10 people | 80 pages/Markdown files, about 240 page-equivalents | Add 4 files, 20 updates across 10 files | Restructuring the wiki, paths or headings of many pages | A published content milestone; how to choose the replaced file; is a source connector really needed? |
| C: Word/PDF enterprise, 80 people | 400 current documents, about 3,200 pages | Add 5 files, replace 8 files | Replacing the logo/template of 100 files | Per-file progress, distinguishing source versions, keeping the usable version when the new one fails |
| D: multi-unit organization, 500 people | 1,500 documents, about 15,000 pages | Add 15 files, replace 30 files | Adding a unit with 200 documents, or mass policy edits | Batched imports, departments/permissions, operating while loading |

Do not use these hypothetical levels for pricing or performance commitments. For B, 20 updates may create 20 ingests if each is published, or fewer if drafts are merged before publication. Debounce, automatic wiki sync, webhooks or folder sync are not assumed to be V2 features.

### 8.3 A concrete walkthrough for C

- Before loading: a manager chooses 400 current documents from the source repository. The source may be larger; choosing current versions is a business step that hashes alone cannot solve.
- First round: send 400 files in several batches. Suppose 390 succeed and 10 fail on format/scans: show the result per file; after fixing, resend only the 10 files. Do not restart the 390 successful files. This is a proposed need, not confirmation that the V2 UI has bulk import.
- The following week: add 2 SOPs, replace 1 SOP changing a deadline from 3 days to 5, edit the tags of 5 documents and withdraw 1 SOP. Only the 3 new file inputs need content processing; tags and withdrawal are management operations. In the current V2, withdrawal may have to be done by deletion; a separate withdrawn status is not settled.
- For the replaced SOP: the old version serves until the new one is processed successfully; whether users want immediate activation or by effective date needs verifying. A technical READY status does not prove the document is in business effect.
- If a 2-page file has an important corrected sentence, answering from the right version takes priority. If reprocessing both pages has an acceptable wait, there is no business reason to build incremental chunking.
- If 100 files only change template, the cost and latency of that round need measuring. Even if the answers stay the same, the new files may shift page positions, so do not assume every old citation position can be reused.

### 8.4 Three kinds of resend to keep apart

| Kind | Meaning | Proposed business outcome to verify |
|---|---|---|
| Resending the same request after a timeout/network error | One operation repeated | Return the previous operation's result/status, avoiding duplicate jobs |
| Creating a new document from an existing file | Possibly a mistake | Report that the document already exists per the in-workspace SHA-256 policy |
| Deliberately replacing a document's version | A new business action | Do not block a meaningful revision just because it is similar; whether an identical upload should create a revision or report "unchanged" needs verifying |

V2-12 currently allows a new version of the same document identical to the old one. This describes the existing scope, not evidence that customers need a revision for every identical upload.

### 8.5 A quantitative example showing the two optimization levels

Suppose the repository has 400 files of 20 chunks each, and a round replaces only 3 files. For illustration, suppose each file still has 20 chunks after re-splitting and the cache is empty for the changed chunks:

- Reloading the whole repository: 8,000 chunks considered, if the pipeline allows that operation.
- Loading only the 3 replaced files: 60 chunks considered; the other 397 files untouched.
- Of the 60 chunks, if measurement shows 54 have the same embedding input/model/revision and are still cached, only 6 new vectors are computed; with no cache hits, 60.

No 90% hit rate is predicted; 54/60 is only an illustrative branch. There are no processing times, costs, RAM or comparisons on real files. Saving at the level of choosing the replaced files is useful even without reusing embeddings within a file.

### 8.6 Comparison with the V2 scope

PRD FR-09 limits each workspace to 50 documents/200 MB by default, configurable. PRD §5 puts bulk import out of scope. So B/C/D are product discovery scenarios; V2 cannot be claimed to handle repository imports at that scale or to have a folder upload button. Raising the quota does not by itself provide a bulk import flow, processing time or machine capacity.

A proposal for the BA to consider next: should V2 let users select multiple files, split batches by quota and see per-file errors? This is the gap between the onboarding needs being surveyed and the current scope, and needs a product decision before TECH is changed.

## 9. Additional sources and remaining gaps

[GitLab, Editing the Handbook](https://handbook.gitlab.com/handbook/about/editing-handbook/) describes how handbook changes are proposed, reviewed and merged; [Handbook Development](https://handbook.gitlab.com/docs/development/) describes the Markdown source. This supports distinguishing commits/draft saves from published content; it does not prove a small team's update rate.

[Microsoft, File share migration](https://learn.microsoft.com/en-us/sharepointmigration/mm-fileshare-copy-to-migrations) describes migration and incremental passes for file shares. This is an example of a repository migration tool with multiple passes, not evidence that SOPilot needs automatic sync or chunk-level updates.

Customer observations, real revision file pairs and measurements on the target machine are still needed. There is no basis yet to settle throughput, new quotas, source connectors or incremental ingestion in the docs.
