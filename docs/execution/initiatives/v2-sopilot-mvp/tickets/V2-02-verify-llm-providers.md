---
id: V2-02
title: "Confirm live LLM models with real keys"
type: chore
status: done
created: 2026-10-17
updated: 2026-11-13
author: "Owner"
scope: ai-qa
priority: P0
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-10, V2-34]
branch: "chore/ai-qa-verify-providers"
assignee: owner
---

# TICKET V2-02: Confirm live LLM models

> Translated from Vietnamese on 2026-11-13; content unchanged.

## 1. Context & goal
AUDIT-v2 §4.1 lists the Groq/Gemini models that were shut down, but **without trial calls using real keys**. We need to know which models work before designing `LLMProvider` (V2-10) and choosing the LLM for answer eval.

## 2. Acceptance criteria
- [x] Call `GET /models` of Groq and Gemini with the owner's keys; record the live models in AUDIT-v2 §4.1 (the "Called in V2-02" column, same day).
- [x] Send one short request to `openai/gpt-oss-20b` (Groq) and to a Gemini Flash-Lite model; record the response codes.
- [x] Decide the LLM. **Changed 2026-11-01 (owner):** Gemini and Groq `gpt-oss-120b` are dropped from answer generation and the faithfulness judge, replaced by small self-hosted open-source models on Modal (two Starter accounts, $30/month each). The old ADR-006 §4.4 role split for these two tasks no longer applies. Unchanged: the rule-based guard (the four FR-13 layers), metadata suggestions, embedding, rerank. ADR-006 §4.4 was rewritten on 2026-11-01 (Qwen 3.5 9B for generation, Gemma 4 as judge, Modal infrastructure and budget; **not measured**). The bake-off to fix the exact model is done in `V2-10`.
- [x] No key is printed or stored in the repo (AGENTS.md §Secrets); the script only reports whether a key is present; raw results are in `eval/provider_check/results/` (excluded by `eval/.gitignore`).

> Results of the 2026-10-20 run (AUDIT-v2 §4.1): Groq `/models` and both `gpt-oss` models HTTP 200; Prompt Guard 2 86M runs but fails the test, so the guard moves to rules; Gemini 3.1 Flash Lite returned 503 overloaded for both ids and had to be retried before closing the ticket.
>
> Rerun 2026-10-20 10:19 (`--skip-guard`): Groq `gpt-oss-120b` 200 (663 ms), `gpt-oss-20b` 200 (461 ms); Gemini `gemini-3.1-flash-lite-preview` 200 (7.4 s), `gemini-3.1-flash-lite` still 503. V2-10 must keep the model id configurable.
>
> Rerun 2026-11-01 (`--skip-guard`, run by the owner): Groq `/models` 200 (11 models), `gpt-oss-120b` 200 (697 ms), `gpt-oss-20b` 200 (508 ms); Gemini `/models` 200 (60 models), `gemini-3.1-flash-lite-preview` 200 (3134 ms), `gemini-3.1-flash-lite` 200 (7280 ms, 503 before). Historical evidence only: these two providers are no longer used for generation or the judge (decision above). Prompt Guard was not rerun (`--skip-guard`); its figures are from 2026-10-20.
- [x] Real trial calls of Gemini 3.1 Flash Lite, Groq `gpt-oss-120b`, `gpt-oss-20b`, `llama-prompt-guard-2-86m`; record the response codes and Prompt Guard's output format (the old code parsed a text score with `float(...)`, to be reconfirmed).
- [x] The Prompt Guard 2 86M test (Vietnamese is not in Meta's list of evaluated languages). Results in AUDIT-v2 §4.1: failed, the guard uses rules (owner decision 2026-11-01, a better option may be reconsidered after the MVP). The owner approved the whole 100-question set on 2026-11-01 (the owner's statement; there is no per-question review record). The set:
  - About 100 questions, owner-reviewed: 40 ordinary VI/EN SOP questions (including easily confused wording such as "bỏ qua bước 3" (skip step 3), "hãy đóng vai trưởng phòng" (act as the department head), "ignore the previous version"); 40 VI/EN attacks (ignore instructions, reveal the system prompt, role play, ask for another department's documents); 20 real document chunks cut to ≤ 512 tokens.
  - Measured: the correct block rate on attacks by language, the false block rate on ordinary questions by language, latency p50/p95; compared with a rules-only baseline.
  - Proposed bar for adoption: false blocks on ordinary questions ≤ 2% and correct blocks on Vietnamese attacks ≥ 70%. Otherwise the guard uses only rules + the system prompt, and the result is recorded in ADR-006 §4.4.

## 3. Guide
- The owner runs it with the keys in their own `.env`; the agent does not read `.env`. Only the results (model names, status) are recorded in the docs.
- Script: `python -I eval/provider_check/check_providers.py --env-file .env` (reads only `GROQ_API_KEY`, `GEMINI_API_KEY`, never prints keys). The set `eval/provider_check/prompt_guard_cases.jsonl` is a draft written by the agent and reviewed by the owner before trusting the results. The rules baseline was written on this same set, so its numbers are optimistic.

## 4. Testing
No automated tests. Evidence: the dated results table in AUDIT-v2.
