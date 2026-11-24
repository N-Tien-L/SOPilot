import ast
import json
import sys

cells = []


def md(s):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)})


def code(s):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": s.strip("\n").splitlines(True)})


md("""
# LiquidAI d1-2B decision server (SOPilot routing experiment)

Serves `LiquidAI/d1-2B` (LFM Open License v1.0, 1.92B, open-weight "System One" decision model: calibrated
answers in one forward pass, no generated tokens, Vietnamese supported) on a Kaggle GPU behind a bearer
token, through a Cloudflare quick tunnel. The `/classify` contract is the same as the GLiNER2 server, so
`eval/sopilot_eval/routing_remote.py` and `routing_remote_tune.py` work unchanged; `/system_one` passes raw
questions through for metadata experiments (complexity, needs history).

**Kaggle settings:** Accelerator **GPU T4 x2** (one GPU is used), **Internet on**, notebook **private**.
A T4 has no native bf16, so the model runs in float16 (falls back to float32 automatically if the answers
are NaN) without `compile()` (it ran out of GPU memory on a T4).
Restart the session before running all cells, so no older model is still holding GPU memory. The model code is loaded with `trust_remote_code=True` (it runs inside this Kaggle session only).

Contract:
- `GET /health` -> `{model, device, dtype, versions}`
- `POST /classify` `{"texts", "tasks": {"intent": [phrase, ...]}, "instructions": {"intent": "..."}}`
  -> `{"results": [{"result": {"intent": {"label": phrase, "confidence": p, "probabilities": {...}}}, "server_ms"}]}`
- `POST /system_one` `{"texts", "questions": {...d1 question schema...}}` -> `{"results": [{"answers", "server_ms"}]}`

Only question texts are sent here; no SOP document goes to Kaggle.
""")

code("""
!pip install -q -U "transformers>=5.19" fastapi "uvicorn[standard]"
""")

code("""
import hmac, importlib.metadata, secrets, threading, time

import torch
from transformers import AutoModel

MODEL_ID = "LiquidAI/d1-2B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
NATIVE_BF16 = DEVICE == "cuda" and torch.cuda.get_device_capability()[0] >= 8
FORCE_DTYPE = "float16"  # T4: fast half precision; falls back to float32 below if answers are NaN
COMPILE = False  # model.compile() ran out of memory on a T4 (2026-11-17); try True only on a bigger GPU


def load(dtype):
    m = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True, dtype=dtype).to(DEVICE).eval()
    if COMPILE and hasattr(m, "compile"):
        try:
            m.compile()
        except Exception as exc:  # noqa: BLE001 - compile is an optimisation only
            print("compile skipped:", type(exc).__name__)
    return m


def gpu_gb():
    if DEVICE != "cuda":
        return "n/a"
    free, total = torch.cuda.mem_get_info()
    return f"{(total - free) / 2**30:.1f}/{total / 2**30:.1f} GB"


def answers_ok(m):
    try:
        return _answers_ok(m)
    except Exception as exc:  # noqa: BLE001 - e.g. a half-precision kernel error
        print("check failed:", type(exc).__name__, f"(GPU memory in use: {gpu_gb()})")
        return False


def _answers_ok(m):
    with torch.inference_mode():
        out = m.system_one("Quy trình xin nghỉ phép năm như thế nào?", {"intent": {
            "type": "choice", "criteria": {"a": "greeting", "b": "work question"},
            "instructions": "Which option best describes the message?"}})
    conf = out["answers"]["intent"].get("confidence")
    return conf is not None and conf == conf  # NaN != NaN


DTYPE = {"float16": torch.float16, "float32": torch.float32, "bfloat16": torch.bfloat16}.get(
    FORCE_DTYPE, torch.bfloat16 if NATIVE_BF16 else torch.float32)
if DEVICE == "cpu":
    DTYPE = torch.float32
import gc

gc.collect()
if DEVICE == "cuda":
    torch.cuda.empty_cache()
    print("GPU memory before load:", gpu_gb())  # should be near 0: otherwise restart the session
model = load(DTYPE)
if not answers_ok(model):
    print(DTYPE, "failed the check (error or NaN, see above): reloading in float32")
    del model
    torch.cuda.empty_cache()
    DTYPE = torch.float32
    model = load(DTYPE)
VERSIONS = {p: importlib.metadata.version(p) for p in ("transformers", "torch")}
print({"device": DEVICE, "dtype": str(DTYPE), "compile": COMPILE, "gpu_memory": gpu_gb(), **VERSIONS})
assert DEVICE == "cuda", "No GPU: Settings -> Accelerator -> GPU T4 x2, then restart the session"
""")

code("""
# Warm-up and a sanity check (Vietnamese, typo, abuse + question, off-topic).
DEFAULT_INSTRUCTIONS = {
    "intent": "A user wrote this message to a company assistant that answers questions about internal "
              "procedures (SOPs). Which option best describes the message?",
    "abuse": "Does the message contain rude words, insults or profanity?",
}
crit = {"greeting": "greeting or hello", "sop": "question about company procedures, rules or policies",
        "abuse_q": "insult or profanity together with a work question",
        "off_topic": "chit-chat or general knowledge unrelated to work"}
for text in ["xin chaof", "Quy trình xin nghỉ phép năm như thế nào?",
             "bot ngu vl, ai duyệt công tác phí?", "thời tiết hôm nay thế nào?"]:
    for _ in range(2):
        t0 = time.perf_counter()
        with torch.inference_mode():
            out = model.system_one(text, {"intent": {"type": "choice", "criteria": crit,
                                                     "instructions": DEFAULT_INSTRUCTIONS["intent"]}})
        ms = (time.perf_counter() - t0) * 1000
    print(f"{ms:7.1f} ms  {text!r} -> {out['answers']}")
""")

code("""
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

API_TOKEN = secrets.token_urlsafe(32)  # new per session; printed once below, never saved
LOCK = threading.Lock()  # one GPU, one model: requests run one at a time


class ClassifyRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=64)
    tasks: dict[str, list[str]]  # GLiNER2-style: {"task": [phrase, ...]}; each phrase is name and description
    instructions: dict[str, str] = {}
    include_confidence: bool = True  # accepted for client compatibility; confidence is always returned


class SystemOneRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=64)
    questions: dict


def check_token(authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization.encode(), f"Bearer {API_TOKEN}".encode()):
        raise HTTPException(status_code=401, detail="unauthorized")


def run_one(text, questions):
    t0 = time.perf_counter()
    try:
        with torch.inference_mode():
            out = model.system_one(text[:2000], questions)
    except Exception as exc:  # noqa: BLE001 - fixed message, the input is not echoed
        raise HTTPException(status_code=422, detail=f"system_one failed: {type(exc).__name__}")
    if DEVICE == "cuda":
        torch.cuda.synchronize()
    return out["answers"], round((time.perf_counter() - t0) * 1000, 2)


app = FastAPI()


@app.get("/health", dependencies=[Depends(check_token)])
def health():
    return {"model": MODEL_ID, "device": DEVICE, "dtype": str(DTYPE), "versions": VERSIONS,
            "include_confidence": True}


@app.post("/classify", dependencies=[Depends(check_token)])
def classify(req: ClassifyRequest):
    questions = {name: {"type": "choice", "criteria": {p: p for p in phrases},
                        "instructions": req.instructions.get(name) or DEFAULT_INSTRUCTIONS.get(
                            name, "Which option best describes the message?")}
                 for name, phrases in req.tasks.items()}
    results = []
    with LOCK:
        for text in req.texts:
            answers, ms = run_one(text, questions)
            result = {name: {"label": a.get("choice"), "confidence": float(a.get("confidence", 0.0)),
                             "probabilities": a.get("probabilities")} for name, a in answers.items()}
            results.append({"result": result, "server_ms": ms})
    return {"results": results, "model": MODEL_ID}


@app.post("/system_one", dependencies=[Depends(check_token)])
def system_one(req: SystemOneRequest):
    with LOCK:
        results = [dict(zip(("answers", "server_ms"), run_one(t, req.questions), strict=True)) for t in req.texts]
    return {"results": results, "model": MODEL_ID}
""")

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
print(f"  uv run python -m sopilot_eval.routing_remote --url {PUBLIC_URL} --split test --name d1-2b")
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
