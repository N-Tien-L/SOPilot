---
id: RESEARCH-V2-19-CORPUS-SOURCES-2026-10-20
title: "Proposed sources for the V2-19 SOP extraction corpus"
status: final
created: 2026-10-20
updated: 2026-11-13
author: "Owner"
type: research
scope: "V2-19: corpus source selection"
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-19-sop-extraction-corpus.md
  - docs/research/audit-ingestion-sop-data-2026-10-19.md
  - docs/archive/01-requirements/PRD-V2-ingestion-mvp-scope.md
---

> Translated from Vietnamese on 2026-11-13; content unchanged. Agency and document names are given in English; the source links keep the original Vietnamese titles.

# V2-19 corpus sources

## 1. Recommendation

Prefer **ISO PDFs from Vietnamese agencies + EPA SOPs + Markdown with a clear license**. Add real TXT and scanned PDFs for edge cases. Choose documents for structural coverage, not only by topic or count. This is source-selection research; no corpus has been collected or labelled and the ticket is not accepted.

Scope per the current ticket: VI/EN, PDFs with a text layer, MD, TXT; 20–50 files, at least 5 document families, plus 2–3 scanned PDFs to test refusal. DOCX is outside the MVP. This set is separate from RQ1–RQ5 and from the GitLab retrieval corpus designed earlier.

## 2. Vietnamese ISO PDFs: worth taking first

The URLs below were opened as PDFs with the web tool on 20/10/2026 and returned text content. **This does not prove the PDF has a native text layer**, because the web service may process documents before returning results. At acquisition, measure with a local parser without OCR, check Unicode and look at the real page before settling the gold. Page counts below are the PDF page counts reported by the web tool, not the numbers printed in the footer.

| Priority | Document / direct source | PDF pages | Value for the corpus |
|---|---|---:|---|
| A | [Ninh Binh Department of Construction — QT-01 information control](https://soxaydung.ninhbinh.gov.vn/uploads/images/2021/iso/qtcb/qt-01_kiem_soat_thong_tin_lap_van_ban.pdf) | 14 | Multi-level headings; a procedure table with a nested table; header metadata; appendices. |
| A | [Ninh Binh DoC — QT-02 risks and opportunities](https://soxaydung.ninhbinh.gov.vn/uploads/images/2021/iso/qtcb/qt-02_quy_trinh_quan_ly_rui_ro_va_co_hoi.pdf) | 10 | An extra sample from the same agency; pages and table labels need checking at acquisition. |
| A | [Ninh Binh DoC — QT-03 internal audit](https://soxaydung.ninhbinh.gov.vn/uploads/images/2021/iso/qtcb/qt-03__quy_trinh_danh_gia_noi_bo_he_thong_qlcl.pdf) | 13 | Compare with another agency's internal audit SOP. |
| A | [Ninh Binh DoC — QT-04 nonconformity and corrective action](https://soxaydung.ninhbinh.gov.vn/uploads/images/2021/iso/qtcb/qt-04_quy_trinh_kiem_soat_skph_va_hdkp.pdf) | 7 | A shorter sample, reducing the initial labelling effort. |
| A | [Thai Binh Port Authority — QT.01 document control](https://cangvuhanghaithaibinh.gov.vn/images/uploads/attach/QT.01%20Quy%20tr%C3%ACnh%20ki%E1%BB%83m%20so%C3%A1t%20th%C3%B4ng%20tin%20d%E1%BA%A1ng%20v%C4%83n%20b%E1%BA%A3n%20%28t%C3%A0i%20li%E1%BB%87u%2C%20h%E1%BB%93%20s%C6%A1%29%20%28Repaired%29-converted.pdf) | 10 | Table of contents, approval/revision tables, deep headings; contains a passage describing the SOP layout that is easily mistaken for real headings. |
| A | [Thai Binh Port Authority — QT.03 internal audit](https://cangvuhanghaithaibinh.gov.vn/images/uploads/attach/QT.03%20Quy%20tr%C3%ACnh%20%C4%90%C3%A1nh%20gi%C3%A1%20n%E1%BB%99i%20b%E1%BB%99-converted.pdf) | 13 | Adds another template; the same procedure name is not the same file. |
| A | [Thai Binh Port Authority — QT.05 management review](https://cangvuhanghaithaibinh.gov.vn/images/uploads/attach/QT.05%20Quy%20tr%C3%ACnh%20Xem%20x%C3%A9t%20l%C3%A3nh%20%C4%91%E1%BA%A1o-converted.pdf) | 11 | A step table spanning several pages; headers interleaved within the table content; repeated metadata. |
| A | [Ninh Binh Inspectorate — QT 06/TTr organizing an inspection](https://thanhtra.ninhbinh.gov.vn/public/userfiles/3541.pdf) | 17 | A step table and attached forms; distinguishes physical pages from footers like 1/7. |

The [Ninh Binh DoC catalogue page](https://soxaydung.ninhbinh.gov.vn/tieu-chuan-iso/quy-trinh-co-ban-theo-tieu-chuan-iso-90012015-14.html) links the four PDFs above directly. The Port Authority catalogue once returned 503, but the three direct PDFs opened. The Quang Ninh PDFs found through search did not open, so they are only fallback sources, not in the priority list.

**Usage rights:** no redistribution license could be verified for these eight ISO PDFs. Do not label them CC or public domain because of the `.gov.vn` domain. Start with a manifest and download script; usage and file distribution rights must be recorded separately. A manifest/script does not create usage rights if the source is restricted. Do not collect the full text of commercial ISO standards just because an SOP cites them.

## 3. Administrative: Decree 30 is the reference, the right PDF must be chosen

The [Government page for Decree 30/2020/NĐ-CP](https://vanban.chinhphu.vn/default.aspx?docid=199378&pageid=27160) confirms the issue date 05/03/2020 and links the [official digitally signed PDF](https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/03/30.signed.pdf). The web tool opened the 76-page PDF but returned **0 lines of text**. That is not enough evidence to conclude the whole file is a scan, nor can it be placed among the successful text PDFs. A local parser must check each page; if it is pure images, use it as a refusal-test candidate.

The Government page requires attribution when republishing information; this is not a CC statement for every linked asset. Record the source conditions and the specific file's rights at acquisition.

To measure Chapter/Article/Clause (Chương/Điều/Khoản), 2–3 **real text PDFs** containing administrative regulations need to be added; the HTML versions on the legal document portal only help to compare content. Do not print HTML to PDF and call it a real original PDF. Documents need not still be in force to measure layout, but the version/date must be recorded and this corpus must not be used as advice on current regulations.

## 4. English and MD/TXT

See the [EN sources research](research-v2-19-english-sources-2026-10-20.md) for file URLs, license evidence and what has/has not been verified.

- **Real EPA SOPs:** prefer Soil Sampling and Field Sampling Quality Control; use them to measure numbered headings, revision/effective-date metadata and headers/footers. EPA QA/G-6 is a guide to writing SOPs, suitable as a source for label design or as one manual sample; do not replace real SOPs entirely with a guidance document.
- **GitLab Handbook:** fits the employee-operations domain and already has internal research in the [dataset HANDOFF](research-02-dataset-and-labeling.md). Choose a few MD files at a fixed commit; check the content license, includes and frontmatter. If it overlaps the retrieval source, keep separate IDs/manifests and do not merge evaluation results.
- **curl INSTALL.md / Kubernetes task Markdown:** open technical samples adding headings, lists, code and templates. Take only a few, since they do not represent enterprise SOPs. Do not strip shortcodes before measuring and then report that the parser handled shortcodes.
- **curl RELEASE-NOTES:** a natural TXT candidate with a non-standard structure. Keep the original bytes; if renamed to `.txt`, record the operation in the manifest. Do not convert every MD to TXT to inflate the number of independent documents.

EPA is preferred over commercial GMP SOPs at this stage because complete public SOPs and document-control information are available. File-level rights still need checking; do not assume every EPA document is public domain. General layout benchmarks can be consulted later, but do not replace V2-19's Vietnamese SOP coverage.

## 5. Proposed allocation: 24 files

This is a **selection target**, not 24 files already collected or rights-verified.

| Family | Files | Selection condition |
|---|---:|---|
| Vietnamese ISO | 8 | The §2 list; confirm the text layer locally before accepting. |
| VI administrative | 3 | Text PDFs with Chapter/Article/Clause, at least two layouts; files not yet settled. |
| EN EPA SOP | 5 | The first two candidates surveyed; choose three more after checking the real files. |
| Wiki/Markdown | 4 | Prefer two GitLab and two technical samples, avoiding all from one template. |
| Non-standard / TXT | 2 | One technical TXT; one real VI document chosen or permitted by the owner. |
| Scans for refusal | 2 | Confirmed pure-image files; the Decree 30 candidate needs verification. |
| **Total** | **24** | 22 expected successful samples + 2 refusal samples. |

Measure each family rather than only the corpus-wide average. Keep documents from the same template in the same group when splitting dev/holdout to avoid memorizing layouts. Artificially transformed samples (text layer removed, MD→TXT) are allowed as extra fixtures with provenance, not counted as independent real documents to reach 20 files.

## 6. Work needed when implementing the ticket

1. Settle the concrete list and have the owner choose the missing sources; V2-19's status is not changed by this research.
2. Create `datasets/extraction/SOURCES.md`: ID, source/landing/download URL, issuing body, language/family/format, license and evidence URL, redistribution rights, retrieved_at UTC, SHA-256, physical page count, text-layer probe, transformations, owner review status.
3. For web/git: pin a commit or keep a snapshot/hash; an access date and a dynamic branch URL are not enough to reproduce. For PDFs: keep the byte hash, and do not take the filename as the revision.
4. Assign gold from the original pages viewed: headings with level/order; tables with position/columns; boilerplate to remove; metadata with evidence. Distinguish the issue date from the effective date; do not fill the effective date just because there is a date in the header.
5. For scans, the gold is the refusal decision and its reason. Do not count a scan's heading/table F1 of 0 towards text PDF processing quality.
6. The owner reviews each label per the acceptance criteria. This research has no gold labels, parser benchmark or V2-19 acceptance evidence.

## 7. Verification limits

Read the ticket, the MVP scope and the related audit; opened the official sources above on the web. No bytes downloaded into the corpus, no parser run without OCR, ISO PDF layouts not verified with page images, per-PDF usage rights not settled, the administrative/VI TXT/scan files not all chosen. The ISO layout observations rely on the per-page web content and need visual confirmation before labelling. No ticket/PLAN or files with the owner's pending changes were edited. No build/test run because only a research report was added.
