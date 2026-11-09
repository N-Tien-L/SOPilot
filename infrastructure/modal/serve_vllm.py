"""Modal deployment script for SOPilot V2 LLM endpoint.

Hosts Qwen/Qwen3.5-9B with vLLM on an NVIDIA A10 GPU (FP8 online quantization),
exposing OpenAI-compatible /v1/chat/completions and /v1/models endpoints.

References:
- Ticket: V2-34 (PLAN-V2-SOPILOT-MVP)
- ADR: ADR-006 §4.4 (Free tier providers & self-hosted open models on Modal)
- Design: TECH-V2-ai-service §4.2, §4.3
"""

import hmac
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import modal

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
# Constants, not environment variables: Modal re-imports this module inside the
# container, where local environment variables are not set, so an override
# would only change the local process and not the served model.

# Model identifier and pinned revision on Hugging Face (ADR-006 §4.4).
MODEL_NAME = "Qwen/Qwen3.5-9B"
MODEL_REVISION = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"

# Pinned vLLM release. It depends on torch 2.14 (CUDA 13 wheels), hence the
# CUDA 13 base image; flashinfer is pinned transitively by vLLM.
VLLM_VERSION = "0.33.0"
CUDA_IMAGE = "nvidia/cuda:13.0.2-devel-ubuntu22.04"

# GPU type. A10 (24 GB, ~600 GB/s) replaces L4 (24 GB, ~300 GB/s): decode is
# memory-bound and L4 measured 24.3 tokens/s (V2-34 §5). ADR-006 §4.4 allows A10.
GPU = "A10"

# Port exposed by vLLM web server.
PORT = 8000

# Reranker sharing the container and the GPU with vLLM (V2-35). Same model, revision and
# max_length as eval/configs/rq2-rerank-bge-m3.yaml, so scores are comparable with RQ2.
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
RERANK_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
RERANK_PORT = 8001
RERANK_MAX_LENGTH = 512
RERANK_MAX_PASSAGES = 64
RERANK_MAX_BODY_BYTES = 4 * 1024 * 1024
SENTENCE_TRANSFORMERS_VERSION = "6.2.0"  # same as services/ai-service/uv.lock

# vLLM share of GPU memory; the rest of the 24 GB A10 holds the reranker and its activations.
GPU_MEMORY_UTILIZATION = "0.85"

# Modal secret holding the Bearer key; it must define VLLM_API_KEY.
SECRET_NAME = "sopilot-vllm-secret"


def out(message: str = "") -> None:
    """Writes one line of CLI/log output (stdout, flushed so Modal logs stream)."""
    sys.stdout.write(message + "\n")
    sys.stdout.flush()

# -----------------------------------------------------------------------------
# Modal App & Container Image
# -----------------------------------------------------------------------------

app = modal.App("sopilot-vllm")

vllm_image = (
    modal.Image.from_registry(CUDA_IMAGE, add_python="3.12")
    .entrypoint([])
    .uv_pip_install(f"vllm=={VLLM_VERSION}", f"sentence-transformers=={SENTENCE_TRANSFORMERS_VERSION}")
    .env({"VLLM_LOG_STATS_INTERVAL": "1"})
)

# Persistent volumes for caching model weights and compilation artifacts.
hf_cache_vol = modal.Volume.from_name("sopilot-hf-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("sopilot-vllm-cache", create_if_missing=True)
# FlashInfer builds its sampling kernels with a JIT compiler on first use (minutes on an A10).
# Keeping ~/.cache/flashinfer on a volume lets later cold starts load the built module.
flashinfer_cache_vol = modal.Volume.from_name("sopilot-flashinfer-cache", create_if_missing=True)

# -----------------------------------------------------------------------------
# Optional Helper: Pre-download model weights into Volume
# -----------------------------------------------------------------------------


@app.function(
    image=vllm_image,
    volumes={"/root/.cache/huggingface": hf_cache_vol},
    timeout=30 * 60,
)
def download_model():
    """Pre-caches model weights to the Hugging Face volume (CPU only, no GPU billed)."""
    from huggingface_hub import snapshot_download

    out(f"Downloading model {MODEL_NAME} (revision: {MODEL_REVISION})...")
    snapshot_download(
        repo_id=MODEL_NAME,
        revision=MODEL_REVISION,
        ignore_patterns=["*.pt", "*.bin"],  # Safetensors only
    )
    out(f"Downloading reranker {RERANK_MODEL} (revision: {RERANK_REVISION})...")
    snapshot_download(
        repo_id=RERANK_MODEL,
        revision=RERANK_REVISION,
        ignore_patterns=["*.pt", "*.bin", "onnx/*", "*.onnx"],
    )
    hf_cache_vol.commit()
    out("Download finished successfully.")


# -----------------------------------------------------------------------------
# vLLM Server Endpoint
# -----------------------------------------------------------------------------


def _make_rerank_handler(model, api_key: str, lock: threading.Lock):
    """HTTP handler for POST /v1/rerank ({query, passages[]} -> {logits[]})."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # never log request lines: no key, no passage text
            return

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {api_key}"
            if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
                self._send(401, {"error": "unauthorized"})
                return
            if self.path.rstrip("/") != "/v1/rerank":
                self._send(404, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > RERANK_MAX_BODY_BYTES:
                    raise ValueError("length")
                data = json.loads(self.rfile.read(length))
                query, passages = data["query"], data["passages"]
                if (
                    not isinstance(query, str)
                    or not isinstance(passages, list)
                    or not passages
                    or len(passages) > RERANK_MAX_PASSAGES
                    or not all(isinstance(p, str) for p in passages)
                ):
                    raise ValueError("shape")
            except (ValueError, KeyError, TypeError):
                self._send(400, {"error": "bad_request"})
                return
            try:
                with lock:  # one batch on the GPU at a time
                    raw = model.predict(
                        [(query, p) for p in passages],
                        activation_fn=lambda x: x,  # raw logits; the client applies the sigmoid
                        batch_size=16,
                        show_progress_bar=False,
                    )
                self._send(200, {"logits": [float(x) for x in raw]})
            except Exception:  # noqa: BLE001 - fixed text; details stay out of the response
                self._send(500, {"error": "rerank_failed"})

    return Handler


def _watch_startup(started: float, torch_module) -> None:
    """Logs when vLLM answers /health, the GPU memory in use, and persists the FlashInfer cache."""
    deadline = started + 15 * 60
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5) as resp:
                if resp.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)
    else:
        out("startup: vLLM did not become healthy within 15 minutes")
        return
    out(f"startup: vLLM healthy {time.monotonic() - started:.0f} s after the container hook began")
    # Total in use (reranker + vLLM + CUDA contexts), then what this process (the reranker) holds.
    smi = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True, check=False,
    )
    out(f"startup: GPU memory used/total (nvidia-smi): {smi.stdout.strip() or smi.stderr.strip()}")
    out(
        "startup: reranker process torch allocated/reserved: "
        f"{torch_module.cuda.memory_allocated() / 2**30:.2f} / "
        f"{torch_module.cuda.memory_reserved() / 2**30:.2f} GiB"
    )
    try:
        flashinfer_cache_vol.commit()
        out("startup: FlashInfer cache volume committed")
    except Exception as exc:  # noqa: BLE001 - a failed commit only costs the next cold start
        out(f"startup: FlashInfer cache commit failed: {type(exc).__name__}")


def _launch_vllm(api_key: str) -> subprocess.Popen:
    """Launches the vLLM OpenAI-compatible server as a subprocess."""
    cmd = [
        "vllm",
        "serve",
        MODEL_NAME,
        "--served-model-name",
        MODEL_NAME,
        "--revision",
        MODEL_REVISION,
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT),
        # BF16 weights are ~19.3 GB; FP8 leaves room for KV cache. A10 (Ampere)
        # has no FP8 tensor cores, so vLLM runs weight-only FP8 (Marlin, W8A16).
        "--quantization",
        "fp8",
        # Text-only RAG: skip the vision encoder to save VRAM.
        "--language-model-only",
        "--gpu-memory-utilization",
        GPU_MEMORY_UTILIZATION,
        "--max-model-len",
        "8192",
        # The template defaults to thinking ON when the flag is absent.
        "--default-chat-template-kwargs",
        '{"enable_thinking": false}',
    ]

    # Log the command before appending the key so it never reaches Modal logs.
    out(f"Launching vLLM with command: {' '.join(cmd)} --api-key ***")
    return subprocess.Popen([*cmd, "--api-key", api_key])


@app.cls(
    image=vllm_image,
    gpu=GPU,
    scaledown_window=60,  # Scale-to-zero: idle for 60s -> terminate GPU container
    # One GPU at most: past 32 concurrent inputs requests queue instead of booting
    # (and billing) a second container with its own cold start.
    max_containers=1,
    timeout=15 * 60,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
        "/root/.cache/flashinfer": flashinfer_cache_vol,
    },
    # Fail closed: deploy is rejected when the secret or its key is missing, so
    # the public modal.run URL is never served without authentication.
    secrets=[modal.Secret.from_name(SECRET_NAME, required_keys=["VLLM_API_KEY"])],
)
@modal.concurrent(max_inputs=32)
class Serve:
    """One container, one A10: reranker on port 8001, vLLM on port 8000 (V2-35)."""

    @modal.enter()
    def start(self):
        api_key = os.environ.get("VLLM_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("VLLM_API_KEY is empty; refusing to serve without authentication")

        import torch
        from sentence_transformers import CrossEncoder

        started = time.monotonic()
        flashinfer_dir = "/root/.cache/flashinfer"
        cached = sum(len(files) for _, _, files in os.walk(flashinfer_dir))
        out(f"startup: FlashInfer cache volume holds {cached} files before launch")

        # Reranker first: vLLM sizes its KV cache from the memory that is still free.
        model = CrossEncoder(
            RERANK_MODEL, revision=RERANK_REVISION, device="cuda", max_length=RERANK_MAX_LENGTH
        )
        torch.cuda.synchronize()
        out(f"Reranker loaded; GPU memory allocated: {torch.cuda.memory_allocated() / 2**30:.2f} GiB")
        handler = _make_rerank_handler(model, api_key, threading.Lock())
        server = ThreadingHTTPServer(("0.0.0.0", RERANK_PORT), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()

        self.vllm = _launch_vllm(api_key)
        threading.Thread(target=_watch_startup, args=(started, torch), daemon=True).start()

    @modal.exit()
    def stop(self):
        proc = getattr(self, "vllm", None)
        if proc is not None:
            proc.terminate()

    # label keeps the V2-34 URL (<workspace>--sopilot-vllm-serve) unchanged.
    @modal.web_server(port=PORT, startup_timeout=10 * 60, label="sopilot-vllm-serve")
    def chat(self):
        """OpenAI-compatible /v1/chat/completions and /v1/models (vLLM)."""

    @modal.web_server(port=RERANK_PORT, startup_timeout=10 * 60, label="sopilot-vllm-rerank")
    def rerank(self):
        """POST /v1/rerank (same container and GPU as vLLM)."""
