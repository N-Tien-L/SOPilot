"""Score a remote zero-shot intent classifier on the routing set: accuracy and latency.

Built for the GLiNER2.5-multi-Decide server in ``eval/kaggle/gliner2_decide_server.ipynb`` (any
server with the same ``POST /classify`` contract works). It sends **one question per request**, as
the service would, and records two latencies per question:

- ``rtt_ms``: wall clock on this machine (network + tunnel + server), what a caller would feel;
- ``server_ms``: model time measured inside the server (the number to compare with a local model).

Scoring reuses ``sopilot_eval.routing`` (``EXPECTED``, ``summarize``), so per-label recall,
costly/cheap errors and the ``sop_question`` misroute rate mean exactly what they mean for the
rules and the semantic router. It also reports plain 14-class accuracy and the top confusions.

A **config** (JSON, ``--config``) decides how the model is asked and how its answer becomes a route:

- ``mode: "single"``: one ``intent`` task over the 14 intents;
- ``mode: "two_task"``: an ``abuse`` task (yes/no) plus an ``intent`` task without the two abuse
  intents, in one call; abuse + a question intent -> ``abuse_with_question``, abuse + anything else
  -> ``abuse_only`` (harmful stays harmful);
- ``phrases``: intent -> natural-language label (zero-shot models match wording, not ids);
- ``min_confidence``: below it a non-RAG prediction falls back to RAG (the safe default);
- ``abuse_phrases`` / ``abuse_min_confidence``: the abuse task's yes/no wording and cut-off.

``sopilot_eval.routing_remote_tune`` writes such a config from the **dev** split only.

The routing labels are pending owner review (``eval/datasets/routing/README.md``): treat numbers as
exploratory. Only the question texts (and ``previous_turn`` with ``--with-history``) leave this
machine; no corpus document is sent.

Run from ``eval/`` (the token comes from the notebook output; never commit it)::

    $env:ROUTER_API_TOKEN = "<token printed by the notebook>"
    uv run python -m sopilot_eval.routing_remote --url https://<name>.trycloudflare.com --split test
    uv run python -m sopilot_eval.routing_remote --url ... --config results/routing/gliner2-tune/two_task.json

Results go to ``eval/results/routing/<name>-<split>/`` (gitignored): ``metrics.json``,
``per_question.jsonl``, ``report.md``.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sopilot_eval.routing import (
    EVAL_ROOT,
    EXPECTED,
    LABELS,
    RAG,
    REPO_ROOT,
    Prediction,
    load_dataset,
    summarize,
)

DEFAULT_PHRASES: dict[str, str] = {
    "greeting": "greeting or hello",
    "thanks": "thanks or gratitude",
    "about_bot": "question about the assistant itself",
    "abuse_only": "insult or profanity with no question",
    "abuse_with_question": "insult or profanity together with a work question",
    "harmful": "harmful or dangerous request",
    "followup": "follow-up that refers to the previous message",
    "sop_question": "question about company procedures, rules or policies",
    "off_topic": "chit-chat or general knowledge unrelated to work",
    "action_request": "asks the assistant to perform an action",
    "personal_data": "asks for another person's private data",
    "legal_medical": "asks for legal advice or emergency medical help",
    "about_source": "asks where the previous answer came from",
    "feedback_in_chat": "feedback about the previous answer",
}
ABUSE_INTENTS = ("abuse_only", "abuse_with_question")
# Intents that carry a real question: with abuse they become abuse_with_question.
QUESTION_INTENTS = frozenset({"sop_question", "followup", "action_request", "personal_data",
                              "legal_medical", "about_source"})
DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "single", "phrases": DEFAULT_PHRASES, "min_confidence": 0.0,
    "abuse_phrases": ["contains insult or profanity", "polite or neutral"],
    "abuse_min_confidence": 0.5,
}
WARMUP = 3
BATCH = 64  # the server's per-request limit


def load_config(path: str | None) -> dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        cfg.update(json.loads(Path(path).read_text(encoding="utf-8")))
    intents = intent_labels(cfg)
    missing = set(intents) - set(cfg["phrases"])
    if missing:
        sys.exit(f"config phrases miss intents: {sorted(missing)}")
    if len({cfg["phrases"][i] for i in intents}) != len(intents):
        sys.exit("two intents share the same phrase")
    return cfg


def intent_labels(cfg: dict[str, Any]) -> tuple[str, ...]:
    """The intents the ``intent`` task chooses from in this mode."""
    if cfg["mode"] == "two_task":
        return tuple(i for i in LABELS if i not in ABUSE_INTENTS)
    return LABELS


def build_tasks(cfg: dict[str, Any]) -> dict[str, list[str]]:
    tasks = {"intent": [cfg["phrases"][i] for i in intent_labels(cfg)]}
    if cfg["mode"] == "two_task":
        tasks["abuse"] = list(cfg["abuse_phrases"])
    return tasks


def _label_conf(raw: Any) -> tuple[str | None, float]:
    item = raw[0] if isinstance(raw, list) and raw else raw
    if isinstance(item, dict):
        return item.get("label"), float(item.get("confidence", 1.0))
    return (item if isinstance(item, str) else None), 1.0


def decide(result: dict[str, Any], cfg: dict[str, Any], *, min_confidence: float | None = None,
           abuse_min_confidence: float | None = None) -> tuple[str, float, str]:
    """``(intent, confidence, route)`` from one server result under ``cfg``.

    The thresholds can be overridden so the tuner sweeps them without calling the server again.
    """
    min_conf = cfg["min_confidence"] if min_confidence is None else min_confidence
    abuse_min = cfg["abuse_min_confidence"] if abuse_min_confidence is None else abuse_min_confidence
    to_intent = {cfg["phrases"][i]: i for i in intent_labels(cfg)}
    label, conf = _label_conf(result.get("intent"))
    intent = to_intent.get(label or "", "unknown")
    if cfg["mode"] == "two_task" and intent != "harmful":
        a_label, a_conf = _label_conf(result.get("abuse"))
        if a_label == cfg["abuse_phrases"][0] and a_conf >= abuse_min:
            intent = "abuse_with_question" if intent in QUESTION_INTENTS else "abuse_only"
            conf = a_conf
    route = EXPECTED.get(intent, intent)
    if route != RAG and conf < min_conf:
        route = RAG  # not sure enough: answer through retrieval, as the service does today
    return intent, conf, route


def _request(url: str, token: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="GET" if payload is None else "POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {token}",
                                          "User-Agent": "sopilot-eval"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def connect(url: str, timeout: float) -> tuple[str, str, dict[str, Any]]:
    """``(base_url, token, health)``; exits with a plain message when the server is not usable."""
    token = os.environ.get("ROUTER_API_TOKEN", "")
    if not token:
        sys.exit("Set ROUTER_API_TOKEN to the token the notebook printed.")
    base = url.rstrip("/")
    try:
        health = _request(f"{base}/health", token, None, timeout)
    except urllib.error.HTTPError as exc:
        sys.exit(f"/health answered {exc.code}: check the token (401) or the URL (404, 530).")
    except (urllib.error.URLError, TimeoutError) as exc:
        sys.exit(f"cannot reach {base}: {type(exc).__name__}. Is the notebook session still running?")
    return base, token, health


def classify_batch(base: str, token: str, texts: Sequence[str], tasks: dict[str, list[str]],
                   timeout: float) -> list[dict[str, Any]]:
    """Results for many texts, ``BATCH`` per request (for tuning: latency is not measured)."""
    out: list[dict[str, Any]] = []
    for i in range(0, len(texts), BATCH):
        resp = _request(f"{base}/classify", token, {"texts": list(texts[i:i + BATCH]), "tasks": tasks,
                                                    "include_confidence": True}, timeout)
        out += [r["result"] for r in resp["results"]]
    return out


def model_input(row: dict[str, Any], with_history: bool) -> str:
    if with_history and row.get("previous_turn"):
        return f"Previous message: {row['previous_turn']}\nCurrent message: {row['text']}"
    return row["text"]


def _stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"n": 0, "mean": None, "p50": None, "p95": None, "max": None}
    data = sorted(values)
    q = statistics.quantiles(data, n=100, method="inclusive") if len(data) > 1 else [data[0]] * 99
    return {"n": len(data), "mean": round(statistics.fmean(data), 1), "p50": round(q[49], 1),
            "p95": round(q[94], 1), "max": round(data[-1], 1)}


def run(args: argparse.Namespace) -> dict[str, Any]:
    cfg = load_config(args.config)
    base, token, health = connect(args.url, args.timeout)
    tasks = build_tasks(cfg)
    rows = load_dataset(REPO_ROOT / f"eval/datasets/routing/{args.split}.jsonl")
    if args.limit:
        rows = rows[:args.limit]

    def classify(text: str) -> tuple[dict[str, Any], float]:
        start = time.perf_counter()
        out = _request(f"{base}/classify", token, {"texts": [text], "tasks": tasks,
                                                   "include_confidence": True}, args.timeout)
        return out, (time.perf_counter() - start) * 1000

    for _ in range(WARMUP):  # tunnel + CUDA warm-up, not counted
        classify("xin chào")

    per_q: list[dict[str, Any]] = []
    preds: list[Prediction] = []
    for i, row in enumerate(rows, 1):
        try:
            out, rtt = classify(model_input(row, args.with_history))
            item = out["results"][0]
            raw = item["result"]
            intent, conf, route = decide(raw, cfg)
            server_ms = float(item["server_ms"])
            error = None
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            intent, conf, route = "error", 0.0, "error"
            rtt, server_ms, raw, error = None, None, None, type(exc).__name__
        preds.append(Prediction(route, "remote", server_ms))
        per_q.append({"id": row["id"], "intent": row["intent"], "predicted": intent,
                      "confidence": round(conf, 4), "route": route,
                      "expected_route": EXPECTED[row["intent"]], "raw": raw, "rtt_ms": rtt,
                      "server_ms": server_ms, "error": error, "lang": row.get("lang"),
                      "unaccented": row.get("unaccented")})
        if i % 25 == 0:
            print(f"{i}/{len(rows)}", file=sys.stderr)  # progress on stderr; eval is not the service

    results = summarize(rows, preds)
    correct = sum(q["predicted"] == q["intent"] for q in per_q)
    confusions = Counter((q["intent"], q["predicted"]) for q in per_q if q["predicted"] != q["intent"])
    non_rag = [q for q in per_q if q["expected_route"] != RAG]
    results.update({
        "name": args.name, "split": args.split, "with_history": args.with_history,
        "server": {k: health.get(k) for k in ("model", "device", "gliner2_version")},
        "intent_accuracy": round(correct / len(per_q), 4) if per_q else None,
        "non_rag_routed_correctly": f"{sum(q['route'] == q['expected_route'] for q in non_rag)}/{len(non_rag)}",
        "errors_transport": sum(q["error"] is not None for q in per_q),
        "latency_ms": {"rtt": _stats([q["rtt_ms"] for q in per_q if q["rtt_ms"] is not None]),
                       "server": _stats([q["server_ms"] for q in per_q if q["server_ms"] is not None])},
        "top_confusions": [{"gold": g, "predicted": p, "n": n} for (g, p), n in confusions.most_common(15)],
        "config": cfg,
    })
    out_dir = EVAL_ROOT / "results" / "routing" / f"{args.name}-{args.split}{'-hist' if args.with_history else ''}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out_dir / "per_question.jsonl").open("w", encoding="utf-8") as fh:
        for q in per_q:
            fh.write(json.dumps(q, ensure_ascii=False) + "\n")
    (out_dir / "report.md").write_text(_report(results), encoding="utf-8")
    print(f"wrote {out_dir}", file=sys.stderr)
    return results


def _report(r: dict[str, Any]) -> str:
    lat = r["latency_ms"]
    cfg = r["config"]
    lines = [f"# {r['name']} on routing/{r['split']} (history: {r['with_history']})", "",
             f"Server: {r['server']}", "",
             (f"Config: mode={cfg['mode']}, min_confidence={cfg['min_confidence']}, "
              f"abuse_min_confidence={cfg['abuse_min_confidence']}"), "",
             f"- 14-class intent accuracy: {r['intent_accuracy']}",
             f"- non-RAG questions routed correctly: {r['non_rag_routed_correctly']}",
             (f"- sop_question routed away: {r['sop_question']['routed_away']}/{r['sop_question']['n']} "
              f"(rate {r['sop_question']['rate']:.3f}; acceptance <= 0.02: {r['acceptance']['passed']})"),
             (f"- costly / cheap / other: {r['errors']['costly']} / {r['errors']['cheap']} / "
              f"{r['errors']['other_misses']}"),
             f"- transport errors: {r['errors_transport']}",
             f"- latency rtt ms: {lat['rtt']}", f"- latency server ms: {lat['server']}", "",
             "| label | n | expected route | recall | precision |", "|---|---|---|---|---|"]
    for label, m in r["per_label"].items():
        rec = "-" if m["recall"] is None else f"{m['recall']:.2f}"
        pre = "-" if m["precision"] is None else f"{m['precision']:.2f}"
        lines.append(f"| {label} | {m['n']} | {m['expected_route']} | {rec} | {pre} |")
    lines += ["", "Top confusions (gold -> predicted):", ""]
    lines += [f"- {c['gold']} -> {c['predicted']}: {c['n']}" for c in r["top_confusions"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--url", required=True, help="public base URL printed by the notebook")
    p.add_argument("--split", choices=("dev", "test"), default="test")
    p.add_argument("--name", default="gliner2-decide", help="result folder prefix")
    p.add_argument("--config", help="JSON config (mode, phrases, thresholds); defaults = first run")
    p.add_argument("--with-history", action="store_true",
                   help="prepend previous_turn (followup / about_source rows) to the text")
    p.add_argument("--limit", type=int, default=0, help="first N rows only (smoke test)")
    p.add_argument("--timeout", type=float, default=60.0)
    args = p.parse_args()
    r = run(args)
    print(_report(r))


if __name__ == "__main__":
    main()
