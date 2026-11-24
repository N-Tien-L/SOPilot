---
id: RESEARCH-V2-19-english-sources-2026-10-20
title: "English sources for the V2-19 extraction corpus"
status: final
created: 2026-10-20
updated: 2026-11-13
author: "Owner"
type: research
scope: tests
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-19-sop-extraction-corpus.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged.

# Recommendation

Prefer EPA LSASD for real PDF SOPs, curl for easy Markdown and plain text, and Kubernetes for structurally complex Markdown. This is a list of candidates checked online on 2026-10-20; no corpus has been downloaded, no extractor run and no gold labels reviewed. V2-19's status is unchanged.

## 1. EPA LSASD: candidate PDF SOPs

The [official catalogue](https://www.epa.gov/quality/quality-system-and-technical-procedures-lsasd-field-branches) collects sampling, field measurement and quality management procedures. Downloaded documents are uncontrolled copies; the source may be updated. The corpus must keep the download date, document code, revision, effective date and SHA-256.

| Candidate | Evidence read from the PDF | Value for V2-19 |
|---|---|---|
| [Soil Sampling PDF](https://www.epa.gov/sites/default/files/2015-06/documents/Soil-Sampling.pdf) | 30 pages; LSASDPROC-300-R5; effective 2023-04-22 | Multi-level numbered headings, TOC, a method summary table, figures, revision history and repeated headers/footers |
| [Field Sampling Quality Control PDF](https://www.epa.gov/sites/default/files/2017-07/documents/field_sampling_quality_control011_af.r5.pdf) | 23 pages; content is LSASDPROC-011-R7; effective 2023-04-22 | Deep headings, metadata, TOC, approval blocks and revision history |

The web parser returned the content and pagination of both PDFs. The bytes need checking with a local parser without OCR to confirm a native text layer; there are no SOPilot extractor quality results yet. Notably, the second PDF's filename has `r5` but the content is `R7`: the revision must be taken from the document. The [QC publication page](https://www.epa.gov/quality/field-sampling-quality-control) also says R7.

Rights: the two files are not labelled `public-domain` or with an open license yet. [EPA Disclaimers](https://www.epa.gov/web-policies-and-procedures/epa-disclaimers) contains language allowing use/distribution for some non-commercial, scientific and educational purposes, but the top of the page says the disclaimers are a catalogue and do not automatically apply to every document. The page also notes individual documents may have their own conditions. Initial recommendation: **manifest + download script**, recording `license_status: needs-document-level-review`; the rights decision must rest on the documents/statements that actually apply. Public access does not mean an open license.

Fallback source: [Document Control](https://www.epa.gov/quality/technical-procedures-laboratory-services-and-applied-science-division-field-quality-system) publishes LSASDDPROC-1000-R3 dated 2024-01-08, but the PDF could not be fetched in this check; not added to the priority set. Some Sediment Sampling URLs returned 502; not used as a byte-verified source.

## 2. curl: Markdown and plain text with a clear license

| Candidate | Actual format | Value |
|---|---|---|
| [docs/INSTALL.md](https://raw.githubusercontent.com/curl/curl/master/docs/INSTALL.md) | Native Markdown, declares `SPDX-License-Identifier: curl` in the file | Many heading levels, lists, code blocks, HTML details; a real installation procedure |
| [RELEASE-NOTES](https://raw.githubusercontent.com/curl/curl/master/RELEASE-NOTES) | Native plain text, the upstream file has no extension | A non-SOP-standard sample: text section labels, lists and statistics; can be saved byte-for-byte as `.txt`, recording the rename, without changing the content |

[COPYING](https://raw.githubusercontent.com/curl/curl/master/COPYING) allows use, copying, modification and distribution, requiring the copyright notice and permission notice to be kept. [REUSE.toml](https://raw.githubusercontent.com/curl/curl/master/REUSE.toml) states that `RELEASE-NOTES` carries the `curl` license. A snapshot can be committed with the notices per the license terms. Pin a specific commit before downloading; `master` is only the discovery path. If the owner requires the upstream file to have a `.txt` extension, RELEASE-NOTES does not meet that narrow condition; do not present it as an original `.txt` file.

## 3. Kubernetes: real-world Markdown with shortcodes

Choose 1–2 files:

- [Safely Drain a Node — raw Markdown](https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/tasks/administer-cluster/safely-drain-node.md): YAML frontmatter, headings, procedure steps, fenced code, Hugo shortcodes and notes.
- [Labels and Selectors — raw Markdown](https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs/concepts/overview/working-with-objects/labels.md): a concept document adding a wiki/docs variant.

The [website repo LICENSE](https://raw.githubusercontent.com/kubernetes/website/main/LICENSE) is CC-BY-4.0. Sharing must keep attribution, the license notice/link and a record of changes. This is the website documentation license, not inferred from the Kubernetes code's Apache license. The [official guide](https://kubernetes.io/docs/contribute/new-content/) confirms the source is written in Markdown and built with Hugo. Pin a commit and keep the source: heading labels must distinguish shortcodes from ordinary headings, rather than silently rendering to HTML and calling that the original Markdown.

## 4. Use in the small set

Start with 2 EPA PDFs + 1 curl MD + 1–2 Kubernetes MD + 1 curl TXT; extend EPA after checking each file. This EN set does not cover Vietnamese ISO 9001, administrative documents, scanned PDFs or Vietnamese-script cases. Do not use many EPA SOPs from the same template as a substitute for structural diversity. Labels must be owner-reviewed; do not treat the TOC as gold labels, because the TOC and the content may differ.
