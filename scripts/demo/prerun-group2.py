"""Pre-run curated Group 2 gold questions through real core-api + ai-service SSE endpoints.

Creates real persisted conversations for corpus-owner@sopilot.local so every question's
answer and Pipeline Inspector trace (rerank ON vs OFF) can be inspected instantly in the UI.

Usage:
    # 0 Modal calls: print question plan and cost/call estimate
    uv run --project services/ai-service python scripts/demo/prerun-group2.py --dry-run

    # Smoke test 2 questions first
    uv run --project services/ai-service python scripts/demo/prerun-group2.py --limit 2

    # Full 10-question pre-run (both rerank ON and OFF)
    uv run --project services/ai-service python scripts/demo/prerun-group2.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

WS_NAME = "SOPilot Acceptance Demo — Corpus 83 (sop-main-v3)"
OWNER_EMAIL = "corpus-owner@sopilot.local"
OWNER_NAME = "Corpus Reviewer"


def api_json(url: str, *, method: str = "GET", token: str | None = None,
             body: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else None


def stream_question(ai_url: str, token: str, question: str, *, rerank: bool,
                    timeout: int = 360) -> dict[str, Any]:
    """Call POST /ai/v1/conversations/new/messages with includeTrace=true and parse SSE."""
    url = f"{ai_url}/ai/v1/conversations/new/messages"
    payload = json.dumps({
        "content": question,
        "includeTrace": True,
        "rerank": rerank,
    }, ensure_ascii=False).encode("utf-8")
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
    steps: list[dict[str, Any]] = []
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
                    elif event_name == "step":
                        steps.append(parsed)
                    elif event_name == "done":
                        done = parsed
                event_name = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

    elapsed_s = round(time.monotonic() - t0, 2)
    conv_id = meta.get("conversationId") or done.get("conversationId")
    msg_id = done.get("messageId")
    trace = None
    if conv_id and msg_id:
        try:
            trace = api_json(
                f"{ai_url}/ai/v1/conversations/{conv_id}/messages/{msg_id}/trace",
                token=token,
            )
        except urllib.error.URLError:
            trace = None

    return {
        "elapsed_s": elapsed_s,
        "conversation_id": conv_id,
        "message_id": msg_id,
        "retrieval_mode": meta.get("retrievalMode"),
        "outcome": done.get("outcome"),
        "refusal_reason": done.get("refusalReason"),
        "citation_count": len(done.get("citations") or []),
        "answer_preview": (done.get("finalText") or "")[:240].replace("\n", " "),
        "trace_summary": _summarize_trace(trace),
    }


def _summarize_trace(trace: dict[str, Any] | None) -> dict[str, Any]:
    if not trace:
        return {}
    out: dict[str, Any] = {}
    for stage in trace.get("stages") or []:
        if stage.get("stage") in ("retrieve_and_gate", "retrieve_rerank", "generate"):
            out[stage["stage"]] = {
                "status": stage.get("status"),
                "durationMs": stage.get("durationMs"),
                "detail": stage.get("detail"),
            }
    return out


def authenticate(core_url: str) -> tuple[str, str]:
    login = api_json(
        f"{core_url}/api/v1/auth/dev-login",
        method="POST",
        body={"email": OWNER_EMAIL, "displayName": OWNER_NAME},
    )
    token = login["data"]["accessToken"]
    workspaces = api_json(f"{core_url}/api/v1/workspaces", token=token)["data"]
    ws = next((w for w in workspaces if w["name"] == WS_NAME), None)
    if ws is None:
        raise RuntimeError(f"Workspace '{WS_NAME}' not found. Run scripts/demo/seed-group2.ps1 first.")
    switched = api_json(
        f"{core_url}/api/v1/auth/switch-workspace",
        method="POST",
        token=token,
        body={"workspaceId": ws["id"]},
    )
    return switched["data"]["accessToken"], ws["id"]


def write_markdown_report(path: Path, results: list[dict[str, Any]]) -> None:
    lines = [
        "# Group 2 Pre-Run Comparison Report (Rerank ON vs OFF)",
        "",
        "| ID | Category | Rerank OFF (mode / outcome / time) | Rerank ON (mode / outcome / time) |",
        "|---|---|---|---|",
    ]
    for r in results:
        off = r["rerank_off"]
        on = r["rerank_on"]
        off_cell = f"`{off['retrieval_mode']}` / {off['outcome']} ({off['refusal_reason'] or f'{off['citation_count']} cites'}) / {off['elapsed_s']}s"
        on_cell = f"`{on['retrieval_mode']}` / {on['outcome']} ({on['refusal_reason'] or f'{on['citation_count']} cites'}) / {on['elapsed_s']}s"
        lines.append(f"| `{r['id']}` | {r['category']} | {off_cell} | {on_cell} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-run Group 2 demo questions (rerank ON vs OFF).")
    parser.add_argument("--core-url", default="http://localhost:8080")
    parser.add_argument("--ai-url", default="http://localhost:8000")
    parser.add_argument("--questions-file", default="scripts/demo/group2-questions.json")
    parser.add_argument("--out-dir", default="scripts/demo")
    parser.add_argument("--skip", type=int, default=0, help="Skip the first N questions.")
    parser.add_argument("--limit", type=int, default=0, help="Run only N questions after skip (0 = all).")
    parser.add_argument("--dry-run", action="store_true", help="Estimate calls & cost without calling Modal.")
    args = parser.parse_args()

    q_path = Path(args.questions_file)
    questions = json.loads(q_path.read_text(encoding="utf-8"))
    if args.skip > 0:
        questions = questions[args.skip :]
    if args.limit > 0:
        questions = questions[: args.limit]

    total_runs = len(questions) * 2
    # Conservative estimate: ~15-25s GPU time per pair when warm -> ~$0.01-$0.02/pair on L40S ($1.95/hr)
    est_minutes = round(total_runs * 0.25, 1)
    est_usd = round((est_minutes / 60.0) * 1.95, 2)

    if args.dry_run:
        sys.stdout.write(f"Dry run: {len(questions)} questions x 2 modes (rerank OFF/ON) = {total_runs} API calls.\n")
        sys.stdout.write(f"Estimated warm L40S time: ~{est_minutes} min (approx. ${est_usd:.2f} USD; +2-4 min if cold start).\n")
        for i, q in enumerate(questions, 1):
            sys.stdout.write(f"  {i:2d}. [{q['category']}] {q['id']} ({q['lang']}): {q['question']}\n")
        return 0

    token, _ = authenticate(args.core_url)
    token_issued_at = time.monotonic()
    opts = api_json(f"{args.ai_url}/ai/v1/retrieval/options", token=token)
    if not opts.get("rerank", {}).get("available"):
        sys.stderr.write("ERROR: Server reports rerank.available=false. Enable RERANK_ENABLED=true before pre-run.\n")
        return 1

    results: list[dict[str, Any]] = []
    for idx, q in enumerate(questions, 1):
        if time.monotonic() - token_issued_at >= 600:
            token, _ = authenticate(args.core_url)
            token_issued_at = time.monotonic()
        sys.stdout.write(f"[{idx}/{len(questions)}] {q['id']} — running rerank=OFF then rerank=ON...\n")
        sys.stdout.flush()
        res_off = stream_question(args.ai_url, token, q["question"], rerank=False)
        res_on = stream_question(args.ai_url, token, q["question"], rerank=True)
        # Rename conversations so they are easy to pick in the chat sidebar during the defense
        if res_off["conversation_id"]:
            api_json(
                f"{args.ai_url}/ai/v1/conversations/{res_off['conversation_id']}",
                method="PATCH",
                token=token,
                body={"title": f"[Rerank OFF] {q['id']}: {q['question'][:80]}"},
            )
        if res_on["conversation_id"]:
            api_json(
                f"{args.ai_url}/ai/v1/conversations/{res_on['conversation_id']}",
                method="PATCH",
                token=token,
                body={"title": f"[Rerank ON] {q['id']}: {q['question'][:80]}"},
            )
        results.append({"id": q["id"], "category": q["category"], "question": q["question"],
                        "rerank_off": res_off, "rerank_on": res_on})

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "group2-prerun-report.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown_report(out_dir / "group2-prerun-report.md", results)
    sys.stdout.write(f"Saved report to {out_dir / 'group2-prerun-report.md'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
