"""Time the SetFit router over the network: classify + round trip (V2-44, ADR-012).

Talks to the Kaggle server from ``eval/kaggle/setfit_bench_server.ipynb``. For each device the server
offers (cpu, cuda) it sends ``--n`` test questions one at a time (the service classifies one question per
turn), after ``--warmup`` untimed ones, and records per request:

- ``total``   client wall time (what a caller sees: network + server work)
- ``server``  server time for encode + head
- ``network`` ``total - server`` (round trip, TLS, tunnel)

The first request on each device is reported as ``cold`` and left out of the statistics. A pure round
trip baseline (``GET /health``, no model work) is measured too. Run from ``eval/``::

    $env:ROUTER_API_TOKEN = "<token printed by the notebook>"
    uv run python experiments/routing/bench_setfit_latency.py --url https://<name>.trycloudflare.com --label kaggle-t4

Writes ``results/routing/setfit-latency/<label>.json``. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sopilot_eval.routing import EVAL_ROOT, load_dataset
from sopilot_eval.routing_remote import model_input


def call(url: str, token: str, payload: dict | None = None, timeout: float = 120.0) -> tuple[dict, float]:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="GET" if payload is None else "POST",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    return body, (time.perf_counter() - t0) * 1000


def stats(values: list[float]) -> dict[str, float | int]:
    data = sorted(values)
    q = statistics.quantiles(data, n=100, method="inclusive") if len(data) > 1 else [data[0]] * 99
    return {"n": len(data), "mean": round(statistics.fmean(data), 1), "p50": round(q[49], 1),
            "p95": round(q[94], 1), "max": round(data[-1], 1)}


def bench_device(base: str, token: str, device: str, texts: list[str], warmup: int) -> dict:
    url = f"{base}/classify"
    _, cold = call(url, token, {"text": texts[0], "device": device})
    for text in texts[1:1 + warmup]:
        call(url, token, {"text": text, "device": device})
    total, server, encode, network = [], [], [], []
    for text in texts[1 + warmup:]:
        body, wall = call(url, token, {"text": text, "device": device})
        total.append(wall)
        server.append(body["server_ms"])
        encode.append(body["encode_ms"])
        network.append(wall - body["server_ms"])
    return {"cold_ms": round(cold, 1), "total": stats(total), "server": stats(server),
            "encode": stats(encode), "network": stats(network)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--label", required=True, help="result file name, e.g. kaggle-t4")
    ap.add_argument("--n", type=int, default=100, help="timed requests per device")
    ap.add_argument("--warmup", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    token = os.environ.get("ROUTER_API_TOKEN", "")
    if not token:
        sys.exit("set ROUTER_API_TOKEN (printed by the notebook)")
    base = args.url.rstrip("/")

    rows = load_dataset(EVAL_ROOT / "datasets/routing/test.jsonl")
    random.Random(args.seed).shuffle(rows)
    need = 1 + args.warmup + args.n
    texts = [model_input(r, True) for r in (rows * (need // len(rows) + 1))[:need]]

    health, _ = call(f"{base}/health", token)
    ping = [call(f"{base}/health", token)[1] for _ in range(30)]
    result = {"label": args.label, "server": health, "n": args.n, "warmup": args.warmup,
              "ping_ms": stats(ping), "devices": {}}
    for device in health["devices"]:
        result["devices"][device] = bench_device(base, token, device, texts, args.warmup)

    out = EVAL_ROOT / "results/routing/setfit-latency" / f"{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    print(f"server: {health['gpu'] or 'no GPU'}, {health['cpu_count']} cpus, "
          f"torch {health['torch_threads']} threads; ping p50 {result['ping_ms']['p50']} ms")
    print(f"{'device':8}{'cold':>9}{'total p50':>11}{'p95':>8}{'server p50':>12}{'p95':>8}"
          f"{'network p50':>13}{'p95':>8}")
    for device, r in result["devices"].items():
        print(f"{device:8}{r['cold_ms']:>9}{r['total']['p50']:>11}{r['total']['p95']:>8}"
              f"{r['server']['p50']:>12}{r['server']['p95']:>8}{r['network']['p50']:>13}"
              f"{r['network']['p95']:>8}")
    print("wrote", out)


if __name__ == "__main__":
    main()
