"""Local review app for V2-06 (questions/evidence) and V2-19 (PDF structure labels).

    eval/.venv/Scripts/python.exe eval/review_ui/server.py          # opens http://127.0.0.1:8765

Stdlib only; binds to 127.0.0.1. Every decision is written straight to the dataset files
(no export/import step). The first write to a file in a session keeps a copy under the
dataset's git-ignored ``local/backups/``. Validators run after each write and the result is
shown in the page.

V2-06 (eval/datasets/sop-main; the pilot is its dev split):
  * approve  -> question ``review_status=reviewed`` + one matching record in ``review.jsonl``
    (negatives also carry ``unanswerable_audit``)
  * exclude  -> question moves to ``questions.excluded.jsonl`` (restorable)
  * edits to question/answer/query_types/evidence reset a reviewed question to ``draft``
  * span edits recompute ``quote``, ``quote_sha`` and ``pages``; ``expected`` is re-derived
V2-19 (datasets/extraction/pilot):
  * work-in-progress decisions autosave to ``local/owner-review.draft.json``
  * "finish document" rewrites that record in ``annotations.jsonl``: rejected items dropped,
    edits/additions kept, ``reviewer_id`` = owner, previous delegate kept in
    ``delegated_reviewer_id``, ``owner_confirmed=full_document``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import shutil
import sys
import threading
import traceback
import webbrowser
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "eval"))

from sopilot_eval.dataset import project_expected, validate_retrieval
from sopilot_eval.extraction import validate_extraction

V206 = ROOT / "eval" / "datasets" / "sop-main"
V219 = ROOT / "datasets" / "extraction" / "pilot"
PREVIEWS = V219 / "local" / "previews"
LOCK = threading.Lock()
_BACKED_UP: set[Path] = set()
SESSION = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(x)
        for x in path.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]


def backup(path: Path, dataset: Path) -> None:
    if path in _BACKED_UP or not path.exists():
        return
    dest = dataset / "local" / "backups"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest / f"{path.stem}.{SESSION}{path.suffix}")
    _BACKED_UP.add(path)


def write_text(path: Path, text: str, dataset: Path) -> None:
    backup(path, dataset)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


def write_jsonl(path: Path, rows: list[dict], dataset: Path) -> None:
    write_text(
        path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), dataset
    )


def write_json(path: Path, data, dataset: Path) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", dataset)


def run_check(fn) -> dict:
    try:
        fn()
        return {"ok": True}
    except (ValueError, TypeError, KeyError, OSError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def preview_pages(doc_id: str) -> list[int]:
    pages = []
    for img in PREVIEWS.glob(f"{doc_id}-p*.png"):
        tail = img.stem.removeprefix(f"{doc_id}-p")
        if tail.isdigit():
            pages.append(int(tail))
    return sorted(pages)


# --------------------------------------------------------------------------- V2-06


class V206Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.f_questions = root / "questions.master.jsonl"
        self.f_excluded = root / "questions.excluded.jsonl"
        self.f_evidence = root / "evidence.jsonl"
        self.f_review = root / "review.jsonl"

    def load(self):
        manifest = read_json(self.root / "manifest.json")
        docs = {d["doc_id"]: d for d in manifest["documents"]}
        texts = {}
        for d in manifest["documents"]:
            p = self.root / d["path"]
            texts[d["doc_id"]] = p.read_bytes().decode("utf-8") if p.exists() else None
        return manifest, docs, texts

    def state(self) -> dict:
        manifest, docs, texts = self.load()
        return {
            "manifest": manifest,
            "texts": texts,
            "page_map": read_json(self.root / "page-map.json", {}),
            "previews": {d: preview_pages(d) for d in docs},
            "spans": read_jsonl(self.f_evidence),
            "questions": read_jsonl(self.f_questions),
            "excluded": read_jsonl(self.f_excluded),
            "reviews": read_jsonl(self.f_review),
            "negative_audit": read_jsonl(self.root / "negative-audit.draft.jsonl"),
            "validation": self.validation(),
        }

    def validation(self) -> dict:
        return {
            "structure": run_check(lambda: validate_retrieval(self.root)),
            "gate": run_check(
                lambda: validate_retrieval(self.root, require_reviewed=True)
            ),
        }

    # helpers ---------------------------------------------------------------
    def _rederive(self, questions: list[dict]) -> None:
        _, docs, _ = self.load()
        spans = {s["span_id"]: s for s in read_jsonl(self.f_evidence)}
        for q in questions:
            if "expected" in q and all(
                sid in spans for es in q["evidence_sets"] for sid in es
            ):
                q["expected"] = project_expected(q, spans, docs)

    def _reset(self, q: dict, reviews: list[dict]) -> list[dict]:
        if q.get("review_status") in {"reviewed", "adjudicated"}:
            q["review_status"] = "draft"
        return [r for r in reviews if r.get("question_id") != q["id"]]

    def _save(self, questions, reviews=None) -> None:
        self._rederive(questions)
        write_jsonl(self.f_questions, questions, self.root)
        if reviews is not None:
            write_jsonl(self.f_review, reviews, self.root)

    # actions ---------------------------------------------------------------
    def patch_question(self, body: dict) -> None:
        allowed = {"question", "reference_answer", "query_types"}
        questions, reviews = read_jsonl(self.f_questions), read_jsonl(self.f_review)
        q = next(q for q in questions if q["id"] == body["id"])
        changed = False
        for k, v in body["patch"].items():
            if k in allowed and q.get(k) != v:
                q[k] = v
                changed = True
        if changed:
            reviews = self._reset(q, reviews)
            self._save(questions, reviews)

    def set_evidence(self, body: dict) -> None:
        spans = {s["span_id"] for s in read_jsonl(self.f_evidence)}
        sets = [[sid for sid in es if sid] for es in body["evidence_sets"]]
        sets = [es for es in sets if es]
        for es in sets:
            for sid in es:
                if sid not in spans:
                    raise ValueError(f"unknown span {sid}")
        questions, reviews = read_jsonl(self.f_questions), read_jsonl(self.f_review)
        for q in questions:
            if q["id"] in body["ids"] and q["evidence_sets"] != sets:
                q["evidence_sets"] = sets
                reviews = self._reset(q, reviews)
        self._save(questions, reviews)

    def upsert_span(self, body: dict) -> dict:
        _, docs, texts = self.load()
        doc_id = body["doc_id"]
        if doc_id not in docs or texts.get(doc_id) is None:
            raise ValueError("unknown or missing document")
        text = texts[doc_id]
        start, end = int(body["start"]), int(body["end"])
        if not 0 <= start < end <= len(text):
            raise ValueError("offset out of range")
        quote = text[start:end]
        if body.get("quote") is not None and body["quote"] != quote:
            raise ValueError(
                "selected text does not match canonical text at these offsets"
            )
        if quote != quote.strip():
            raise ValueError("span must not start/end with whitespace")
        pmap = read_json(self.root / "page-map.json", {}).get(doc_id)
        spans = read_jsonl(self.f_evidence)
        sid = body["span_id"].strip()
        existing = next((s for s in spans if s["span_id"] == sid), None)
        if body.get("create") and existing:
            raise ValueError(f"span id already exists: {sid}")
        if not body.get("create") and not existing:
            raise ValueError(f"unknown span: {sid}")
        row = existing if existing else {"span_id": sid}
        if existing and existing["doc_id"] != doc_id:
            raise ValueError("cannot move a span to another document")
        row.update(
            {
                "doc_id": doc_id,
                "section_id": body.get("section_id")
                or row.get("section_id")
                or "manual",
                "start_char": start,
                "end_char": end,
                "quote": quote,
                "quote_sha": sha256(quote),
            }
        )
        if pmap:
            row["pages"] = [
                p["page"]
                for p in pmap
                if p["end_char"] > start and p["start_char"] < end
            ]
        if not existing:
            spans.append(row)
        write_jsonl(self.f_evidence, spans, self.root)
        questions, reviews = read_jsonl(self.f_questions), read_jsonl(self.f_review)
        for q in questions:
            if any(sid in es for es in q["evidence_sets"]):
                reviews = self._reset(q, reviews)
        self._save(questions, reviews)
        return row

    def decide(self, body: dict) -> None:
        manifest, _, texts = self.load()
        questions, reviews = read_jsonl(self.f_questions), read_jsonl(self.f_review)
        q = next(q for q in questions if q["id"] == body["id"])
        decision = body["decision"]
        reviewer = (body.get("reviewer_id") or "").strip()
        reviews = [r for r in reviews if r.get("question_id") != q["id"]]
        if decision == "draft":
            q["review_status"] = "draft"
        elif decision == "reviewed":
            if not reviewer:
                raise ValueError("reviewer_id is required")
            record = {
                "question_id": q["id"],
                "decision": "reviewed",
                "reviewer_id": reviewer,
                "reviewed_at": now(),
                "notes": (body.get("notes") or "").strip() or "Đồng ý, không sửa.",
                "label_version": q["label_version"],
                "corpus_version": manifest["corpus_version"],
            }
            if not q["answerable"]:
                audit = body.get("unanswerable_audit") or {}
                terms = [t.strip() for t in audit.get("search_terms", []) if t.strip()]
                if not terms or not (audit.get("reason") or "").strip():
                    raise ValueError(
                        "negative question needs audit reason and search terms"
                    )
                record["unanswerable_audit"] = {
                    "reason": audit["reason"].strip(),
                    "search_terms": terms,
                    "candidate_sections": {
                        d: {
                            t: n
                            for t in terms
                            if (n := (texts[d] or "").casefold().count(t.casefold()))
                        }
                        for d in texts
                    },
                    "conclusion": (audit.get("conclusion") or "").strip()
                    or "unanswerable_in_pilot_corpus_human_checked",
                    "scope_documents": sorted(texts),
                }
            reviews.append(record)
            q["review_status"] = "reviewed"
        elif decision == "excluded":
            excluded = read_jsonl(self.f_excluded)
            questions = [x for x in questions if x["id"] != q["id"]]
            excluded = [x for x in excluded if x["id"] != q["id"]]
            q = dict(q)
            q["review_status"] = "excluded"
            q["excluded_by"] = reviewer or "owner"
            q["excluded_at"] = now()
            q["exclude_note"] = (body.get("notes") or "").strip()
            excluded.append(q)
            write_jsonl(self.f_excluded, excluded, self.root)
        else:
            raise ValueError("unknown decision")
        self._save(questions, reviews)

    def restore(self, body: dict) -> None:
        excluded = read_jsonl(self.f_excluded)
        q = next(x for x in excluded if x["id"] == body["id"])
        for k in ("excluded_by", "excluded_at", "exclude_note"):
            q.pop(k, None)
        q["review_status"] = "draft"
        questions = read_jsonl(self.f_questions)
        questions.append(q)
        write_jsonl(
            self.f_excluded, [x for x in excluded if x["id"] != q["id"]], self.root
        )
        self._save(questions)

    def search(self, term: str) -> list[dict]:
        _, _, texts = self.load()
        term = term.strip()
        hits = []
        if len(term) < 2:
            return hits
        low = term.casefold()
        for doc_id, text in texts.items():
            if text is None:
                continue
            folded = text.casefold()
            pos = folded.find(low)
            while pos != -1 and len(hits) < 200:
                a, b = max(0, pos - 90), min(len(text), pos + len(term) + 90)
                hits.append(
                    {
                        "doc_id": doc_id,
                        "start": pos,
                        "end": pos + len(term),
                        "before": text[a:pos],
                        "match": text[pos : pos + len(term)],
                        "after": text[pos + len(term) : b],
                    }
                )
                pos = folded.find(low, pos + 1)
        return hits


# --------------------------------------------------------------------------- V2-19

ITEM_KINDS = ("headings", "tables", "furniture", "cross_references")


class V219Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.f_ann = root / "annotations.jsonl"
        self.f_draft = root / "local" / "owner-review.draft.json"

    def state(self) -> dict:
        manifest = read_json(self.root / "manifest.json")
        md = {}
        for d in manifest["documents"]:
            p = self.root / d["path"]
            if p.suffix == ".md" and p.exists():
                md[d["doc_id"]] = p.read_text(encoding="utf-8")
        return {
            "manifest": manifest,
            "annotations": read_jsonl(self.f_ann),
            "previews": {
                d["doc_id"]: preview_pages(d["doc_id"]) for d in manifest["documents"]
            },
            "markdown": md,
            "drafts": read_json(self.f_draft, {}),
            "validation": {
                "structure": run_check(lambda: validate_extraction(self.root)),
                "gate": run_check(lambda: validate_extraction(self.root, True)),
            },
        }

    def save_draft(self, body: dict) -> None:
        drafts = read_json(self.f_draft, {})
        if body.get("draft") is None:
            drafts.pop(body["doc_id"], None)
        else:
            drafts[body["doc_id"]] = body["draft"]
        self.f_draft.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.f_draft.with_suffix(".tmp")
        tmp.write_text(json.dumps(drafts, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.f_draft)

    def finish(self, body: dict) -> None:
        reviewer = (body.get("reviewer_id") or "").strip()
        if not reviewer:
            raise ValueError("reviewer_id is required")
        drafts = read_json(self.f_draft, {})
        draft = drafts.get(body["doc_id"])
        if not draft:
            raise ValueError("no draft for this document")
        rows = read_jsonl(self.f_ann)
        rec = next(r for r in rows if r["doc_id"] == body["doc_id"])
        counts = {"rejected": 0, "edited": 0, "added": 0, "kept": 0}
        for kind in ITEM_KINDS:
            kept = []
            for it in draft["items"].get(kind, []):
                d = it.get("_d")
                if d == "reject":
                    if not it.get("_added"):
                        counts["rejected"] += 1
                    continue
                if it.get("_added"):
                    counts["added"] += 1
                elif d == "edit":
                    counts["edited"] += 1
                else:
                    counts["kept"] += 1
                kept.append({k: v for k, v in it.items() if not k.startswith("_")})
            rec[kind] = kept
        if draft.get("metadata_d") == "reject":
            rec["metadata"] = {}
        else:
            rec["metadata"] = {
                k: v for k, v in (draft.get("metadata") or {}).items() if k and v
            }
        prev = rec.get("reviewer_id")
        if prev and prev != reviewer and "delegated_reviewer_id" not in rec:
            rec["delegated_reviewer_id"] = prev
            rec["delegated_reviewed_at"] = rec.get("reviewed_at")
        rec["review_status"] = "reviewed"
        rec["reviewer_id"] = reviewer
        rec["reviewed_at"] = now()
        rec["owner_confirmed"] = "full_document"
        rec["owner_review_changes"] = counts
        notes = (body.get("notes") or "").strip()
        if notes:
            rec["owner_review_notes"] = notes
        else:
            rec.pop("owner_review_notes", None)
        write_jsonl(self.f_ann, rows, self.root)
        self.save_draft({"doc_id": body["doc_id"], "draft": None})


# --------------------------------------------------------------------------- HTTP

S206, S219 = V206Store(V206), V219Store(V219)
V219_ROOT = V219


class Handler(BaseHTTPRequestHandler):
    server_version = "SOPilotReview/1"

    def log_message(self, fmt, *args):  # keep the console quiet
        return

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(
            status,
            json.dumps(data, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send(200, path.read_bytes(), ctype)

    def do_GET(self):
        url = urlparse(self.path)
        parts = [unquote(p) for p in url.path.strip("/").split("/") if p]
        try:
            if not parts:
                self._file(HERE / "app.html")
            elif parts == ["api", "v206"]:
                with LOCK:
                    self._json(S206.state())
            elif parts == ["api", "v219"]:
                with LOCK:
                    self._json(S219.state())
            elif parts == ["api", "v206", "search"]:
                self._json(S206.search(parse_qs(url.query).get("q", [""])[0]))
            elif len(parts) == 3 and parts[0] == "img":
                doc, page = parts[1], parts[2]
                if not doc.replace("-", "").isalnum() or not page.isdigit():
                    raise ValueError("bad image path")
                self._file(PREVIEWS / f"{doc}-p{int(page)}.png")
            elif len(parts) == 2 and parts[0] == "pdf":
                doc = parts[1].removesuffix(".pdf")
                if not doc.replace("-", "").isalnum():
                    raise ValueError("bad pdf path")
                self._file(V219_ROOT / "local" / "corpus" / f"{doc}.pdf")
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as exc:  # noqa: BLE001 - report any failure to the page
            self._json({"error": str(exc)}, 400)

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        routes = {
            "/api/v206/question": S206.patch_question,
            "/api/v206/evidence": S206.set_evidence,
            "/api/v206/span": S206.upsert_span,
            "/api/v206/decide": S206.decide,
            "/api/v206/restore": S206.restore,
            "/api/v219/draft": S219.save_draft,
            "/api/v219/finish": S219.finish,
        }
        fn = routes.get(url.path)
        if not fn:
            self._json({"error": "not found"}, 404)
            return
        try:
            with LOCK:
                result = fn(body)
                payload = {"ok": True, "result": result}
                if url.path.startswith("/api/v206"):
                    payload["validation"] = S206.validation()
                elif url.path == "/api/v219/finish":
                    payload["state"] = S219.state()
            self._json(payload)
        except StopIteration:
            self._json({"error": "unknown id"}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001 - report any failure to the page
            sys.stderr.write(traceback.format_exc())
            self._json({"error": f"{exc}"}, HTTPStatus.BAD_REQUEST)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument(
        "--v206",
        type=Path,
        default=V206,
        help="V2-06 dataset root (for testing on a copy)",
    )
    ap.add_argument(
        "--v219",
        type=Path,
        default=V219,
        help="V2-19 dataset root (for testing on a copy)",
    )
    args = ap.parse_args()
    global S206, S219, PREVIEWS, V219_ROOT
    S206, S219 = V206Store(args.v206.resolve()), V219Store(args.v219.resolve())
    V219_ROOT = args.v219.resolve()
    PREVIEWS = V219_ROOT / "local" / "previews"
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    sys.stdout.write(f"SOPilot review: {url}  (Ctrl+C to stop)\n")
    sys.stdout.flush()
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
