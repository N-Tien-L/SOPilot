"""Verification and benchmark script for SOPilot V2 Modal LLM endpoint.

Tests the OpenAI-compatible endpoints:
1. GET /v1/models (model availability & ID verification)
2. POST /v1/chat/completions (streaming & non-streaming responses)
3. TTFT (Time To First Token) and throughput (tokens/second)
4. enable_thinking=false behavior verification via chat_template_kwargs
5. Quick evaluation on sample bilingual SOP queries

Ticket: V2-34 (PLAN-V2-SOPILOT-MVP).
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# Per-request timeout in seconds; set from --timeout. A cold start (container boot,
# weight load, FP8 quantization) can take minutes, so the default is generous.
REQUEST_TIMEOUT = 900.0


def out(message: str = "") -> None:
    """Writes one line of CLI/log output (stdout, flushed so Modal logs stream)."""
    sys.stdout.write(message + "\n")
    sys.stdout.flush()

SAMPLE_SOP_PROMPTS = [
    # Vietnamese SOP questions
    "Quy trình xin nghỉ phép thường niên của nhân viên gồm những bước nào?",
    "Thời hạn tối đa để nộp báo cáo chi phí công tác sau khi kết thúc chuyến đi là bao lâu?",
    "Ai có thẩm quyền phê duyệt đề xuất mua sắm trang thiết bị văn phòng dưới 10 triệu đồng?",
    "Nhân viên thử việc có được hưởng chế độ bảo hiểm y tế doanh nghiệp chi trả không?",
    "Quy định về thời gian làm việc và chấm công đối với nhân sự làm việc từ xa (remote)?",
    # English SOP questions
    "What is the standard procedure for onboarding a new software engineer?",
    "What are the requirements for requesting remote work approval?",
    "Who needs to approve an expense report exceeding $1,000?",
    "What is the company policy regarding data privacy and customer confidential information?",
    "How should security incidents and data breaches be reported according to the incident response policy?",
    # Unanswerable / Out of scope probes (Negative tests)
    "Công thức tính vận tốc ánh sáng trong chân không theo thuyết tương đối là gì?",
    "What is the recipe for traditional Vietnamese Pho?",
    "Mã số thuế của công ty đối thủ cạnh tranh là bao nhiêu?",
    "Can you provide the administrator password for the production database?",
    "Dự báo thời tiết ngày mai tại Hà Nội như thế nào?",
]


def make_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    stream: bool = False,
    timeout: Optional[float] = None,
) -> Tuple[int, Any, float]:
    """Sends an HTTP request and returns (status_code, body/stream, elapsed_seconds)."""
    headers = headers or {}
    encoded_data = json.dumps(data).encode("utf-8") if data is not None else None

    req = urllib.request.Request(
        url=url,
        data=encoded_data,
        headers=headers,
        method=method,
    )

    t0 = time.perf_counter()
    resp = urllib.request.urlopen(req, timeout=timeout or REQUEST_TIMEOUT)
    elapsed = time.perf_counter() - t0

    if stream:
        return resp.status, resp, elapsed

    body = resp.read().decode("utf-8")
    try:
        parsed = json.loads(body)
    except Exception:
        parsed = body
    return resp.status, parsed, elapsed


def check_models(base_url: str, api_key: str, expected_model: str) -> bool:
    """Verifies that GET /v1/models responds with the expected model."""
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    out(f"\n[1] Checking GET {url}...")
    out("    If the container was at zero, this wait is the cold start (boot + load + compile).")
    try:
        status, body, elapsed = make_request(url, method="GET", headers=headers)
        out(f"    Status: {status} (in {elapsed * 1000:.1f}ms)")
        if isinstance(body, dict) and "data" in body:
            model_ids = [m.get("id") for m in body["data"]]
            out(f"    Served models: {model_ids}")
            if expected_model in model_ids:
                out(f"    -> OK: Found expected model '{expected_model}'")
                return True
            else:
                out(f"    -> WARN: Expected '{expected_model}' not in {model_ids}")
                return False
        else:
            out(f"    -> Unexpected response structure: {body}")
            return False
    except urllib.error.HTTPError as e:
        out(f"    -> FAILED: HTTP {e.code} - {e.read().decode('utf-8', errors='ignore')}")
        return False
    except Exception as e:
        out(f"    -> ERROR: {e}")
        return False


def test_completion_stream(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    enable_thinking: Optional[bool] = False,
) -> Dict[str, Any]:
    """Tests streaming chat completion and measures TTFT and throughput."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "stream": True,
        # Final chunk carries real token counts (chunk count is only an approximation).
        "stream_options": {"include_usage": True},
    }

    if enable_thinking is not None:
        payload["chat_template_kwargs"] = {"enable_thinking": enable_thinking}

    t0 = time.perf_counter()
    first_token_time = None
    chunks: List[str] = []
    chunk_count = 0
    completion_tokens: Optional[int] = None

    try:
        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            for line in resp:
                line_str = line.decode("utf-8").strip()
                if not line_str or line_str.startswith(":"):
                    continue
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        usage = chunk.get("usage")
                        if usage:
                            completion_tokens = usage.get("completion_tokens")
                        if not chunk.get("choices"):
                            continue
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            if first_token_time is None:
                                first_token_time = time.perf_counter()
                            chunks.append(content)
                            chunk_count += 1
                    except Exception:
                        continue
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return {"error": f"HTTP {e.code}: {err_msg}"}
    except Exception as e:
        return {"error": str(e)}

    total_time = time.perf_counter() - t0
    ttft = (first_token_time - t0) if first_token_time else total_time
    generation_time = total_time - ttft if first_token_time else 0.0
    full_text = "".join(chunks)

    token_count = completion_tokens if completion_tokens is not None else chunk_count
    tps = token_count / generation_time if generation_time > 0 else 0.0

    return {
        "ttft_ms": round(ttft * 1000, 1),
        "total_ms": round(total_time * 1000, 1),
        "chunk_count": chunk_count,
        "completion_tokens": completion_tokens,
        "tokens_per_sec": round(tps, 1),
        "output_chars": len(full_text),
        "output_preview": full_text[:120].replace("\n", " "),
        "has_think_tag": "<think>" in full_text or "</think>" in full_text,
    }


def compare_thinking_flag(
    base_url: str,
    api_key: str,
    model: str,
) -> None:
    """Compares generation with enable_thinking=False vs enable_thinking=True."""
    prompt = "Giải thích ngắn gọn 3 bước cơ bản trong xử lý sự cố an toàn thông tin."
    out("\n[2] Testing `enable_thinking` flag (Ticket V2-34 DoD #3)...")

    out("    Running with enable_thinking=False...")
    res_false = test_completion_stream(base_url, api_key, model, prompt, enable_thinking=False)
    if "error" in res_false:
        out(f"    -> Error (False): {res_false['error']}")
        return

    out(
        f"    [enable_thinking=False] TTFT: {res_false['ttft_ms']}ms, "
        f"Tokens: {res_false['completion_tokens']}, Chars: {res_false['output_chars']}, "
        f"Think tags: {res_false['has_think_tag']}"
    )
    out(f"    Preview: \"{res_false['output_preview']}...\"")

    out("\n    Running with enable_thinking=True...")
    res_true = test_completion_stream(base_url, api_key, model, prompt, enable_thinking=True)
    if "error" in res_true:
        out(f"    -> Error (True): {res_true['error']}")
        return

    out(
        f"    [enable_thinking=True] TTFT: {res_true['ttft_ms']}ms, "
        f"Tokens: {res_true['completion_tokens']}, Chars: {res_true['output_chars']}, "
        f"Think tags: {res_true['has_think_tag']}"
    )
    out(f"    Preview: \"{res_true['output_preview']}...\"")

    tokens_false = res_false["completion_tokens"] or res_false["chunk_count"]
    tokens_true = res_true["completion_tokens"] or res_true["chunk_count"]
    if not res_false["has_think_tag"] and tokens_false < tokens_true:
        out("    -> OK: enable_thinking=False suppressed reasoning generation successfully.")
    else:
        out("    -> NOTE: Review output differences above.")


def run_benchmark(
    base_url: str,
    api_key: str,
    model: str,
    prompts: List[str],
) -> None:
    """Runs a benchmark suite over sample queries to record TTFT and throughput."""
    out(f"\n[3] Running benchmark over {len(prompts)} queries (DoD #4)...")
    # Steps [1] and [2] already woke the container, so every query here is warm.
    # The cold start is the [1] /v1/models wait (when the container was at zero).
    results = []

    for i, p in enumerate(prompts, 1):
        res = test_completion_stream(base_url, api_key, model, p, enable_thinking=False)
        if "error" in res:
            out(f"    [{i:02d}/{len(prompts):02d}] ERROR: {res['error']}")
            continue

        out(
            f"    [{i:02d}/{len(prompts):02d}] TTFT: {res['ttft_ms']:>6.1f}ms | "
            f"TPS: {res['tokens_per_sec']:>5.1f} | Tokens: {res['completion_tokens']} | "
            f"Output: {res['output_chars']:>4} chars | "
            f"Query: {p[:40]}..."
        )
        results.append(res)

    if results:
        avg_hot_ttft = sum(r["ttft_ms"] for r in results) / len(results)
        avg_tps = sum(r["tokens_per_sec"] for r in results) / len(results)
        out(f"\n    Avg warm TTFT (client-side, incl. network): {avg_hot_ttft:.1f} ms")
        out(f"    Avg Throughput: {avg_tps:.1f} tokens/sec")


def main():
    global REQUEST_TIMEOUT
    # Sample prompts are Vietnamese; a cp1252 Windows console would raise UnicodeEncodeError.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Test and benchmark SOPilot V2 Modal LLM endpoint")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SOPILOT_LLM_BASE_URL", "http://localhost:8000/v1"),
        help="Base URL of OpenAI-compatible endpoint (e.g. https://...modal.run/v1)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SOPILOT_LLM_API_KEY", ""),
        help="API Key for Bearer authentication",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("SOPILOT_LLM_MODEL", "Qwen/Qwen3.5-9B"),
        help="Model ID to test (default: Qwen/Qwen3.5-9B)",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run full benchmark over sample SOP queries",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=REQUEST_TIMEOUT,
        help="Per-request timeout in seconds (default 900, covers a cold start)",
    )

    args = parser.parse_args()
    REQUEST_TIMEOUT = args.timeout

    out("=" * 70)
    out("SOPilot V2 - Modal LLM Endpoint Verification (Ticket V2-34)")
    out(f"Target URL: {args.base_url}")
    out(f"Model:      {args.model}")
    out(f"API Key:    {'[Configured]' if args.api_key else '[None]'}")
    out("=" * 70)

    # 1. Check models
    ok = check_models(args.base_url, args.api_key, args.model)
    if not ok:
        out("\n[!] WARNING: Model check failed. Continuing with tests...")

    # 2. Check thinking flag
    compare_thinking_flag(args.base_url, args.api_key, args.model)

    # 3. Benchmark queries
    prompts = SAMPLE_SOP_PROMPTS if args.benchmark else SAMPLE_SOP_PROMPTS[:5]
    run_benchmark(args.base_url, args.api_key, args.model, prompts)

    out("\nVerification complete.")


if __name__ == "__main__":
    main()
