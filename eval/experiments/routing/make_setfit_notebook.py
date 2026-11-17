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
# SetFit training server (SOPilot routing experiment)

Fine-tunes a sentence encoder with SetFit (contrastive pairs + logistic-regression head) on a Kaggle GPU.
The local client `eval/sopilot_eval/routing_setfit_remote.py` sends the training rows (dev split + router
exemplars, question texts only), starts a training job, polls it, then asks for class probabilities.
Training runs in a background job because a Cloudflare quick tunnel drops requests after about 100 s.

**Kaggle settings:** Accelerator **GPU T4 x2** (one GPU is used), **Internet on**, notebook **private**.
Run all cells, keep the session open while the client runs, then run the last cell and stop the session.

Contract (all need `Authorization: Bearer <token>`):
- `GET /health` -> versions and device
- `POST /train` `{"texts", "labels" (ints), "model_id", "num_iterations", "num_epochs", "batch_size", "max_seq_length", "seed"}` -> `{"job": id}`
- `GET /job/{id}` -> `{"state": "running|done|failed", "train_s", "error"}`
- `POST /predict` `{"job", "texts" (<=256)}` -> `{"classes", "results": [{"proba": [...], "server_ms"}]}`
- `POST /save` `{"job", "label_names"}` -> writes `/kaggle/working/setfit-router/` (`body/`, `head.npz`,
  `labels.json`, about 2.2 GB); download the files from the Output panel before stopping the session
''')

code('''
!pip install -q setfit fastapi "uvicorn[standard]"
''')

code('''
import hmac, importlib.metadata, os, secrets, threading, time, traceback, uuid

os.environ["WANDB_DISABLED"] = "true"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import torch
from datasets import Dataset
from setfit import SetFitModel, Trainer, TrainingArguments

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
VERSIONS = {p: importlib.metadata.version(p)
            for p in ("setfit", "sentence-transformers", "transformers", "torch", "scikit-learn")}
print(DEVICE, VERSIONS)
''')

code('''
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

API_TOKEN = secrets.token_urlsafe(32)  # new per session; printed once below, never saved
GPU = threading.Lock()  # one training or prediction at a time
JOBS = {}  # id -> {"state", "model", "train_s", "error"}


class TrainRequest(BaseModel):
    texts: list[str] = Field(min_length=2, max_length=5000)
    labels: list[int]
    model_id: str = "BAAI/bge-m3"
    num_iterations: int = Field(default=20, ge=1, le=100)
    num_epochs: int = Field(default=1, ge=1, le=5)
    batch_size: int = Field(default=16, ge=1, le=128)
    max_seq_length: int = Field(default=128, ge=16, le=512)
    seed: int = 42


class PredictRequest(BaseModel):
    job: str
    texts: list[str] = Field(min_length=1, max_length=256)


def check_token(authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization.encode(), f"Bearer {API_TOKEN}".encode()):
        raise HTTPException(status_code=401, detail="unauthorized")


def make_args(req):
    kwargs = dict(batch_size=req.batch_size, num_epochs=req.num_epochs, num_iterations=req.num_iterations,
                  seed=req.seed, use_amp=DEVICE == "cuda", report_to="none")
    try:
        return TrainingArguments(**kwargs)
    except TypeError:  # older setfit without report_to
        kwargs.pop("report_to")
        return TrainingArguments(**kwargs)


def train_job(job_id, req):
    job = JOBS[job_id]
    try:
        with GPU:
            t0 = time.perf_counter()
            model = SetFitModel.from_pretrained(req.model_id, device=DEVICE)
            model.model_body.max_seq_length = req.max_seq_length
            ds = Dataset.from_dict({"text": req.texts, "label": req.labels})
            Trainer(model=model, args=make_args(req), train_dataset=ds).train()
            job.update(model=model, state="done", train_s=round(time.perf_counter() - t0, 1))
    except Exception as exc:  # noqa: BLE001 - reported to the client as type + last frame only
        job.update(state="failed", error=f"{type(exc).__name__}: {traceback.format_exc(limit=-1)[-400:]}")
    finally:
        if DEVICE == "cuda":
            torch.cuda.empty_cache()


app = FastAPI()


@app.get("/health", dependencies=[Depends(check_token)])
def health():
    return {"device": DEVICE, "versions": VERSIONS, "jobs": len(JOBS)}


@app.post("/train", dependencies=[Depends(check_token)])
def train(req: TrainRequest):
    if len(req.texts) != len(req.labels):
        raise HTTPException(status_code=422, detail="texts and labels differ in length")
    for old in JOBS.values():  # keep one model in GPU memory: older ones are dropped
        old.pop("model", None)
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"state": "running"}
    threading.Thread(target=train_job, args=(job_id, req), daemon=True).start()
    return {"job": job_id}


@app.get("/job/{job_id}", dependencies=[Depends(check_token)])
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return {k: v for k, v in job.items() if k != "model"}


class SaveRequest(BaseModel):
    job: str
    label_names: list[str] = []


@app.post("/save", dependencies=[Depends(check_token)])
def save(req: SaveRequest):
    """Write the trained model to /kaggle/working/setfit-router for download from the Output panel.

    `body/` is a sentence-transformers folder (load it with SentenceTransformer, no setfit needed);
    `head.npz` holds the logistic-regression head as plain arrays (coef, intercept, classes), so the
    service can apply it with numpy: softmax(embedding @ coef.T + intercept).
    """
    import json as _json, shutil
    import numpy as np

    job = JOBS.get(req.job)
    if job is None or "model" not in job:
        raise HTTPException(status_code=404, detail="no trained model for this job")
    model, out = job["model"], "/kaggle/working/setfit-router"
    shutil.rmtree(out, ignore_errors=True)
    with GPU:
        model.model_body.save(f"{out}/body")
        head = model.model_head
        np.savez(f"{out}/head.npz", coef=head.coef_, intercept=head.intercept_, classes=head.classes_)
    with open(f"{out}/labels.json", "w", encoding="utf-8") as fh:
        _json.dump({"label_names": req.label_names, "classes": [int(c) for c in head.classes_],
                    "versions": VERSIONS, "job": req.job}, fh, indent=1)
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    return {"dir": out, "size_mb": round(size / 2**20, 1)}


@app.post("/predict", dependencies=[Depends(check_token)])
def predict(req: PredictRequest):
    job = JOBS.get(req.job)
    if job is None or "model" not in job:
        raise HTTPException(status_code=404, detail="no trained model for this job")
    model = job["model"]
    classes = [int(c) for c in model.model_head.classes_]
    results = []
    with GPU:
        for text in req.texts:  # one at a time: server_ms is the per-question latency
            t0 = time.perf_counter()
            proba = model.predict_proba([text[:2000]])
            if DEVICE == "cuda":
                torch.cuda.synchronize()
            ms = (time.perf_counter() - t0) * 1000
            results.append({"proba": [round(float(x), 5) for x in proba[0]], "server_ms": round(ms, 2)})
    return {"classes": classes, "results": results}
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
print(f"  uv run python -m sopilot_eval.routing_setfit_remote --url {PUBLIC_URL} --with-history --save")
''')

md('''
Keep this session running while the client works (about 15 min per configuration with bge-m3:
5 cross-validation trainings on dev to pick the threshold, then one final training and the test run).
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
