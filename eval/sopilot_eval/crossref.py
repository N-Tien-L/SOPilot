"""V2-19: count cross-references over the whole extraction corpus (TECH-V2-ai-service §6.4a).

    python -m sopilot_eval.crossref --dataset ../datasets/extraction/pilot --out results/crossref.json

Reads the text layer (pypdf for PDF, raw text for Markdown), removes the labelled furniture
lines so a repeated header such as "SOP Number: 21301" is not counted on every page, and counts
regex candidates:

* ``within_document``: forms/annexes of the document itself (BM-01-02 inside QT-01),
  "mục 5.3", "Điều 12", "khoản 2", "section 5.13", "Step 5.1", "bước 3",
  "Phụ lục 1", "Attachment 1", "Appendix A", "Chương II"
* ``between_documents``: document codes (QT-05, BM-01-02, SOP 21918, ORA-LAB.5.8), legal
  instruments (Nghị định 30/2020/NĐ-CP, Thông tư, Quyết định, Luật), standards (ISO 9001,
  TCVN ISO 9001:2015) and US regulations (21 CFR 211.101)

A between-document candidate counts as ``in_corpus`` when its normalized code matches the
``doc_code`` of another labelled document or a known alias of one. Candidates are not adjudicated
labels: the report also lists the labelled reference counts so the regex can be judged against
them. Scan documents without a text layer contribute no text and are listed separately.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from .dataset import read_jsonl

ROMAN = r"(?:[IVXLC]+)"
WITHIN = re.compile(
    r"\b(?:"
    r"(?:mục|tiểu mục|điểm)\s+\d+(?:\.\d+)*"
    r"|(?:điều|khoản)\s+\d+"
    r"|chương\s+" + ROMAN + r"\b"
    r"|(?:phụ lục|biểu mẫu số)\s+(?:\d+|" + ROMAN + r")\b"
    r"|bước\s+\d+"
    r"|(?:section|sections|step|steps|paragraph|clause)\s+\d+(?:\.\d+)*"
    r"|(?:attachment|appendix|annex|exhibit)\s+(?:\d+|[A-Z])\b"
    r")",
    re.IGNORECASE,
)
CODE = (
    r"BM\.(?:QT|HD)\.\d+(?:\.\d+)*"  # BM.QT.03.01
    r"|(?:QT|BM|HD|HDCV|PL)[ .\-–]?\d+(?:[.\-–]\d+)*(?:/[A-Za-z]+)?"  # QT-05, BM-01-02, QT 06/TTr
    r"|SOP[ \-]?\d{3,}"  # SOP 21918, SOP-000285
    r"|[A-Z]{3,}(?:PROC|FORM|GUID)-\d+(?:-R\d+)?"  # LSASDPROC-206, SESDFORM-011
    r"|[A-Z]{2,5}-[A-Z]{2,5}\.\d+(?:\.\d+)*"  # ORA-LAB.5.8
)
# Vietnamese instruments are matched case-sensitively so "luật hiện hành" is not a reference.
LEGAL = (
    r"(?:(?:Nghị định|Thông tư|Quyết định|Nghị quyết|Chỉ thị|Pháp lệnh|Công văn|Thông báo)\s+(?:số\s+)?)?"
    r"\d+/(?:\d{4}/)?(?:NĐ|TT|QĐ|NQ|CT|PL|TB|VBHN|VPCP|UBTVQH)[A-Za-zĐđ0-9\-]*"
    r"|Luật\s+[A-ZĐ]\w*(?:\s+\w+){0,3}?(?=\s+(?:số|năm|ngày)\b|[,.;:()]|$)"
)
STANDARD = r"(?:TCVN\s+)?ISO(?:/IEC)?\s*\d{4,5}(?::\d{4})?|TCVN\s+\d{4,5}(?::\d{4})?"
US_REG = r"\d+\s*CFR\s*(?:Part\s*)?\d+(?:\.\d+)?(?:\([a-z0-9]+\))*"
BETWEEN = re.compile(
    r"(?<![\w/.])(?:" + LEGAL + r"|(?i:" + STANDARD + r"|" + US_REG + r")|" + CODE + r")",
    re.MULTILINE,
)
INTERNAL = re.compile(r"^(?:BM\.)?(?:QT|BM|HD|HDCV|PL)[ .\-–]?(\d+)", re.IGNORECASE)
GLOBAL = re.compile(r"\d+/|ISO|TCVN|CFR|Luật", re.IGNORECASE)


def norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def code_key(text: str) -> str:
    """Comparable key for a document code: 'QT.05' == 'qt-05' == 'QT 05'; '30/2020/NĐ-CP' kept."""
    value = norm(text).casefold().replace("–", "-")
    value = re.sub(r"^(?:nghị định|thông tư|quyết định|nghị quyết)\s+(?:số\s+)?", "", value)
    value = re.sub(r"^sop[\s-]+", "sop-", value)
    value = re.sub(r"^(qt|bm|hd|hdcv|pl)[\s.\-]?", r"\1-", value)
    return value


def page_texts(root: Path, doc: dict) -> list[str]:
    path = root / doc["path"]
    if not path.is_file():
        return []
    if path.suffix == ".md":
        return [path.read_text(encoding="utf-8")]
    from pypdf import PdfReader

    return [page.extract_text() or "" for page in PdfReader(str(path)).pages]


def strip_furniture(text: str, furniture: list[str]) -> str:
    lines = []
    blocked = {norm(f).casefold() for f in furniture}
    for line in text.splitlines():
        key = norm(line).casefold()
        if key and key in blocked:
            continue
        lines.append(line)
    out = "\n".join(lines)
    for f in sorted(blocked, key=len, reverse=True):
        if len(f) >= 12:
            out = re.sub(re.escape(f).replace(r"\ ", r"\s+"), " ", out, flags=re.IGNORECASE)
    return out


def find_refs(text: str) -> dict[str, list[str]]:
    value = unicodedata.normalize("NFC", text)
    between = [norm(m.group(0)) for m in BETWEEN.finditer(value)]
    within = [norm(m.group(0)) for m in WITHIN.finditer(value)]
    return {"within_document": within, "between_documents": between}


def corpus_aliases(annotations: list[dict], manifest: dict) -> dict[str, list[str]]:
    """code key -> doc_ids; several issuers may share a code such as QT-02."""
    aliases: dict[str, list[str]] = defaultdict(list)
    for rec in annotations:
        code = (rec.get("metadata") or {}).get("doc_code")
        if code:
            aliases[code_key(code)].append(rec["doc_id"])
    for doc in manifest["documents"]:
        for alias in doc.get("aliases", []):
            aliases[code_key(alias)].append(doc["doc_id"])
    return dict(aliases)


def own_number(code: str | None) -> str | None:
    m = INTERNAL.match(code or "")
    return m.group(1).lstrip("0") or "0" if m else None


def is_self_attachment(ref: str, own: str | None) -> bool:
    """BM-01-02 inside QT-01, QT.03.01 inside QT.03: a form/annex of this document."""
    m = INTERNAL.match(ref)
    if not (m and own):
        return False
    same = (m.group(1).lstrip("0") or "0") == own
    exact_other_procedure = re.fullmatch(r"(?i)QT[ .\-–]?\d+", ref.strip()) is not None
    return same and not exact_other_procedure


def is_self_mention(ref: str, own_key: str) -> bool:
    """The document's own code (LSASDPROC-300-R5, 1308/QĐ-TTg) is an identifier, not a reference."""
    key = code_key(ref)
    return key == own_key or own_key.startswith(key + "-r") or (
        "/" in own_key and key.endswith(own_key)
    )


def resolve(
    ref: str, aliases: dict[str, list[str]], hosts: dict[str, str], self_id: str
) -> str | None:
    """Global identifiers (legal numbers, standards) resolve corpus-wide; internal codes such as
    QT-02 are issuer-scoped, so they only resolve to a document from the same source host."""
    key = code_key(ref)
    for alias, doc_ids in aliases.items():
        if not (key == alias or (GLOBAL.search(alias) and alias in key)):
            continue
        for doc_id in doc_ids:
            if doc_id != self_id and (GLOBAL.search(ref) or hosts.get(doc_id) == hosts.get(self_id)):
                return doc_id
    return None


def analyse(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    annotations = {r["doc_id"]: r for r in read_jsonl(root / "annotations.jsonl")}
    aliases = corpus_aliases(list(annotations.values()), manifest)
    hosts = {d["doc_id"]: urlparse(d.get("source", "")).netloc for d in manifest["documents"]}
    docs, no_text = [], []
    groups: dict[str, Counter] = defaultdict(Counter)
    for doc in manifest["documents"]:
        rec = annotations.get(doc["doc_id"], {})
        furniture_by_page: dict[int | None, list[str]] = defaultdict(list)
        for f in rec.get("furniture", []):
            furniture_by_page[f.get("page")].append(f["text"])
        pages = page_texts(root, doc)
        text_chars = sum(len(t.strip()) for t in pages)
        if text_chars == 0:
            no_text.append(doc["doc_id"])
            continue
        within, between, words = [], [], 0
        for number, text in enumerate(pages, 1):
            page_key = None if doc["path"].endswith(".md") else number
            body = strip_furniture(text, furniture_by_page.get(page_key, []))
            words += len(body.split())
            found = find_refs(body)
            within += found["within_document"]
            between += found["between_documents"]
        own_code = (rec.get("metadata") or {}).get("doc_code")
        own = own_number(own_code)
        own_key = code_key(own_code) if own_code else None
        self_mentions = [r for r in between if own_key and is_self_mention(r, own_key)]
        between = [r for r in between if not (own_key and is_self_mention(r, own_key))]
        attachments = [r for r in between if is_self_attachment(r, own)]
        between = [r for r in between if not is_self_attachment(r, own)]
        within += attachments
        resolved = [(r, resolve(r, aliases, hosts, doc["doc_id"])) for r in between]
        in_corpus = [{"text": r, "target": t} for r, t in resolved if t]
        gold = rec.get("cross_references", [])
        row = {
            "doc_id": doc["doc_id"],
            "family": doc.get("family"),
            "lang": doc.get("lang"),
            "words": words,
            "within_document": len(within),
            "between_documents": len(between),
            "between_in_corpus": len(in_corpus),
            "self_mentions_excluded": len(self_mentions),
            "per_1000_words": round(1000 * (len(within) + len(between)) / max(words, 1), 2),
            "gold_within": sum(g.get("kind") == "within_document" for g in gold),
            "gold_between": sum(g.get("kind") == "between_documents" for g in gold),
            "examples_within": sorted(Counter(within).most_common(5)),
            "examples_between": sorted(Counter(between).most_common(5)),
            "in_corpus_targets": sorted({x["target"] for x in in_corpus}),
        }
        docs.append(row)
        for key in (f"family:{row['family']}", f"lang:{row['lang']}", "all"):
            g = groups[key]
            g["documents"] += 1
            g["documents_with_any_ref"] += int(row["within_document"] + row["between_documents"] > 0)
            g["documents_with_within"] += int(row["within_document"] > 0)
            g["documents_with_between_in_corpus"] += int(row["between_in_corpus"] > 0)
            for k in ("words", "within_document", "between_documents", "between_in_corpus",
                      "gold_within", "gold_between"):
                g[k] += row[k]
    summary = {}
    for key, g in sorted(groups.items()):
        refs = g["within_document"] + g["between_documents"]
        summary[key] = dict(g) | {
            "refs_per_1000_words": round(1000 * refs / max(g["words"], 1), 2),
            "share_between_in_corpus": round(g["between_in_corpus"] / max(g["between_documents"], 1), 3),
        }
    return {
        "corpus_version": manifest["corpus_version"],
        "method": "regex candidates over pypdf/Markdown text, labelled furniture removed; not adjudicated",
        "summary": summary,
        "documents": docs,
        "no_text_layer": no_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    payload = json.dumps(analyse(args.dataset), ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    sys.stdout.buffer.write(payload.encode("utf-8"))


if __name__ == "__main__":
    main()
