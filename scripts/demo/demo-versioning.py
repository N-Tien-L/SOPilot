"""Automated end-to-end demo for Document Versioning (Group 1).

Tests the full versioning lifecycle against live core-api + ai-service:
1. Upload v1 (ops-oncall-allowance-2025.md) as eng-lead (DEPARTMENT publisher), assign category.
2. Ask Q&A as eng-member -> verify v1 figures (200,000 / 400,000 / 30 min) and v1 citation.
3. Upload v2 (ops-oncall-allowance-2026.md, different filename!) via POST /documents/{id}/versions.
4. Verify:
   - v1 status becomes SUPERSEDED, v2 becomes READY (currentVersion.versionNo == 2)
   - SYSTEM title auto-syncs from "ops-oncall-allowance-2025" -> "ops-oncall-allowance-2026"
   - Category from v1 is inherited and NOT overwritten
5. Ask the exact same Q&A as eng-member -> verify v2 figures (350,000 / 700,000 / 10 min),
   zero old v1 figures, and citation points to v2 with the synced title.
6. Negative checks:
   - Re-uploading identical v2 file returns 409 DOCUMENT_UNCHANGED.
   - hr-member asking the same question gets NO_EVIDENCE (department isolation preserved).

Usage:
    uv run --project services/ai-service python scripts/demo/demo-versioning.py
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

WS_NAME = "SOPilot Acceptance Demo — Multi-Role"
DOCS_DIR = Path(__file__).resolve().parent / "docs"
V1_FILE = DOCS_DIR / "ops-oncall-allowance-2025.md"
V2_FILE = DOCS_DIR / "ops-oncall-allowance-2026.md"
QUESTION = (
    "Theo SOP-OPS-07, phụ cấp trực on-call ngày thường, cuối tuần, "
    "giới hạn ca trực mỗi tháng và SLA phản hồi sự cố P1 là bao nhiêu?"
)


def api_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def multipart_upload(
    url: str,
    *,
    token: str,
    file_path: Path,
    fields: dict[str, str | list[str]] | None = None,
    timeout: int = 60,
) -> tuple[int, Any]:
    boundary = f"----SOPilotDemo{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(value.encode("utf-8"))
        chunks.append(b"\r\n")

    for k, v in (fields or {}).items():
        if isinstance(v, list):
            for item in v:
                add_field(k, item)
        else:
            add_field(k, v)

    mime = mimetypes.guess_type(file_path.name)[0] or "text/markdown"
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode()
    )
    chunks.append(f"Content-Type: {mime}\r\n\r\n".encode())
    chunks.append(file_path.read_bytes())
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())

    body = b"".join(chunks)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def dev_login_and_switch(core_url: str, email: str, display_name: str, ws_id: str | None = None) -> tuple[str, str]:
    status, resp = api_json(
        f"{core_url}/api/v1/auth/dev-login",
        method="POST",
        body={"email": email, "displayName": display_name},
    )
    if status != 200:
        raise RuntimeError(f"dev-login failed for {email}: {status} {resp}")
    token = resp["data"]["accessToken"]
    if ws_id is None:
        _, ws_resp = api_json(f"{core_url}/api/v1/workspaces", token=token)
        found = next((w for w in ws_resp["data"] if w["name"] == WS_NAME), None)
        if not found:
            raise RuntimeError(f"Workspace '{WS_NAME}' not found. Run scripts/demo/seed-group1.ps1 first.")
        ws_id = found["id"]
    status, sw = api_json(
        f"{core_url}/api/v1/auth/switch-workspace",
        method="POST",
        token=token,
        body={"workspaceId": ws_id},
    )
    if status != 200:
        raise RuntimeError(f"switch-workspace failed for {email}: {status} {sw}")
    return sw["data"]["accessToken"], ws_id


def wait_doc_version_ready(core_url: str, token: str, doc_id: str, expected_ver_no: int, timeout_s: int = 180) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status, resp = api_json(f"{core_url}/api/v1/documents/{doc_id}", token=token)
        if status != 200:
            raise RuntimeError(f"GET document {doc_id} failed: {status} {resp}")
        doc = resp["data"]
        latest = doc["latestVersion"]
        if latest["versionNo"] == expected_ver_no:
            if latest["status"] == "READY":
                return doc
            if latest["status"] == "FAILED":
                raise RuntimeError(f"Version v{expected_ver_no} FAILED: {latest.get('failureCode')} {latest.get('failureMessage')}")
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for document {doc_id} v{expected_ver_no} to reach READY")


def stream_qa(ai_url: str, token: str, question: str, *, rerank: bool = True, timeout: int = 360) -> dict[str, Any]:
    url = f"{ai_url}/ai/v1/conversations/new/messages"
    payload = json.dumps({"content": question, "includeTrace": True, "rerank": rerank}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    t0 = time.monotonic()
    meta: dict[str, Any] = {}
    done: dict[str, Any] = {}
    citations: list[dict[str, Any]] = []
    event_name: str | None = None
    data_lines: list[str] = []

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").rstrip("\r\n")
            if line.startswith(":"):
                continue
            if line == "":
                if event_name and data_lines:
                    try:
                        parsed = json.loads("\n".join(data_lines))
                    except json.JSONDecodeError:
                        parsed = {"raw": "\n".join(data_lines)}
                    if event_name == "meta":
                        meta = parsed
                    elif event_name == "citations":
                        citations = parsed.get("citations") or (parsed if isinstance(parsed, list) else [])
                    elif event_name == "done":
                        done = parsed
                event_name = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

    return {
        "elapsed_s": round(time.monotonic() - t0, 2),
        "conversation_id": meta.get("conversationId") or done.get("conversationId"),
        "retrieval_mode": meta.get("retrievalMode"),
        "outcome": done.get("outcome"),
        "refusal_reason": done.get("refusalReason"),
        "citations": citations or done.get("citations") or [],
        "answer": done.get("finalText") or "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Group 1 Document Versioning end-to-end demo.")
    parser.add_argument("--core-url", default="http://localhost:8080")
    parser.add_argument("--ai-url", default="http://localhost:8000")
    parser.add_argument("--no-rerank", action="store_true", help="Disable reranker for Q&A calls.")
    parser.add_argument("--keep-doc", action="store_true", default=True, help="Keep the v2 document in Group 1 after run.")
    args = parser.parse_args()

    print("=== Group 1 Versioning E2E Demo ===")
    owner_token, ws_id = dev_login_and_switch(args.core_url, "owner@sopilot.local", "Nguyễn Minh Chủ")
    eng_lead_token, _ = dev_login_and_switch(args.core_url, "eng-lead@sopilot.local", "Lê Kỹ Thuật (Lead)", ws_id)
    eng_member_token, _ = dev_login_and_switch(args.core_url, "eng-member@sopilot.local", "Phạm Dev", ws_id)
    hr_member_token, _ = dev_login_and_switch(args.core_url, "hr-member@sopilot.local", "Đỗ Tuyển Dụng", ws_id)

    # Resolve Kỹ thuật department & Vận hành & An toàn category
    _, depts_resp = api_json(f"{args.core_url}/api/v1/departments", token=owner_token)
    dept_eng = next(d["id"] for d in depts_resp["data"] if d["name"] == "Kỹ thuật")
    _, cats_resp = api_json(f"{args.core_url}/api/v1/categories", token=owner_token)
    cat_ops = next(c for c in cats_resp["data"] if c["name"] == "Vận hành & An toàn")

    # Clean any prior run of ops-oncall-allowance-* so this demo is repeatable
    _, docs_resp = api_json(f"{args.core_url}/api/v1/documents?limit=100", token=owner_token)
    for d in docs_resp["data"]:
        if d["title"].startswith("ops-oncall-allowance"):
            print(f"[CLEAN] Deleting previous demo document {d['id']} ({d['title']})...")
            api_json(f"{args.core_url}/api/v1/documents/{d['id']}", method="DELETE", token=owner_token)
            time.sleep(2)

    results: dict[str, Any] = {"workspaceId": ws_id, "checks": []}

    def record(name: str, passed: bool, detail: str) -> None:
        tag = "PASS" if passed else "FAIL"
        print(f"[{tag}] {name}: {detail}")
        results["checks"].append({"name": name, "passed": passed, "detail": detail})

    # 1. Upload v1 (omit title -> SYSTEM title = "ops-oncall-allowance-2025")
    print("\n[STEP 1] Uploading v1 (ops-oncall-allowance-2025.md) as eng-lead...")
    status, up1 = multipart_upload(
        f"{args.core_url}/api/v1/documents",
        token=eng_lead_token,
        file_path=V1_FILE,
        fields={
            "visibility": "DEPARTMENTS",
            "ownerDepartmentId": dept_eng,
            "departmentIds": [dept_eng],
            "categoryId": cat_ops["id"],
        },
    )
    if status not in (200, 201):
        raise RuntimeError(f"v1 upload failed: {status} {up1}")
    doc_id = up1["data"]["id"]
    doc_v1 = wait_doc_version_ready(args.core_url, eng_lead_token, doc_id, expected_ver_no=1)
    v1_id = doc_v1["currentVersion"]["id"]
    record(
        "v1_ready_and_metadata",
        doc_v1["title"] == "ops-oncall-allowance-2025"
        and doc_v1["fieldSources"]["title"] == "SYSTEM"
        and (doc_v1.get("category") or {}).get("id") == cat_ops["id"],
        f"docId={doc_id}, v1={v1_id}, title={doc_v1['title']!r}, category={(doc_v1.get('category') or {}).get('name')!r}",
    )

    # 2. Ask Q&A on v1 as eng-member
    print("\n[STEP 2] Asking Q&A on v1 as eng-member...")
    qa_v1 = stream_qa(args.ai_url, eng_member_token, QUESTION, rerank=not args.no_rerank)
    ans1 = qa_v1["answer"]
    v1_ok = (
        qa_v1["outcome"] == "ANSWERED"
        and "200" in ans1
        and "400" in ans1
        and "30" in ans1
        and any(c.get("versionId") == v1_id for c in qa_v1["citations"])
    )
    record(
        "qa_v1_answers_old_figures",
        v1_ok,
        f"outcome={qa_v1['outcome']}, elapsed={qa_v1['elapsed_s']}s, citations={len(qa_v1['citations'])}, answer={ans1[:220]!r}",
    )
    results["qa_v1"] = qa_v1

    # 3. Upload v2 (different filename!) as eng-lead
    print("\n[STEP 3] Uploading v2 (ops-oncall-allowance-2026.md) via POST /documents/{id}/versions...")
    status, up2 = multipart_upload(
        f"{args.core_url}/api/v1/documents/{doc_id}/versions",
        token=eng_lead_token,
        file_path=V2_FILE,
    )
    if status not in (200, 201):
        raise RuntimeError(f"v2 upload failed: {status} {up2}")
    doc_v2 = wait_doc_version_ready(args.core_url, eng_lead_token, doc_id, expected_ver_no=2)
    v2_id = doc_v2["currentVersion"]["id"]

    # Check version history: v1 SUPERSEDED, v2 READY
    _, hist_resp = api_json(f"{args.core_url}/api/v1/documents/{doc_id}/versions", token=eng_lead_token)
    hist_by_no = {v["versionNo"]: v["status"] for v in hist_resp["data"]}

    record(
        "v2_activated_and_v1_superseded",
        doc_v2["currentVersion"]["versionNo"] == 2
        and hist_by_no.get(1) == "SUPERSEDED"
        and hist_by_no.get(2) == "READY",
        f"v2={v2_id}, history={hist_by_no}",
    )
    record(
        "title_synced_to_v2_filename",
        doc_v2["title"] == "ops-oncall-allowance-2026",
        f"title={doc_v2['title']!r} (expected 'ops-oncall-allowance-2026')",
    )
    record(
        "category_inherited_from_v1",
        (doc_v2.get("category") or {}).get("id") == cat_ops["id"],
        f"category={(doc_v2.get('category') or {}).get('name')!r}",
    )

    # 4. Ask the EXACT SAME Q&A on v2 as eng-member
    print("\n[STEP 4] Asking the same Q&A on v2 as eng-member...")
    qa_v2 = stream_qa(args.ai_url, eng_member_token, QUESTION, rerank=not args.no_rerank)
    ans2 = qa_v2["answer"]
    has_new = "350" in ans2 and "700" in ans2 and "10" in ans2
    has_old = "200,000" in ans2 or "200.000" in ans2 or "400,000" in ans2 or "400.000" in ans2 or "30 phút" in ans2 or "30 minutes" in ans2
    cites_v2 = any(c.get("versionId") == v2_id for c in qa_v2["citations"])
    cites_v1 = any(c.get("versionId") == v1_id for c in qa_v2["citations"])
    cite_titles = [c.get("documentTitle") for c in qa_v2["citations"]]
    record(
        "qa_v2_answers_new_figures_zero_v1_leak",
        qa_v2["outcome"] == "ANSWERED" and has_new and not has_old and cites_v2 and not cites_v1,
        f"outcome={qa_v2['outcome']}, elapsed={qa_v2['elapsed_s']}s, citeTitles={cite_titles}, answer={ans2[:240]!r}",
    )
    results["qa_v2"] = qa_v2

    # 5. Negative check: re-upload identical v2 -> 409 DOCUMENT_UNCHANGED
    print("\n[STEP 5] Negative check: re-uploading identical v2 file...")
    dup_status, dup_body = multipart_upload(
        f"{args.core_url}/api/v1/documents/{doc_id}/versions",
        token=eng_lead_token,
        file_path=V2_FILE,
    )
    dup_code = (dup_body or {}).get("error", {}).get("code")
    record(
        "unchanged_reupload_rejected_409",
        dup_status == 409 and dup_code == "DOCUMENT_UNCHANGED",
        f"HTTP {dup_status}, code={dup_code}",
    )

    # 6. Negative check: hr-member still cannot read Engineering v2
    print("\n[STEP 6] Negative check: hr-member department isolation on v2...")
    qa_hr = stream_qa(args.ai_url, hr_member_token, QUESTION, rerank=not args.no_rerank)
    record(
        "hr_member_blocked_from_eng_v2",
        qa_hr["outcome"] != "ANSWERED" and len(qa_hr["citations"]) == 0,
        f"outcome={qa_hr['outcome']}, refusalReason={qa_hr['refusal_reason']}, elapsed={qa_hr['elapsed_s']}s",
    )
    results["qa_hr"] = qa_hr

    # Write report
    report_path = Path(__file__).resolve().parent / "versioning-demo-report.md"
    passed_count = sum(1 for c in results["checks"] if c["passed"])
    total_count = len(results["checks"])
    lines = [
        "# Group 1 Document Versioning Demo Report",
        "",
        f"- **Workspace:** `{WS_NAME}` (`{ws_id}`)",
        f"- **Document ID:** `{doc_id}`",
        f"- **Question:** `{QUESTION}`",
        f"- **Result:** **{passed_count}/{total_count} checks passed**",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    for c in results["checks"]:
        lines.append(f"| `{c['name']}` | **{'PASS' if c['passed'] else 'FAIL'}** | {c['detail'].replace('|', '\\|')} |")
    lines += [
        "",
        "## Q&A Answers",
        "",
        f"### v1 (`ops-oncall-allowance-2025.md`, {qa_v1['elapsed_s']}s)",
        "",
        qa_v1["answer"],
        "",
        f"### v2 (`ops-oncall-allowance-2026.md`, {qa_v2['elapsed_s']}s)",
        "",
        qa_v2["answer"],
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {report_path}")
    print(f"=== SUMMARY: {passed_count}/{total_count} PASSED ===")
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
