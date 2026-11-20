"""Build the Kaggle notebook that serves the trained SetFit router for the latency benchmark.

    uv run python experiments/routing/make_setfit_bench_notebook.py kaggle/setfit_bench_server.ipynb

The notebook loads the saved artifact (``body/``, ``head.npz``) the way ``qa/setfit_router.py`` does and
serves ``POST /classify`` on the CPU and, when the session has a GPU, on CUDA, behind a Cloudflare quick
tunnel. The local client ``bench_setfit_latency.py`` times the round trips.
"""
import ast
import json
import sys

cells = []


def md(s):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)})


def code(s):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": s.strip("\n").splitlines(True)})


md('''
# SetFit latency benchmark server (SOPilot routing, V2-44)

Serves the trained router (`body/` + `head.npz`) so the local client can time **classify + network**.

**Kaggle settings:** attach the dataset that holds the `setfit-router` folder (Add Input), **Internet on**,
notebook **private**. Accelerator **GPU T4 x2** gives a CUDA and a CPU run from one session (`device`
field of the request); pick **None** to measure the Kaggle CPU alone.

Contract (all need `Authorization: Bearer <token>`):
- `GET /health` -> device, torch threads, cpu count (also the pure network round trip, no model work)
- `POST /classify` `{"text", "device": "cpu" | "cuda"}` -> `{"label", "proba", "encode_ms", "server_ms"}`
''')

code('''
!pip install -q fastapi "uvicorn[standard]" sentence-transformers
''')

code('''
import glob, hmac, importlib.metadata, os, secrets, threading, time

os.environ["TOKENIZERS_PARALLELISM"] = "false"
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

heads = glob.glob("/kaggle/input/**/head.npz", recursive=True)
assert len(heads) == 1, f"expected one head.npz under /kaggle/input, found {heads}"
ROOT = os.path.dirname(heads[0])
head = np.load(heads[0], allow_pickle=False)
COEF = head["coef"].astype(np.float64)
INTERCEPT = head["intercept"].astype(np.float64).reshape(-1)

ENCODERS = {}
for dev in ["cpu"] + (["cuda"] if torch.cuda.is_available() else []):
    t0 = time.perf_counter()
    enc = SentenceTransformer(os.path.join(ROOT, "body"), device=dev)
    enc.max_seq_length = 128
    ENCODERS[dev] = enc
    print(f"loaded on {dev} in {time.perf_counter() - t0:.1f} s")
VERSIONS = {p: importlib.metadata.version(p) for p in ("sentence-transformers", "torch", "transformers")}
print(list(ENCODERS), VERSIONS, "cpu count", os.cpu_count(), "torch threads", torch.get_num_threads())
''')

code('''
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

API_TOKEN = secrets.token_urlsafe(32)  # new per session; printed once below, never saved
LOCK = threading.Lock()  # one encode at a time, like the service


def check_token(authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization.encode(), f"Bearer {API_TOKEN}".encode()):
        raise HTTPException(status_code=401, detail="unauthorized")


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    device: str = "cpu"


app = FastAPI()


@app.get("/health", dependencies=[Depends(check_token)])
def health():
    return {"devices": list(ENCODERS), "versions": VERSIONS, "cpu_count": os.cpu_count(),
            "torch_threads": torch.get_num_threads(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}


@app.post("/classify", dependencies=[Depends(check_token)])
def classify(req: ClassifyRequest):
    enc = ENCODERS.get(req.device)
    if enc is None:
        raise HTTPException(status_code=422, detail=f"device not available: {req.device}")
    with LOCK:
        t0 = time.perf_counter()
        emb = enc.encode([req.text], normalize_embeddings=False, convert_to_numpy=True)
        if req.device == "cuda":
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        z = np.asarray(emb, dtype=np.float64).reshape(1, -1) @ COEF.T + INTERCEPT
        z = z - z.max(axis=1, keepdims=True)
        p = (np.exp(z) / np.exp(z).sum(axis=1, keepdims=True))[0]
        t2 = time.perf_counter()
    best = int(np.argmax(p))
    return {"label": best, "proba": round(float(p[best]), 4),
            "encode_ms": round((t1 - t0) * 1000, 2), "server_ms": round((t2 - t0) * 1000, 2)}
''')

code('''
import uvicorn

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
time.sleep(3)
print("local server started:", server.started)
''')

code('''
# Public HTTPS URL through a Cloudflare quick tunnel (random *.trycloudflare.com name, no account).
import re, subprocess

!wget -q -O /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
!chmod +x /tmp/cloudflared

tunnel = subprocess.Popen(
    ["/tmp/cloudflared", "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8000"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
PUBLIC_URL = None
deadline = time.time() + 90
while time.time() < deadline and PUBLIC_URL is None:
    line = tunnel.stdout.readline()
    m = re.search(r"https://[a-z0-9-]+[.]trycloudflare[.]com", line)
    if m:
        PUBLIC_URL = m.group(0)
threading.Thread(target=lambda: [None for _ in tunnel.stdout], daemon=True).start()

print("URL  :", PUBLIC_URL)
print("TOKEN:", API_TOKEN)
print()
print("On your machine (PowerShell, from eval/):")
print(f'  $env:ROUTER_API_TOKEN = "{API_TOKEN}"')
print(f"  uv run python experiments/routing/bench_setfit_latency.py --url {PUBLIC_URL} --label kaggle-t4")
''')

md('''
Keep this session running while the client works (about 2 min). Then run the last cell and stop the session.
''')

code('''
tunnel.terminate()
server.should_exit = True
print("stopped")
''')

for c in cells:
    if c["cell_type"] == "code":
        ast.parse("".join(l for l in c["source"] if not l.lstrip().startswith("!")))

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}
with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as fh:
    json.dump(nb, fh, ensure_ascii=False, indent=1)
print("wrote", sys.argv[1], len(cells), "cells")
