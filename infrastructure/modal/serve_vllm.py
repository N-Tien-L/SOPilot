"""Modal deployment script for SOPilot V2 LLM endpoint.

Hosts Qwen/Qwen3.5-9B with vLLM on an NVIDIA A10 GPU (FP8 online quantization),
exposing OpenAI-compatible /v1/chat/completions and /v1/models endpoints.

References:
- Ticket: V2-34 (PLAN-V2-SOPILOT-MVP)
- ADR: ADR-006 §4.4 (Free tier providers & self-hosted open models on Modal)
- Design: TECH-V2-ai-service §4.2, §4.3
"""

import os
import subprocess
import sys

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
    .uv_pip_install(f"vllm=={VLLM_VERSION}")
    .env({"VLLM_LOG_STATS_INTERVAL": "1"})
)

# Persistent volumes for caching model weights and compilation artifacts.
hf_cache_vol = modal.Volume.from_name("sopilot-hf-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("sopilot-vllm-cache", create_if_missing=True)

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
    hf_cache_vol.commit()
    out("Download finished successfully.")


# -----------------------------------------------------------------------------
# vLLM Server Endpoint
# -----------------------------------------------------------------------------


@app.function(
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
    },
    # Fail closed: deploy is rejected when the secret or its key is missing, so
    # the public modal.run URL is never served without authentication.
    secrets=[modal.Secret.from_name(SECRET_NAME, required_keys=["VLLM_API_KEY"])],
)
@modal.concurrent(max_inputs=32)
@modal.web_server(port=PORT, startup_timeout=10 * 60)
def serve():
    """Launches the vLLM OpenAI-compatible server as a subprocess."""
    api_key = os.environ.get("VLLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("VLLM_API_KEY is empty; refusing to serve without authentication")

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
        "0.90",
        "--max-model-len",
        "8192",
        # The template defaults to thinking ON when the flag is absent.
        "--default-chat-template-kwargs",
        '{"enable_thinking": false}',
    ]

    # Log the command before appending the key so it never reaches Modal logs.
    out(f"Launching vLLM with command: {' '.join(cmd)} --api-key ***")
    subprocess.Popen([*cmd, "--api-key", api_key])
