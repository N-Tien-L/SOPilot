"""Thinking on vs off on the answer endpoint: time metrics and a small correctness check.

Why: the owner chose to trade some latency for reasoning power (2026-11-15). This measures the
trade on the real endpoint with the production prompt (``sopilot_ai.qa.prompt.build_prompt``), so
the numbers describe what a chat turn costs, not a toy prompt.

Run from ``services/ai-service`` (it imports the service's prompt builder; the endpoint URL, key
and model id come from the environment or flags, never from this file)::

    $env:PYTHONPATH = "src"
    uv run python ../../infrastructure/modal/bench_thinking.py --repeat 3 --json out.json

Warm the container first (a cold start takes minutes); the script also sends one uncounted warm-up
request and prints how long it took. Stdlib HTTP only, no new dependency.

Per request it records: ``first_token`` (any streamed token, reasoning included),
``first_answer`` (first token of the answer, what the user waits for without a dropdown),
``thinking`` (``first_answer`` minus ``first_token``), ``total``, completion tokens,
whether the output was cut by ``max_tokens`` (``finish_reason == "length"``), and whether the
answer passes the case's check (``must`` patterns all match, or for an unanswerable question
the answer says it was not found).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date

from sopilot_ai.providers.llm import ThinkSplitter, Thought
from sopilot_ai.qa.prompt import SourceText, build_prompt

SOURCES = [
    SourceText(n=1, title="quy-trinh-nghi-phep", page=2, code="QT-NS-01", rev="03", text=(
        "# 4. Bảng số ngày phép theo thâm niên\n"
        "Số ngày phép năm tăng theo thâm niên làm việc tại công ty, như bảng dưới đây. "
        "Mức thấp nhất là 12 ngày.\n\n"
        "| Thâm niên | Số ngày phép |\n| --- | --- |\n| Dưới 5 năm | 12 ngày |\n"
        "| Từ 5 đến 10 năm | 14 ngày |\n| Trên 10 năm | 16 ngày |\n\n"
        "Số ngày phép chưa sử dụng được chuyển sang quý đầu tiên của năm sau, tối đa 5 ngày. "
        "Phần vượt quá sẽ không được chuyển.")),
    SourceText(n=2, title="quy-trinh-nghi-phep", page=1, code="QT-NS-01", rev="03", text=(
        "Bước 1: nhân viên điền đơn xin nghỉ phép trên hệ thống nhân sự. Bước 2: quản lý trực "
        "tiếp xem xét và duyệt. Bước 3: phòng nhân sự xác nhận số ngày phép còn lại. Bước 4: "
        "nhân viên nhận thông báo kết quả qua thư điện tử. Quy trình này không áp dụng cho "
        "nhân viên thời vụ.")),
    SourceText(n=3, title="quy-trinh-nghi-phep", page=3, code="QT-NS-01", rev="03", text=(
        "Nhân viên đã hết phép năm có thể xin nghỉ không lương tối đa 30 ngày mỗi năm. Việc "
        "nghỉ không lương phải được giám đốc bộ phận phê duyệt bằng văn bản trước khi nghỉ.\n\n"
        "# 6. Nghỉ chế độ\nNghỉ cưới: 3 ngày làm việc có lương. Nghỉ tang: 3 ngày làm việc có "
        "lương khi người thân trực hệ qua đời. Các ngày nghỉ chế độ không tính vào số ngày phép "
        "năm. Đơn nghỉ phép và kết quả phê duyệt được lưu tại phòng nhân sự trong 5 năm kể từ "
        "ngày nghỉ.")),
]

NOT_FOUND = (r"không tìm thấy|không có thông tin|không đề cập|không nêu|không quy định|"
             r"could not find|couldn.t find|not found|no information")


@dataclass(frozen=True)
class Case:
    """One question. ``must`` patterns all match, ``forbid`` patterns never match; ``refuse``
    means the right answer is "not found". ``sources`` default to the leave-policy passages."""

    question: str
    lang: str
    must: tuple[str, ...] = ()
    refuse: bool = False
    forbid: tuple[str, ...] = ()
    sources: tuple[SourceText, ...] | None = None
    kind: str = "easy"


# --- hard set: answerable only by combining facts, applying an exception or a newer revision ----

EXPENSE = (
    SourceText(n=1, title="quy-trinh-cong-tac-phi", page=1, code="QT-TC-02", rev="02", text=(
        "# 2. Tạm ứng công tác phí\nHạn mức tạm ứng tối đa cho một chuyến công tác trong nước là "
        "5.000.000 đồng; chuyến công tác nước ngoài là 20.000.000 đồng. Khoản tạm ứng trên "
        "10.000.000 đồng phải được giám đốc tài chính phê duyệt; từ 10.000.000 đồng trở xuống do "
        "trưởng phòng phê duyệt.")),
    SourceText(n=2, title="quy-trinh-cong-tac-phi", page=2, code="QT-TC-02", rev="02", text=(
        "# 3. Quyết toán\nBáo cáo thanh toán phải nộp trong 7 ngày làm việc kể từ ngày kết thúc "
        "chuyến đi. Ngoại lệ: chuyến công tác nước ngoài được nộp trong 10 ngày làm việc. Nộp trễ "
        "sẽ bị khấu trừ vào lương kỳ kế tiếp. Khoản tạm ứng chưa quyết toán sau 30 ngày được khấu "
        "trừ toàn bộ vào lương.")),
    SourceText(n=3, title="quy-trinh-cong-tac-phi", page=3, code="QT-TC-02", rev="02", text=(
        "# 4. Phụ cấp ăn\nPhụ cấp ăn là 200.000 đồng mỗi ngày với chuyến đi trong nước và 50 USD "
        "mỗi ngày với chuyến đi nước ngoài. Nếu bữa ăn do đối tác đài thọ thì phụ cấp của ngày "
        "đó giảm 50%. Chuyến đi dưới 4 giờ không có phụ cấp ăn.")),
)

LEAVE_VERSIONS = (
    SourceText(n=1, title="quy-trinh-nghi-phep", page=2, code="QT-NS-01", rev="02",
               effective="2025-01-01", text=(
        "Số ngày phép chưa sử dụng được chuyển sang quý đầu tiên của năm sau, tối đa 3 ngày. "
        "Phiên bản này được thay thế khi có phiên bản mới hơn.")),
    SourceText(n=2, title="quy-trinh-nghi-phep", page=2, code="QT-NS-01", rev="03",
               effective="2026-01-15", text=(
        "Số ngày phép chưa sử dụng được chuyển sang quý đầu tiên của năm sau, tối đa 5 ngày. "
        "Quy trình này có hiệu lực từ ngày 15 tháng 1 năm 2026 và thay thế toàn bộ các quy định "
        "nghỉ phép trước đó.")),
)

EASY_CASES = [
    Case("Nhân viên làm việc 7 năm được bao nhiêu ngày phép năm?", "vi", (r"\b14\b",)),
    Case("Nhân viên làm đúng 5 năm thì được mấy ngày phép?", "vi", (r"\b14\b",)),
    Case("Tôi làm 11 năm và còn dư 8 ngày phép chưa dùng. Sang năm tôi tối đa có bao nhiêu ngày "
         "phép tính cả phần chuyển sang?", "vi", (r"\b21\b",)),
    Case("Ai phải duyệt đơn nghỉ không lương, và tối đa được nghỉ bao nhiêu ngày một năm?", "vi",
         (r"giám đốc bộ phận", r"\b30\b")),
    Case("How long are leave request records kept after the leave date?", "en", (r"\b5\b",)),
    Case("Nghỉ cưới có bị trừ vào số ngày phép năm không?", "vi", (r"không|not",)),
    Case("Quy định về nghỉ bù khi làm thêm giờ là gì?", "vi", refuse=True),
    Case("What is the overtime pay rate on public holidays?", "en", refuse=True),
]

HARD_CASES = [
    Case("Tôi đi công tác trong nước và tạm ứng 12 triệu đồng. Khoản này có vượt hạn mức không "
         "và ai phải duyệt?", "vi", (r"giám đốc tài chính", r"vượt|quá|5[.,]000[.,]000|5 triệu"),
         sources=EXPENSE, kind="hard"),
    Case("Chuyến công tác nước ngoài thì tôi có tối đa bao nhiêu ngày làm việc để nộp báo cáo "
         "thanh toán?", "vi", (r"\b10\b",), sources=EXPENSE, kind="hard"),
    Case("Tôi đi công tác nước ngoài 4 ngày, trong đó có 1 ngày đối tác đài thọ bữa ăn. Tổng "
         "phụ cấp ăn của tôi là bao nhiêu USD?", "vi", (r"\b175\b",), sources=EXPENSE,
         kind="hard"),
    Case("Tôi đi công tác trong nước 3 ngày, 1 trong 3 ngày đối tác đài thọ bữa ăn. Tổng phụ cấp "
         "ăn là bao nhiêu?", "vi", (r"500[.,]?000|500 nghìn|500k|0,5 triệu",), sources=EXPENSE,
         kind="hard"),
    Case("Tôi được chuyển tối đa bao nhiêu ngày phép chưa dùng sang năm sau?", "vi", (r"\b5\b",),
         sources=LEAVE_VERSIONS, kind="hard"),
    Case("Tôi làm đúng 10 năm, đã dùng hết phép năm và muốn nghỉ không lương 20 ngày. Tôi có "
         "được nghỉ không và cần ai duyệt?", "vi",
         (r"giám đốc bộ phận", r"được|có thể|đủ điều kiện"), kind="hard"),
    Case("Tạm ứng công tác bằng ngoại tệ thì được quy đổi theo tỷ giá nào?", "vi", refuse=True,
         sources=EXPENSE, kind="hard"),
    Case("Nếu tôi nộp báo cáo thanh toán trễ 3 ngày thì bị trừ bao nhiêu tiền lương?", "vi",
         refuse=True, sources=EXPENSE, kind="hard"),
    Case("If I advance 8 million VND for a domestic trip and do not settle it within 40 days, "
         "what happens?", "en", (r"deduct", r"\b30\b", r"5[.,]000[.,]000|5 million|5M"),
         sources=EXPENSE, kind="hard"),
    Case("Nhân viên thời vụ có được xin nghỉ phép năm theo quy trình này không?", "vi",
         (r"không",), forbid=(r"được phép xin nghỉ",), kind="hard"),
]

CASE_SETS = {"easy": EASY_CASES, "hard": HARD_CASES, "all": EASY_CASES + HARD_CASES}


def out(message: str = "") -> None:
    """One line of CLI output (flushed so a long run streams)."""
    sys.stdout.write(f"{message}\n")
    sys.stdout.flush()


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def _post(url: str, key: str, body: dict, timeout: float):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, json.dumps(body).encode(), headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - the owner's own endpoint


def run_one(base: str, key: str, model: str, messages: list[dict], thinking: bool,
            max_tokens: int, timeout: float) -> dict:
    body = {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens,
            "stream": True, "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": thinking}}
    t0 = time.perf_counter()
    first_any = first_answer = None
    reasoning, answer = [], []
    splitter = ThinkSplitter(thinking)  # the production splitter, so the numbers match it
    usage: dict = {}
    finish = None
    try:
        with _post(f"{base.rstrip('/')}/chat/completions", key, body, timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                obj = json.loads(data)
                usage = obj.get("usage") or usage
                if not obj.get("choices"):
                    continue
                choice = obj["choices"][0]
                finish = choice.get("finish_reason") or finish
                delta = choice.get("delta") or {}
                server_reasoning = delta.get("reasoning_content") or delta.get("reasoning") or ""
                content = delta.get("content") or ""
                now = time.perf_counter() - t0
                pieces: list[str] = []
                if server_reasoning:
                    splitter.server_parsed()
                    pieces.append(Thought(server_reasoning))
                if content:
                    pieces.extend(splitter.feed(content))
                if finish is not None:
                    pieces.extend(splitter.flush())
                for piece in pieces:
                    first_any = first_any if first_any is not None else now
                    if isinstance(piece, Thought):
                        reasoning.append(str(piece))
                    else:
                        first_answer = first_answer if first_answer is not None else now
                        answer.append(piece)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    total = time.perf_counter() - t0
    text = "".join(answer).strip()
    return {
        "thinking_on": thinking, "total": total, "first_token": first_any,
        "first_answer": first_answer, "completion_tokens": usage.get("completion_tokens"),
        "truncated": finish == "length", "answer": text, "reasoning_chars": len("".join(reasoning)),
        "answer_chars": len(text),
    }


def passes(case: Case, answer: str) -> bool:
    if case.refuse:
        return re.search(NOT_FOUND, answer, re.IGNORECASE) is not None
    if not answer or any(re.search(p, answer, re.IGNORECASE) for p in case.forbid):
        return False
    return all(re.search(p, answer, re.IGNORECASE) for p in case.must)


def summarize(label: str, rows: list[dict]) -> None:
    ok = [r for r in rows if "error" not in r]
    if not ok:
        out(f"{label}: no successful request")
        return

    def col(name: str) -> list[float]:
        return [r[name] for r in ok if r.get(name) is not None]

    def line(name: str, values: list[float], unit: str = "s") -> str:
        if not values:
            return f"{name:<14} no data"
        return (f"{name:<14} p50 {statistics.median(values):6.2f}{unit}  "
                f"p95 {_pct(values, 0.95):6.2f}{unit}  max {max(values):6.2f}{unit}")

    out(f"\n== {label}: {len(ok)} ok of {len(rows)} ==")
    out(line("first token", col("first_token")))
    out(line("first answer", col("first_answer")))
    out(line("total", col("total")))
    toks = col("completion_tokens")
    if toks:
        out(f"{'tokens':<14} p50 {statistics.median(toks):6.0f}   p95 {_pct(toks, 0.95):6.0f}   "
              f"max {max(toks):6.0f}")
    cut = sum(1 for r in ok if r["truncated"])
    right = sum(1 for r in ok if r["pass"])
    out(f"{'truncated':<14} {cut}/{len(ok)} hit max_tokens   correct {right}/{len(ok)}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base-url", default=os.environ.get("SOPILOT_LLM_BASE_URL", ""))
    ap.add_argument("--api-key", default=os.environ.get("SOPILOT_LLM_API_KEY", ""))
    ap.add_argument("--model", default=os.environ.get("SOPILOT_LLM_MODEL", ""))
    ap.add_argument("--repeat", type=int, default=2, help="runs per case and mode")
    ap.add_argument("--max-tokens", type=int, default=3000,
                    help="output ceiling, reasoning included (models.yaml uses 3000; try 6000 for "
                         "the hard set; the server context is 65536, ADR-011)")
    ap.add_argument("--set", dest="case_set", choices=sorted(CASE_SETS), default="all",
                    help="easy = lookups, hard = multi-step / exceptions / versions")
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--json", help="write every run (with answers) to this file")
    args = ap.parse_args()
    if not args.base_url or not args.model:
        out("Set SOPILOT_LLM_BASE_URL and SOPILOT_LLM_MODEL (or --base-url / --model).")
        return 2

    cases = CASE_SETS[args.case_set]

    def messages(case: Case) -> list[dict]:
        bundle = build_prompt(question=case.question, sources=case.sources or SOURCES,
                              lang=case.lang, today=date.today())
        return bundle.messages

    out(f"endpoint {args.base_url}  model {args.model}  set {args.case_set}  "
        f"max_tokens {args.max_tokens}  cases {len(cases)} x {args.repeat} x 2")
    warm = run_one(args.base_url, args.api_key, args.model, messages(cases[0]), False, 64,
                   args.timeout)
    out("warm-up (uncounted): " + (f"error {warm['error']}" if "error" in warm
                                   else f"{warm['total']:.1f}s"))

    rows: list[dict] = []
    for rep in range(args.repeat):
        for index, case in enumerate(cases):
            # off then on, alternating the order, so drift in the endpoint hits both modes alike
            order = (False, True) if (rep + index) % 2 == 0 else (True, False)
            for thinking in order:
                row = run_one(args.base_url, args.api_key, args.model, messages(case), thinking,
                              args.max_tokens, args.timeout)
                row.update(case=index, rep=rep, thinking_on=thinking, kind=case.kind,
                           question=case.question)
                if "error" not in row:
                    row["pass"] = passes(case, row["answer"])
                    fa = "  none" if row["first_answer"] is None else f"{row['first_answer']:5.1f}s"
                    out(f"[{rep}.{index}] {'ON ' if thinking else 'off'} "
                          f"first-answer {fa} "
                          f"total {row['total']:5.1f}s tokens {row['completion_tokens']} "
                          f"{'PASS' if row['pass'] else 'FAIL'}"
                          f"{' CUT' if row['truncated'] else ''}")
                else:
                    out(f"[{rep}.{index}] error {row['error']}")
                rows.append(row)

    for kind in sorted({c.kind for c in cases}):
        of_kind = [r for r in rows if r.get("kind") == kind]
        summarize(f"{kind}: thinking OFF", [r for r in of_kind if not r["thinking_on"]])
        summarize(f"{kind}: thinking ON", [r for r in of_kind if r["thinking_on"]])
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
        out(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
