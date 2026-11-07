"""Merge a downloaded ``annotations.review.json`` into ``annotations.jsonl``.

    python eval/review_ui/apply_review.py path/to/annotations.review.json

Only documents the reviewer marked finished change: rejected items are dropped, edited items keep
the reviewer's values, and the record gets ``review_status=reviewed`` plus reviewer and time. Other
documents stay ``draft``. The previous file is kept as ``annotations.pre-review-<time>.jsonl``.
"""
from __future__ import annotations

import argparse
import json
import sys
import shutil
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "datasets" / "extraction" / "pilot"
REVIEWED_VERSION = "pilot-reviewed-v1"


def say(message: str) -> None:
    sys.stdout.write(message + chr(10))
    sys.stdout.flush()


def _keep(items: list[dict]) -> list[dict]:
    kept = []
    for it in items:
        if it.get("decision") == "reject":
            continue
        kept.append({k: v for k, v in it.items() if k not in ("decision", "added")})
    return kept


def apply(review: dict, annotations: list[dict]) -> tuple[list[dict], list[str]]:
    reviewed_at = review.get("exported_at") or datetime.now(UTC).isoformat()
    done: list[str] = []
    out = []
    for rec in annotations:
        r = review.get("docs", {}).get(rec["doc_id"])
        if not r or not r.get("finished"):
            out.append(rec)
            continue
        new = dict(rec)
        new["headings"] = _keep(r["headings"])
        new["tables"] = _keep(r["tables"])
        new["furniture"] = _keep(r["furniture"])
        new["metadata"] = {} if r.get("metadata_decision") == "reject" else r.get("metadata", {})
        new["cross_references"] = r.get("cross_references", rec.get("cross_references", []))
        new["review_status"] = "reviewed"
        new["reviewer_id"] = review["reviewer_id"]
        new["reviewed_at"] = reviewed_at
        new["label_version"] = REVIEWED_VERSION
        if r.get("notes"):
            new["review_notes"] = r["notes"]
        out.append(new)
        done.append(rec["doc_id"])
    return out, done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("review_json", type=Path)
    ap.add_argument("--pilot", type=Path, default=PILOT)
    args = ap.parse_args()
    review = json.loads(args.review_json.read_text(encoding="utf-8"))
    path = args.pilot / "annotations.jsonl"
    records = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    merged, done = apply(review, records)
    if not done:
        say("No finished documents in the review file; nothing changed.")
        return
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"annotations.pre-review-{stamp}.jsonl")
    shutil.copy2(path, backup)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n",
                    encoding="utf-8")
    say(f"reviewed: {', '.join(done)}\nbackup:   {backup.name}")


if __name__ == "__main__":
    main()
