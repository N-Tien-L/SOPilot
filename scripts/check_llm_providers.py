"""List the LLM models a Groq / Gemini key can use, with their rate limits.

Reads GROQ_API_KEY and GEMINI_API_KEY from the environment, falling back to
the repo-root .env. Key values are never written to output.

How limits are discovered:
- Groq: GET /models lists models. Limits are only returned as response headers
  on a request, so each chat model is probed with a 1-token completion and the
  x-ratelimit-* headers are recorded (RPD = requests/day, TPM = tokens/minute).
- Gemini: GET /models lists models. The API does not expose free-tier limits;
  a probe only shows whether the model is callable. When the probe is
  rejected with 429, the QuotaFailure details (metric + limit) are recorded,
  which reveals free-tier quotas of 0. See https://aistudio.google.com/rate-limit
  for the full table.

Each probe uses one request of that model's quota. Use --no-probe to list only.

Usage (from repo root):
    python scripts/check_llm_providers.py
    python scripts/check_llm_providers.py --provider groq --json out.json
    python scripts/check_llm_providers.py --provider gemini --match flash
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GROQ_BASE = "https://api.groq.com/openai/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT_S = 30

# Groq models that do not accept chat completions.
GROQ_NON_CHAT = ("whisper", "tts", "orpheus", "playai", "distil-whisper")
# Gemini models that support generateContent but are not text chat models.
GEMINI_NON_TEXT = (
    "imagen", "veo", "tts", "native-audio", "live", "image", "embedding", "aqa", "robotics",
    "computer-use", "lyria", "nano-banana", "transcribe", "deep-research", "antigravity", "omni",
)

GROQ_LIMIT_HEADERS = {
    "x-ratelimit-limit-requests": "rpd",
    "x-ratelimit-remaining-requests": "rpd_remaining",
    "x-ratelimit-reset-requests": "rpd_reset",
    "x-ratelimit-limit-tokens": "tpm",
    "x-ratelimit-remaining-tokens": "tpm_remaining",
    "x-ratelimit-reset-tokens": "tpm_reset",
}


def emit(line: str = "") -> None:
    sys.stdout.write(line + "\n")


def load_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return None
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip().removeprefix("export ").strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        return value or None
    return None


def http(method: str, url: str, headers: dict[str, str], body: dict | None = None) -> tuple[int, dict[str, str], dict | str]:
    data = json.dumps(body).encode() if body is not None else None
    # Groq's edge rejects the default Python-urllib User-Agent with 403.
    base_headers = {"Content-Type": "application/json", "User-Agent": "sopilot-provider-check/1.0"}
    req = urllib.request.Request(url, data=data, method=method, headers={**base_headers, **headers})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                status, resp_headers, raw = resp.status, dict(resp.headers), resp.read()
            break
        except urllib.error.HTTPError as err:
            status, resp_headers, raw = err.code, dict(err.headers or {}), err.read()
            break
        except (urllib.error.URLError, TimeoutError) as err:
            if attempt == 1:
                return 0, {}, f"network error: {err}"
            time.sleep(2)
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, {k.lower(): v for k, v in resp_headers.items()}, json.loads(text)
    except json.JSONDecodeError:
        return status, {k.lower(): v for k, v in resp_headers.items()}, text


def error_message(payload: dict | str) -> str:
    if isinstance(payload, dict):
        err = payload.get("error", payload)
        if isinstance(err, dict):
            return str(err.get("message") or err.get("status") or err)[:1000]
        return str(err)[:1000]
    return payload[:1000]


def check_groq(key: str, probe: bool, match: str | None) -> dict:
    auth = {"Authorization": f"Bearer {key}"}
    status, _, payload = http("GET", f"{GROQ_BASE}/models", auth)
    if status != 200 or not isinstance(payload, dict):
        return {"ok": False, "status": status, "error": error_message(payload), "models": []}

    models = []
    for m in sorted(payload.get("data", []), key=lambda x: x.get("id", "")):
        mid = m.get("id", "")
        if match and match.lower() not in mid.lower():
            continue
        row = {
            "id": mid,
            "owned_by": m.get("owned_by"),
            "active": m.get("active"),
            "context_window": m.get("context_window"),
            "max_completion_tokens": m.get("max_completion_tokens"),
            "chat": not any(tag in mid for tag in GROQ_NON_CHAT),
        }
        if probe and row["chat"] and row["active"] is not False:
            p_status, p_headers, p_payload = http(
                "POST",
                f"{GROQ_BASE}/chat/completions",
                auth,
                {"model": mid, "messages": [{"role": "user", "content": "ping"}], "max_completion_tokens": 1},
            )
            row["probe_status"] = p_status
            row.update({field: p_headers.get(header) for header, field in GROQ_LIMIT_HEADERS.items()})
            if p_status != 200:
                row["probe_error"] = error_message(p_payload)
            time.sleep(2.1)  # stay under the free-tier 30 requests/minute
        models.append(row)
    return {"ok": True, "status": status, "models": models}


def gemini_quota_violations(payload: dict | str) -> list[dict]:
    """QuotaFailure details; the limit value is often only in the message ("limit: 0, model: ...")."""
    if not isinstance(payload, dict):
        return []
    message = error_message(payload)
    limits = {m.group(1): m.group(2) for m in re.finditer(r"Quota exceeded for metric: \S+?/(\S+?), limit: (\d+)", message)}
    found = []
    for detail in payload.get("error", {}).get("details", []):
        if detail.get("@type", "").endswith("QuotaFailure"):
            for v in detail.get("violations", []):
                metric = (v.get("quotaMetric") or "").rsplit("/", 1)[-1]
                value = v.get("quotaValue") or limits.get(metric)
                found.append({"quotaMetric": v.get("quotaMetric"), "quotaId": v.get("quotaId"), "quotaValue": value})
    if not found and "limit: 0" in message:
        found.append({"quotaMetric": None, "quotaId": "unknown", "quotaValue": "0"})
    return found


def check_gemini(key: str, probe: bool, match: str | None) -> dict:
    auth = {"x-goog-api-key": key}
    listed, page_token = [], None
    while True:
        url = f"{GEMINI_BASE}/models?pageSize=1000" + (f"&pageToken={page_token}" if page_token else "")
        status, _, payload = http("GET", url, auth)
        if status != 200 or not isinstance(payload, dict):
            return {"ok": False, "status": status, "error": error_message(payload), "models": []}
        listed.extend(payload.get("models", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    models = []
    for m in sorted(listed, key=lambda x: x.get("name", "")):
        mid = m.get("name", "").removeprefix("models/")
        if match and match.lower() not in mid.lower():
            continue
        methods = m.get("supportedGenerationMethods", [])
        row = {
            "id": mid,
            "display_name": m.get("displayName"),
            "input_token_limit": m.get("inputTokenLimit"),
            "output_token_limit": m.get("outputTokenLimit"),
            "methods": methods,
            "chat": "generateContent" in methods and not any(tag in mid for tag in GEMINI_NON_TEXT),
        }
        if probe and row["chat"]:
            p_status, _, p_payload = http(
                "POST",
                f"{GEMINI_BASE}/models/{mid}:generateContent",
                auth,
                {"contents": [{"parts": [{"text": "ping"}]}], "generationConfig": {"maxOutputTokens": 1}},
            )
            row["probe_status"] = p_status
            if p_status != 200:
                row["probe_error"] = error_message(p_payload)
                row["quota_violations"] = gemini_quota_violations(p_payload)
            time.sleep(0.5)
        models.append(row)
    return {"ok": True, "status": status, "models": models}


def short_quota(quota_id: str | None) -> str:
    q = quota_id or ""
    if "Requests" in q:
        return "RPD" if "PerDay" in q else "RPM"
    if "Tokens" in q:
        return "TPD" if "PerDay" in q else "TPM"
    return q or "?"


def verdict(row: dict) -> str:
    if "probe_status" not in row:
        return "listed" if row.get("chat") else "non-chat"
    if row["probe_status"] == 200:
        return "OK"
    if row["probe_status"] == 429:
        zero = any(str(v.get("quotaValue")) == "0" for v in row.get("quota_violations", []))
        return "NO FREE QUOTA" if zero else "RATE LIMITED"
    return f"FAIL {row['probe_status']}"


def render_table(headers: list[str], rows: list[list]) -> None:
    cells = [[("" if c is None else str(c)) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h) for i, h in enumerate(headers)]
    emit("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    emit("  ".join("-" * w for w in widths))
    for r in cells:
        emit("  ".join(c.ljust(w) for c, w in zip(r, widths)))


def report(name: str, result: dict) -> None:
    emit(f"\n=== {name} ===")
    if not result.get("ok"):
        emit(f"FAILED to list models: HTTP {result.get('status')} {result.get('error', '')}")
        return
    rows = result["models"]
    if name == "groq":
        render_table(
            ["model", "status", "ctx", "max_out", "RPD", "RPD left", "TPM", "TPM left"],
            [[r["id"], verdict(r), r["context_window"], r["max_completion_tokens"], r.get("rpd"), r.get("rpd_remaining"), r.get("tpm"), r.get("tpm_remaining")] for r in rows],
        )
    else:
        render_table(
            ["model", "status", "in_tokens", "out_tokens", "quota detail"],
            [
                [
                    r["id"],
                    verdict(r),
                    r["input_token_limit"],
                    r["output_token_limit"],
                    " ".join(sorted(f"{short_quota(v['quotaId'])}={v['quotaValue']}" for v in r.get("quota_violations", []))),
                ]
                for r in rows
            ],
        )
        emit("Gemini free-tier RPM/TPM/RPD are not exposed via API: https://aistudio.google.com/rate-limit")
    failed = [r for r in rows if r.get("probe_status") not in (None, 200, 429)]
    for r in failed:
        emit(f"  ! {r['id']}: {r.get('probe_error', '')[:200]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", choices=["groq", "gemini", "all"], default="all")
    parser.add_argument("--no-probe", action="store_true", help="only list models; send no completion requests")
    parser.add_argument("--match", help="only models whose id contains this substring")
    parser.add_argument("--json", type=Path, help="also write the full result to this JSON file")
    args = parser.parse_args()

    checks = {"groq": ("GROQ_API_KEY", check_groq), "gemini": ("GEMINI_API_KEY", check_gemini)}
    selected = checks if args.provider == "all" else {args.provider: checks[args.provider]}
    output = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "probe": not args.no_probe, "providers": {}}

    exit_code = 0
    for name, (env_name, fn) in selected.items():
        key = load_key(env_name)
        if not key:
            emit(f"\n=== {name} ===\nSKIPPED: {env_name} not set in environment or .env")
            output["providers"][name] = {"ok": False, "error": f"{env_name} missing", "models": []}
            exit_code = 1
            continue
        result = fn(key, probe=not args.no_probe, match=args.match)
        output["providers"][name] = result
        report(name, result)
        if not result.get("ok"):
            exit_code = 1

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        emit(f"\nWrote {args.json}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
