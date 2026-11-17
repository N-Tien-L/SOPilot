"""Tune a zero-shot router config on the routing **dev** split only (never on test).

For ``routing_remote``: greedy coordinate search over label wording (one intent at a time, keep the
variant that scores best), then a sweep of the confidence thresholds. One server pass per wording
(dev in batches of 64); thresholds are applied afterwards without new calls.

Score on dev = non-RAG questions routed correctly, **subject to zero costly errors** (no
``sop_question`` / ``followup`` routed away), the safe operating point; ties go to 14-class accuracy.
With 157 dev rows the search can still overfit a little: judge it on one test run.

Run from ``eval/``::

    $env:ROUTER_API_TOKEN = "<token>"
    uv run python -m sopilot_eval.routing_remote_tune --url https://<name>.trycloudflare.com --mode two_task
    uv run python -m sopilot_eval.routing_remote --url ... --config results/routing/gliner2-tune/two_task.json --name gliner2-two-task
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from typing import Any

from sopilot_eval.routing import EVAL_ROOT, EXPECTED, RAG, REPO_ROOT, load_dataset
from sopilot_eval.routing_remote import (
    DEFAULT_CONFIG,
    build_tasks,
    classify_batch,
    connect,
    decide,
    intent_labels,
    model_input,
)

# Index 0 is the first run's wording. English, Vietnamese and bilingual variants.
VARIANTS: dict[str, list[str]] = {
    "greeting": ["greeting or hello", "lời chào hỏi (greeting, hello)", "says hi"],
    "thanks": ["thanks or gratitude", "lời cảm ơn (thank you)", "says thank you"],
    "about_bot": ["question about the assistant itself", "hỏi về chatbot: bạn là ai, làm được gì",
                  "asks what the chatbot is or what it can do"],
    "abuse_only": ["insult or profanity with no question", "chỉ chửi bới, xúc phạm, không hỏi gì",
                   "only swearing at the bot"],
    "abuse_with_question": ["insult or profanity together with a work question",
                            "vừa chửi thề vừa hỏi công việc", "rude words plus a real work question"],
    "harmful": ["harmful or dangerous request", "yêu cầu nguy hiểm: tự hại, vũ khí, hack, chất độc",
                "self-harm, weapons, hacking or violence"],
    "followup": ["follow-up that refers to the previous message", "câu hỏi tiếp nối câu trước (cái đó, còn ... thì sao)",
                 "short follow-up like 'and that one?' or 'what about...'"],
    "sop_question": ["question about company procedures, rules or policies",
                     "câu hỏi về quy trình, quy định, chính sách công ty",
                     "workplace question: leave, expenses, approvals, hiring, safety, forms"],
    "off_topic": ["chit-chat or general knowledge unrelated to work", "chuyện ngoài công việc: thời tiết, thơ, kiến thức chung",
                  "weather, jokes, poems, sports or trivia"],
    "action_request": ["asks the assistant to perform an action", "nhờ bot làm việc giúp: gửi, duyệt, đặt, tạo",
                       "asks the bot to send, approve, book or submit something"],
    "personal_data": ["asks for another person's private data", "hỏi thông tin cá nhân của người khác: lương, số điện thoại, CCCD",
                      "asks for a colleague's salary, phone, ID or address"],
    "legal_medical": ["asks for legal advice or emergency medical help", "xin tư vấn pháp lý hoặc cấp cứu y tế",
                      "asks a lawyer-type or doctor-type question about their own case"],
    "about_source": ["asks where the previous answer came from", "hỏi nguồn của câu trả lời trước (tài liệu nào, trang nào)",
                     "asks which document or page the answer came from"],
    "feedback_in_chat": ["feedback about the previous answer", "nhận xét câu trả lời trước: sai rồi, hay quá",
                         "says the previous answer was wrong, good or unhelpful"],
}
ABUSE_VARIANTS: list[list[str]] = [
    ["contains insult or profanity", "polite or neutral"],
    ["có chửi thề, xúc phạm, từ thô tục", "lịch sự, bình thường"],
    ["rude: swearing, insults, vulgar slang (ngu, vl, đm, stupid)", "no rude words"],
]
CONF_GRID = [round(x * 0.05, 2) for x in range(19)]  # 0.00 .. 0.90
ABUSE_GRID = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


def score(rows: list[dict[str, Any]], results: list[dict[str, Any]], cfg: dict[str, Any]
          ) -> tuple[tuple[int, int], float, float]:
    """Best ``((routed_ok, intent_ok), min_conf, abuse_min)`` with zero costly errors on dev."""
    best: tuple[tuple[int, int], float, float] = ((-1, -1), 1.0, 0.5)
    abuse_grid = ABUSE_GRID if cfg["mode"] == "two_task" else [cfg["abuse_min_confidence"]]
    for am in abuse_grid:
        for mc in CONF_GRID:
            routed_ok = intent_ok = costly = 0
            for row, res in zip(rows, results, strict=True):
                intent, _, route = decide(res, cfg, min_confidence=mc, abuse_min_confidence=am)
                want = EXPECTED[row["intent"]]
                if row["intent"] in ("sop_question", "followup") and route != RAG:
                    costly += 1
                if want != RAG and route == want:
                    routed_ok += 1
                intent_ok += intent == row["intent"]
            if costly == 0 and (routed_ok, intent_ok) > best[0]:
                best = ((routed_ok, intent_ok), mc, am)
    return best


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--url", required=True)
    p.add_argument("--mode", choices=("single", "two_task"), default="two_task")
    p.add_argument("--with-history", action="store_true")
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--out-dir", default="gliner2-tune", help="folder under results/routing/")
    args = p.parse_args()

    base, token, _ = connect(args.url, args.timeout)
    rows = load_dataset(REPO_ROOT / "eval/datasets/routing/dev.jsonl")
    texts = [model_input(r, args.with_history) for r in rows]
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["mode"] = args.mode

    def evaluate(c: dict[str, Any]):
        return score(rows, classify_batch(base, token, texts, build_tasks(c), args.timeout), c)

    best = evaluate(cfg)
    print(f"start: routed_ok/intent_ok={best[0]} min_conf={best[1]} abuse_min={best[2]}", file=sys.stderr)
    for intent in intent_labels(cfg):
        for phrase in VARIANTS[intent][1:]:
            trial = copy.deepcopy(cfg)
            trial["phrases"] = {**cfg["phrases"], intent: phrase}
            got = evaluate(trial)
            if got[0] > best[0]:
                best, cfg = got, trial
                print(f"  {intent}: {phrase!r} -> {got[0]}", file=sys.stderr)
    if args.mode == "two_task":
        for pair in ABUSE_VARIANTS[1:]:
            trial = copy.deepcopy(cfg)
            trial["abuse_phrases"] = pair
            got = evaluate(trial)
            if got[0] > best[0]:
                best, cfg = got, trial
                print(f"  abuse: {pair!r} -> {got[0]}", file=sys.stderr)

    cfg["min_confidence"], cfg["abuse_min_confidence"] = best[1], best[2]
    cfg["tuned_on"] = {"split": "dev", "rows": len(rows), "routed_ok": best[0][0],
                       "non_rag_rows": sum(EXPECTED[r["intent"]] != RAG for r in rows),
                       "intent_ok": best[0][1], "costly": 0, "with_history": args.with_history}
    out = EVAL_ROOT / "results" / "routing" / args.out_dir / f"{args.mode}{'-hist' if args.with_history else ''}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(cfg["tuned_on"]), f"\nwrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
