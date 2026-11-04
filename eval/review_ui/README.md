# Review app for V2-06 and V2-19

Local app (Python stdlib, `127.0.0.1` only) for the owner review of
`eval/datasets/sop-main` (V2-06 questions/evidence; the pilot is its dev split; `--v206` picks another dataset) and `datasets/extraction/pilot`
(V2-19 PDF structure labels).

```powershell
eval/.venv/Scripts/python.exe eval/review_ui/server.py    # opens http://127.0.0.1:8765
```

Every decision is written straight to the dataset files; there is no export/import step. The
first write to a file in a session keeps a copy in that dataset's git-ignored `local/backups/`.
Both validators run after each write; the header shows "cấu trúc" (structure) and
"gate --require-reviewed". The reviewer name (top right) becomes `reviewer_id`.

## V2-06 (one intent = VI + EN question)

- Middle: evidence sets (OR between sets, AND inside one), then each question with its question,
  reference answer, `query_types`, review note and **Duyệt / Loại / Về nháp**.
- Right: canonical text with the spans highlighted and the PDF page image underneath (the image
  follows the page you scroll to). Select text to replace a span, add it to a set or start a new
  OR set; offsets, `quote_sha`, `pages` and `expected` are recomputed.
- Search box (`/`) searches every corpus document; for negative questions "Tìm các từ này" counts
  the audit terms. Approving a negative writes `unanswerable_audit` (`candidate_sections` is
  counted by the server).
- Approve writes `review_status=reviewed` plus one matching `review.jsonl` record. Exclude moves
  the question to `questions.excluded.jsonl` (restorable). Editing a reviewed question or its
  spans puts it back to `draft`.
- Keys: `J`/`K` next/previous intent, `A` approve both questions of the intent.

## V2-19 (one PDF at a time)

- Left: page image (or the Markdown file); right: labels on that page (headings, tables with
  merged cells, furniture, cross references), document metadata and the delegate's
  `review_notes` with "KHÔNG CHẮC" highlighted.
- Each label: ✓ correct, ✎ edit, ✗ wrong; "+ thêm" adds a missing label on the current page.
  `Enter` marks the page checked (unmarked labels count as correct) and moves to the next page;
  `←`/`→` browse.
- Progress autosaves to `datasets/extraction/pilot/local/owner-review.draft.json`.
- "Hoàn tất file" (after every page is checked) rewrites that record in `annotations.jsonl`:
  rejected labels dropped, edits/additions kept, `reviewer_id` = you, previous delegate kept in
  `delegated_reviewer_id`/`delegated_reviewed_at`, `owner_confirmed=full_document`,
  `owner_review_changes` counts.

Test on a copy with `--v206 <dir> --v219 <dir> --no-browser --port <n>`.

The older static page (`build.py`, `template.html`, `apply_review.py`) covered only the earlier
page-limited V2-19 labels and is superseded by `server.py`.
