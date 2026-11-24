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
# GLiNER2.5-multi-Decide intent server (SOPilot routing experiment)

Serves `fastino/GLiNER2.5-multi-Decide` (Apache-2.0, mDeBERTa-v3-base, ~287M) on a Kaggle GPU behind a
bearer token, and opens a public HTTPS URL with a Cloudflare quick tunnel (no account). The local client
`eval/sopilot_eval/routing_remote.py` calls it to measure accuracy and latency on the routing set.

**Kaggle settings (right panel):** Accelerator **GPU T4 x2** (one GPU is used), **Internet on** (needs a
phone-verified account), keep the notebook **private**. Run all cells in order and keep the session open
while the client runs. Quota counts wall-clock time: run the last cell and stop the session when done.

Contract:
- `GET /health` -> `{model, device, gliner2_version, include_confidence}`
- `POST /classify` `{"texts": [...], "tasks": {"intent": ["label a", ...]}, "include_confidence": true}`
  -> `{"results": [{"result": {...}, "server_ms": 12.3}], "model": ...}`

Only question texts are sent here; no SOP document goes to Kaggle.
''')

code('''
!pip install -q "gliner2[local]" fastapi "uvicorn[standard]"
''')

code('''
import hmac, importlib.metadata, inspect, secrets, threading, time

import torch
from gliner2 import AutoExtractor

MODEL_ID = "fastino/GLiNER2.5-multi-Decide"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

model = AutoExtractor.from_pretrained(MODEL_ID)


def move_to(obj, device):
    """AutoExtractor's device API is not documented: try the object, then its inner module."""
    for target in (obj, getattr(obj, "model", None)):
        if target is not None and hasattr(target, "to"):
            try:
                out = target.to(device)
                return (out or obj) if target is obj else obj
            except Exception as exc:  # noqa: BLE001
                print("move failed on", type(target).__name__, type(exc).__name__)
    return obj


def param_device(obj):
    for target in (obj, getattr(obj, "model", None)):
        params = getattr(target, "parameters", None)
        if callable(params):
            try:
                return str(next(params()).device)
            except StopIteration:
                pass
    return "unknown"


model = move_to(model, DEVICE)
ACTUAL_DEVICE = param_device(model)
SUPPORTS_CONFIDENCE = "include_confidence" in inspect.signature(model.classify_text).parameters
GLINER2_VERSION = importlib.metadata.version("gliner2")
print({"device": ACTUAL_DEVICE, "include_confidence": SUPPORTS_CONFIDENCE, "gliner2": GLINER2_VERSION})
''')

code('''
# Warm-up and a quick sanity check (Vietnamese, typo, abuse + question, off-topic).
labels = ["greeting or hello", "question about company procedures, rules or policies",
          "insult or profanity together with a work question",
          "chit-chat or general knowledge unrelated to work"]
for text in ["xin chaof", "Quy trình xin nghỉ phép năm như thế nào?",
             "bot ngu vl, ai duyệt công tác phí?", "thời tiết hôm nay thế nào?"]:
    t0 = time.perf_counter()
    out = model.classify_text(text, {"intent": labels})
    print(f"{(time.perf_counter() - t0) * 1000:7.1f} ms  {text!r} -> {out}")
''')

code('''
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

API_TOKEN = secrets.token_urlsafe(32)  # new per session; printed once below, never saved
LOCK = threading.Lock()  # one GPU, one model: requests run one at a time


class ClassifyRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=64)
    # GLiNER2 task schema: {"name": [labels]} or
    # {"name": {"labels": [...], "multi_label": true, "cls_threshold": 0.4}}
    tasks: dict
    include_confidence: bool = True


def check_token(authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization.encode(), f"Bearer {API_TOKEN}".encode()):
        raise HTTPException(status_code=401, detail="unauthorized")


app = FastAPI()


@app.get("/health", dependencies=[Depends(check_token)])
def health():
    return {"model": MODEL_ID, "device": ACTUAL_DEVICE, "gliner2_version": GLINER2_VERSION,
            "include_confidence": SUPPORTS_CONFIDENCE}


@app.post("/classify", dependencies=[Depends(check_token)])
def classify(req: ClassifyRequest):
    kwargs = {"include_confidence": True} if (req.include_confidence and SUPPORTS_CONFIDENCE) else {}
    results = []
    with LOCK:
        for text in req.texts:
            t0 = time.perf_counter()
            try:
                out = model.classify_text(text[:2000], req.tasks, **kwargs)
            except Exception as exc:  # noqa: BLE001 - fixed message, the input is not echoed
                raise HTTPException(status_code=422, detail=f"classify failed: {type(exc).__name__}")
            if DEVICE == "cuda":
                torch.cuda.synchronize()
            results.append({"result": out, "server_ms": round((time.perf_counter() - t0) * 1000, 2)})
    return {"results": results, "model": MODEL_ID}
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
# Keep draining cloudflared's log so its pipe never fills and blocks the tunnel.
threading.Thread(target=lambda: [None for _ in tunnel.stdout], daemon=True).start()

print("URL  :", PUBLIC_URL)
print("TOKEN:", API_TOKEN)
print()
print("On your machine (PowerShell, from eval/):")
print(f'  $env:ROUTER_API_TOKEN = "{API_TOKEN}"')
print(f"  uv run python -m sopilot_eval.routing_remote --url {PUBLIC_URL} --split test")
''')

md('''
Keep this session running while the client works. The tunnel URL and the token change every session.
A new quick tunnel can take 10-30 s before it answers.
''')

code('''
# Stop the tunnel and the server, then stop the Kaggle session to save GPU quota.
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
