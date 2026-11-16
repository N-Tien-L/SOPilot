"""Long-prompt TTFT, decode speed and a concurrency smoke test for the answer endpoint (V2-40).

Measures what ADR-011 estimated: time to first token at 8K / 32K / 64K prompt tokens, decode
tokens per second, and whether 8 long requests at once all complete. Stdlib HTTP only.

    python infrastructure/modal/bench_context.py ttft --sizes 8000 32000 64000 --repeat 3
    python infrastructure/modal/bench_context.py smoke --concurrency 8 --tokens 32000

The endpoint URL, key and model id come from the environment (``SOPILOT_LLM_BASE_URL``,
``SOPILOT_LLM_API_KEY``, ``SOPILOT_LLM_MODEL``) or flags, never from this file. Warm the container
first: a cold start takes minutes and would be counted in the first request.

Every prompt starts with a random nonce, so vLLM's prefix cache cannot serve a repeated prompt and
the TTFT is a real prefill. The prompt size reported is the server's ``prompt_tokens``, not an
estimate: the filler is calibrated once per size with a one-token request.

The client cannot see a preemption or an out-of-memory kill in a healthy-looking stream. After
``smoke``, read the server log (``modal app logs sopilot-vllm``) for ``preempt``, ``OOM`` and
``out of memory``, and record what you found next to the result.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

QUESTION = "Summarise, in about 150 words, what the sections above say about approvals."


def out(message: str = "") -> None:
    """One line of CLI output (flushed so a long run streams)."""
    sys.stdout.write(f"{message}\n")
    sys.stdout.flush()


def filler(lines: int, nonce: str) -> str:
    """``lines`` numbered SOP-like lines; the nonce first, so no two prompts share a prefix."""
    body = "\n".join(
        f"Section {i}. Procedure {i % 17} needs the approval of the department head within "
        f"{i % 9 + 1} working days; exception {i % 5} applies to temporary staff."
        for i in range(lines))
    return f"[run {nonce}]\n{body}\n\n{QUESTION}"


def stream(base: str, key: str, model: str, prompt: str, max_tokens: int, timeout: float) -> dict:
    """One streamed chat completion; thinking off. ``error`` is set on any failure."""
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0,
            "max_tokens": max_tokens, "stream": True, "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False}}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base.rstrip('/')}/chat/completions",
                                 json.dumps(body).encode(), headers, method="POST")
    t0 = time.perf_counter()
    first = None
    usage: dict = {}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - own endpoint
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                obj = json.loads(data)
                usage = obj.get("usage") or usage
                choices = obj.get("choices") or []
                if choices and first is None and (choices[0].get("delta") or {}).get("content"):
                    first = time.perf_counter() - t0
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}"}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {"error": type(exc).__name__}
    total = time.perf_counter() - t0
    done = usage.get("completion_tokens") or 0
    decode = (done - 1) / (total - first) if first is not None and done > 1 and total > first else None
    return {"ttft": first, "total": total, "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": done, "decode_tps": decode}


def lines_for(args: argparse.Namespace, target: int) -> int:
    """Number of filler lines that reach about ``target`` prompt tokens (one calibration call)."""
    probe = 200
    res = stream(args.base_url, args.api_key, args.model, filler(probe, uuid.uuid4().hex), 1,
                 args.timeout)
    if "error" in res or not res["prompt_tokens"]:
        raise SystemExit(f"calibration failed: {res.get('error', 'no usage in the reply')}")
    return max(1, round(target * probe / res["prompt_tokens"]))


def cmd_ttft(args: argparse.Namespace) -> int:
    out(f"{'target':>8} {'prompt':>8} {'ttft s':>8} {'decode tok/s':>13} {'out tok':>8}")
    for target in args.sizes:
        lines = lines_for(args, target)
        rows = []
        for _ in range(args.repeat):
            res = stream(args.base_url, args.api_key, args.model, filler(lines, uuid.uuid4().hex),
                         args.max_tokens, args.timeout)
            if "error" in res:
                out(f"{target:>8} error {res['error']}")
                continue
            rows.append(res)
            tps = "-" if res["decode_tps"] is None else f"{res['decode_tps']:.1f}"
            out(f"{target:>8} {res['prompt_tokens'] or 0:>8} {res['ttft'] or 0:>8.2f} {tps:>13} "
                f"{res['completion_tokens']:>8}")
        ttfts = [r["ttft"] for r in rows if r["ttft"] is not None]
        if ttfts:
            tpss = [r["decode_tps"] for r in rows if r["decode_tps"] is not None]
            out(f"{target:>8} median ttft {statistics.median(ttfts):.2f} s over {len(ttfts)} runs"
                + (f", median decode {statistics.median(tpss):.1f} tok/s" if tpss else ""))
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    lines = lines_for(args, args.tokens)
    results: list[dict] = [{}] * args.concurrency
    start = threading.Barrier(args.concurrency)

    def worker(i: int) -> None:
        start.wait()  # all requests leave together
        results[i] = stream(args.base_url, args.api_key, args.model,
                            filler(lines, uuid.uuid4().hex), args.max_tokens, args.timeout)

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(args.concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    bad = [r for r in results if "error" in r or not r.get("completion_tokens")]
    for i, r in enumerate(results):
        out(f"[{i}] " + (f"error {r.get('error', 'no result')}" if "error" in r or not r else
                         f"prompt {r['prompt_tokens']} ttft {r['ttft'] or 0:.1f}s "
                         f"total {r['total']:.1f}s out {r['completion_tokens']}"))
    out(f"{args.concurrency - len(bad)}/{args.concurrency} completed in {wall:.1f} s wall clock")
    out("Now check the server log for 'preempt', 'OOM' and 'out of memory' (see the docstring).")
    return 1 if bad else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base-url", default=os.environ.get("SOPILOT_LLM_BASE_URL", ""))
    ap.add_argument("--api-key", default=os.environ.get("SOPILOT_LLM_API_KEY", ""))
    ap.add_argument("--model", default=os.environ.get("SOPILOT_LLM_MODEL", "Qwen/Qwen3.5-9B"))
    ap.add_argument("--timeout", type=float, default=900.0)
    sub = ap.add_subparsers(dest="command", required=True)
    t = sub.add_parser("ttft", help="TTFT and decode speed at given prompt sizes")
    t.add_argument("--sizes", type=int, nargs="+", default=[8000, 32000, 64000],
                   help="target prompt tokens (65536 is the server limit, keep room for output)")
    t.add_argument("--repeat", type=int, default=3)
    t.add_argument("--max-tokens", type=int, default=256)
    s = sub.add_parser("smoke", help="N long requests at once: all must complete")
    s.add_argument("--concurrency", type=int, default=8)
    s.add_argument("--tokens", type=int, default=32000, help="target prompt tokens per request")
    s.add_argument("--max-tokens", type=int, default=256)
    args = ap.parse_args()
    if not args.base_url:
        out("Set SOPILOT_LLM_BASE_URL (or --base-url).")
        return 2
    return {"ttft": cmd_ttft, "smoke": cmd_smoke}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
