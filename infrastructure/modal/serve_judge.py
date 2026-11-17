"""Modal deployment script for the SOPilot V2 answer judge (V2-37 §2 D).

Hosts one Gemma 4 model with vLLM on an NVIDIA L40S (FP8 online quantization) behind the
OpenAI-compatible /v1/chat/completions endpoint. One file, parameterized by model: pick the model
with the JUDGE_MODEL environment variable at deploy time (`26b` or `31b`, default `26b`).

    $env:JUDGE_MODEL = "26b"; modal deploy infrastructure/modal/serve_judge.py

It is a separate app (`sopilot-judge-<key>`) from `serve_vllm.py`: no reranker, short context,
no sharing with the answer model, and it runs on the owner's second Modal account (the answer
model's account is not billed for the judge). Never point it at real internal documents: the
prompts leave the local machine.

References: ticket V2-37 §2 D, ADR-011 (serving profile), ADR-006 §4.4.
"""

import os
import subprocess
import sys

import modal

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
# Model keys and pinned Hugging Face revisions (looked up 2026-11-17; both repos are public,
# Apache-2.0 per the model card metadata). The BF16 checkpoints are quantized to FP8 at load.
MODELS = {
    "26b": ("google/gemma-4-26B-A4B-it", "4d7ae4984b7db7de8f8457170b3f1a419ee76d52"),
    "31b": ("google/gemma-4-31B-it", "842da3794eaa0b77d5f08bae87a17459d91ff475"),
}
JUDGE_KEY = os.environ.get("JUDGE_MODEL", "26b").strip().lower()
if JUDGE_KEY not in MODELS:
    raise SystemExit(f"JUDGE_MODEL must be one of {sorted(MODELS)}, got {JUDGE_KEY!r}")
MODEL_NAME, MODEL_REVISION = MODELS[JUDGE_KEY]

# Same pinned vLLM and CUDA image as serve_vllm.py, so the image layers are shared on the account.
VLLM_VERSION = "0.33.0"
CUDA_IMAGE = "nvidia/cuda:13.0.2-devel-ubuntu22.04"

GPU = "L40S"
# The judge prompt is question + sources + answer: well under 8K tokens.
MAX_MODEL_LEN = "8192"
MAX_NUM_SEQS = "8"
GPU_MEMORY_UTILIZATION = "0.90"
SCALEDOWN_WINDOW_S = 60  # V2-37 §2 D: 60 s idle, the judge runs in short bursts
PORT = 8000
SECRET_NAME = "sopilot-judge-secret"  # must define VLLM_API_KEY (on the judge account)


def out(message: str = "") -> None:
    """Writes one line of CLI/log output (stdout, flushed so Modal logs stream)."""
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


# -----------------------------------------------------------------------------
# Modal App & Container Image
# -----------------------------------------------------------------------------
app = modal.App(f"sopilot-judge-{JUDGE_KEY}")

# The container re-imports this module without the local environment, so the choice is baked
# into the image environment: the same JUDGE_KEY is seen on both sides.
judge_image = (
    modal.Image.from_registry(CUDA_IMAGE, add_python="3.12")
    .entrypoint([])
    .uv_pip_install(f"vllm=={VLLM_VERSION}")
    .env({"VLLM_LOG_STATS_INTERVAL": "1", "JUDGE_MODEL": JUDGE_KEY})
)

hf_cache_vol = modal.Volume.from_name("sopilot-judge-hf-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("sopilot-judge-vllm-cache", create_if_missing=True)
flashinfer_cache_vol = modal.Volume.from_name("sopilot-judge-flashinfer-cache", create_if_missing=True)


@app.function(
    image=judge_image,
    volumes={"/root/.cache/huggingface": hf_cache_vol},
    timeout=45 * 60,
)
def download_model():
    """Pre-caches the weights to the volume (CPU only, no GPU billed)."""
    from huggingface_hub import snapshot_download

    out(f"Downloading {MODEL_NAME} (revision: {MODEL_REVISION})...")
    snapshot_download(
        repo_id=MODEL_NAME,
        revision=MODEL_REVISION,
        ignore_patterns=["*.pt", "*.bin", "*.gguf"],  # safetensors only
    )
    hf_cache_vol.commit()
    out("Download finished successfully.")


def _launch_vllm(api_key: str) -> subprocess.Popen:
    cmd = [
        "vllm", "serve", MODEL_NAME,
        "--served-model-name", MODEL_NAME,
        "--revision", MODEL_REVISION,
        "--host", "0.0.0.0",
        "--port", str(PORT),
        "--quantization", "fp8",
        # Text-only judging: skip the vision/audio encoders.
        "--language-model-only",
        "--gpu-memory-utilization", GPU_MEMORY_UTILIZATION,
        "--max-model-len", MAX_MODEL_LEN,
        "--kv-cache-dtype", "fp8",  # V2-37 §2 D
        "--max-num-seqs", MAX_NUM_SEQS,
    ]
    # Log the command before appending the key so it never reaches Modal logs.
    out(f"Launching vLLM with command: {' '.join(cmd)} --api-key ***")
    return subprocess.Popen([*cmd, "--api-key", api_key])


@app.cls(
    image=judge_image,
    gpu=GPU,
    scaledown_window=SCALEDOWN_WINDOW_S,
    max_containers=1,  # one GPU at most: extra requests queue instead of billing a second one
    timeout=15 * 60,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
        "/root/.cache/flashinfer": flashinfer_cache_vol,
    },
    # Fail closed: the deploy is rejected when the secret or its key is missing.
    secrets=[modal.Secret.from_name(SECRET_NAME, required_keys=["VLLM_API_KEY"])],
)
@modal.concurrent(max_inputs=int(MAX_NUM_SEQS))
class Serve:
    @modal.enter()
    def start(self):
        api_key = os.environ.get("VLLM_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("VLLM_API_KEY is empty; refusing to serve without authentication")
        self.vllm = _launch_vllm(api_key)

    @modal.exit()
    def stop(self):
        proc = getattr(self, "vllm", None)
        if proc is not None:
            proc.terminate()

    @modal.web_server(port=PORT, startup_timeout=15 * 60, label=f"sopilot-judge-{JUDGE_KEY}")
    def chat(self):
        """OpenAI-compatible /v1/chat/completions and /v1/models (vLLM)."""
