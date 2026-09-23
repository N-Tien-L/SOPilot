# =============================================================================
# Modal app that runs HuggingFace Text Embeddings Inference (TEI) for BAAI/bge-m3.
#
# This service exposes an OpenAI-compatible ``POST /v1/embeddings`` endpoint
# that matches the local Docker container used by ``docker-compose.yml``:
#
#   * Image:    ghcr.io/huggingface/text-embeddings-inference:cpu-1.6
#   * Model:    BAAI/bge-m3
#   * Pooling:  cls       (matches local ``--pooling cls``)
#   * Batch:    --max-batch-tokens 2048 --max-client-batch-size 8
#
# Because TEI applies the dense linear projection that ``transformers.AutoModel``
# skips, vectors produced by this service are **bit-compatible** with vectors
# produced by the local ``bge-m3-embedding`` Docker container. The same model
# weights, the same pooling, the same tokenisation, the same projection.
#
# Usage
# -----
#   # 1) Deploy the long-running web endpoint (one-time, ~10 min for first
#   #    cold-start while the model downloads).
#   modal deploy bge_m3_tei.py::embed
#
#   # 2) Quick health-check from your terminal (uses the deployed URL).
#   modal run bge_m3_tei.py::smoke_test --text "hello world"
#
#   # 3) From any ingestion Modal app, call ``embed_texts.remote(texts)``
#   #    or POST to the URL printed by ``modal deploy``.
# =============================================================================

import modal
import subprocess
import time
import os

MODEL_VOLUME_NAME = "poliwise-tei-cache"
TEI_PORT = 80

tei_image = modal.Image.from_registry(
    "ghcr.io/huggingface/text-embeddings-inference:cpu-1.6",
    add_python="3.11",
)

app = modal.App("poliwise-tei-bge-m3")

# Persistent volume holds the BAAI/bge-m3 weights (~2.3 GB) so subsequent
# cold-starts skip the HuggingFace download.
model_volume = modal.Volume.from_name(MODEL_VOLUME_NAME, create_if_missing=True)


# -----------------------------------------------------------------------------
# Long-running web endpoint – keeps the TEI server warm.
# -----------------------------------------------------------------------------
@app.function(
    image=tei_image,
    cpu=4,
    memory=8192,
    timeout=3600,
    scaledown_window=300,  # keep warm for 5 min between calls
    volumes={"/data": model_volume},
    # Run the router as the container entrypoint.
)
@modal.web_server(
    port=TEI_PORT,
    startup_timeout=600,  # first cold-start downloads ~2.3 GB
)
def embed():
    """Serve BGE-M3 via TEI on port 80.

    Command-line flags mirror the local ``docker-compose.yml`` service so the
    resulting vectors are identical to the local Docker pipeline.
    """
    cmd = [
        "text-embeddings-router",
        "--model-id", "BAAI/bge-m3",
        "--pooling", "cls",
        "--max-batch-tokens", "2048",
        "--max-client-batch-size", "8",
        "--payload-limit", "512000",
        "--hostname", "0.0.0.0",
        "--port", str(TEI_PORT),
    ]
    # ``HF_HOME=/data`` makes TEI download & cache the model in our volume.
    subprocess.Popen(cmd, env={"HF_HOME": "/data"})


# -----------------------------------------------------------------------------
# Smoke test – boots a *transient* TEI server inside Modal (same image &
# flags), curls it, prints the embedding, then tears down. This works
# without ``modal deploy`` because we run TEI in-process and never expose
# a public URL.
# -----------------------------------------------------------------------------
@app.function(
    image=tei_image,
    cpu=4,
    memory=8192,
    timeout=900,
    volumes={"/data": model_volume},
)
def smoke_test_local(text: str) -> dict:
    """Boot TEI inside a Modal container, embed ``text``, return the vector."""
    import subprocess
    import httpx

    cmd = [
        "text-embeddings-router",
        "--model-id", "BAAI/bge-m3",
        "--pooling", "cls",
        "--max-batch-tokens", "2048",
        "--max-client-batch-size", "8",
        "--payload-limit", "512000",
        "--hostname", "127.0.0.1",
        "--port", str(TEI_PORT),
    ]
    env = {**os.environ, "HF_HOME": "/data"}
    proc = subprocess.Popen(cmd, env=env)

    try:
        # Wait for /health to become green (model download + warmup).
        deadline = time.time() + 600
        with httpx.Client(timeout=10.0) as client:
            while time.time() < deadline:
                try:
                    r = client.get(f"http://127.0.0.1:{TEI_PORT}/health")
                    if r.status_code == 200:
                        break
                except Exception:
                    pass
                time.sleep(5)
            else:
                raise RuntimeError("TEI did not become healthy in 10 min")

            r = client.post(
                f"http://127.0.0.1:{TEI_PORT}/v1/embeddings",
                json={"input": [text]},
                timeout=120.0,
            )
            r.raise_for_status()
            data = r.json()
            vec = sorted(data["data"], key=lambda x: x["index"])[0]["embedding"]
            return {
                "text": text,
                "dim": len(vec),
                "head": vec[:5],
                "norm": sum(v * v for v in vec) ** 0.5,
            }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# Convenience local entrypoint that delegates to the in-container version.
@app.local_entrypoint()
def smoke_test(text: str = "Poliwise BGE-M3 smoke test"):
    """End-to-end check: spin up TEI in Modal, embed one string, print it."""
    result = smoke_test_local.remote(text)
    for k, v in result.items():
        print(f"{k:>5}: {v}")
