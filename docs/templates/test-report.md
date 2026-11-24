---
id: TEST-REPORT-NNN
title: "<Scope> test report YYYY-MM-DD"
status: final # draft | final
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: "Owner"
verdict: PASSED # PASSED | FAILED | PASSED_WITH_WARNINGS
refs: [] # ticket / test plan
evidence: "" # artifacts/testing/<run-id>/ (gitignored); empty if none
---

# TEST-REPORT-NNN: <Title>

## Scope

## Environment
Date, branch and commit (`git rev-parse --short HEAD`), OS, Docker yes/no, provider endpoints used.

## Executed
| Command / suite | Result (quote the summary line) |
|---|---|

## Not executed
Each skipped suite with its reason (for example "Docker unavailable"). Never report an unrun suite as passed.

## Browser verification
"Not performed" unless it was. If it was: the tool used and the screenshot paths under `evidence`.

## Findings and limitations
