# Review UI for V2-19 PDF labels

Local, offline page for the owner review of `datasets/extraction/pilot/annotations.jsonl`.

```powershell
python eval/review_ui/build.py            # writes datasets/extraction/pilot/local/review.html
# open that file in a browser, review, click "Tải file kết quả (.json)"
python eval/review_ui/apply_review.py $HOME\Downloads\annotations.review.json
```

- Left: page images of the labelled pages (link to the source PDF at that page). Right: headings,
  tables, furniture, metadata. Mark each item correct, edited or rejected; edit values in place.
- Progress autosaves in the browser (`localStorage`); export whenever you want a checkpoint.
- `apply_review.py` changes only documents marked finished: rejected items are dropped, the record
  gets `review_status=reviewed`, `reviewer_id`, `reviewed_at`, `label_version`. It keeps a
  timestamped backup of the previous `annotations.jsonl`. Other documents stay `draft`.
- Nothing leaves your machine. The generated page embeds the preview images, so it stays under
  `local/` (git-ignored).
