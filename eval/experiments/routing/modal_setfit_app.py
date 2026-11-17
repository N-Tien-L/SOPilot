"""Modal worker for the SetFit router experiment (replaces the Kaggle server for training).

Self-contained on purpose: Modal re-imports this file inside the container, where ``sopilot_eval`` is not
installed. The local side is ``sopilot_eval/routing_setfit_remote.py --modal``, which sends one job per
cross-validation fold plus one final job and runs them in parallel on separate GPUs.

One job = train SetFit (same recipe and library versions as ``eval/kaggle/setfit_server.ipynb``) on the
given rows, then return class probabilities for ``predict_texts``. The final job predicts one question per
call (``per_question``) for latency and can write the model to the Modal Volume ``sopilot-setfit``::

    modal volume get sopilot-setfit setfit-router <local dir>
"""
from __future__ import annotations

import time
from typing import Any

import modal

MODEL_ID = "BAAI/bge-m3"
GPU = "A100-40GB"
VOLUME_NAME = "sopilot-setfit"
OUT_DIR = "/out/setfit-router"
# Versions the Kaggle run reported (metrics.json "server"), so results stay comparable.
VERSIONS = {"setfit": "1.2.0", "sentence-transformers": "5.7.0", "transformers": "5.20.2",
            "torch": "2.11.0", "scikit-learn": "1.6.1"}


def _download_model() -> None:
    from sentence_transformers import SentenceTransformer

    SentenceTransformer(MODEL_ID)  # bake the weights into the image: 6 containers must not each download


image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*(f"{name}=={version}" for name, version in VERSIONS.items()), "datasets", "numpy")
    .env({"WANDB_DISABLED": "true", "TOKENIZERS_PARALLELISM": "false", "HF_HOME": "/hf"})
    .run_function(_download_model)
)
app = modal.App("sopilot-setfit-router", image=image)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)


@app.function(gpu=GPU, timeout=3 * 3600, volumes={"/out": volume})
def train_predict(job: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    import torch
    from setfit import SetFitModel, Trainer, TrainingArguments

    from datasets import Dataset

    t0 = time.perf_counter()
    model = SetFitModel.from_pretrained(job["model_id"], device="cuda")
    model.model_body.max_seq_length = job["max_seq_length"]
    args = TrainingArguments(batch_size=job["batch_size"], num_epochs=job["num_epochs"],
                             num_iterations=job["num_iterations"], seed=job["seed"], use_amp=True,
                             report_to="none")
    ds = Dataset.from_dict({"text": job["texts"], "label": job["labels"]})
    Trainer(model=model, args=args, train_dataset=ds).train()
    train_s = round(time.perf_counter() - t0, 1)

    classes = [int(c) for c in model.model_head.classes_]
    texts = job["predict_texts"]
    probas: list[list[float]] = []
    ms: list[float] = []
    if job.get("per_question"):  # one at a time: ms is the per-question latency
        model.predict_proba(texts[:3])  # warm-up
        for text in texts:
            s = time.perf_counter()
            p = model.predict_proba([text[:2000]])
            torch.cuda.synchronize()
            ms.append(round((time.perf_counter() - s) * 1000, 2))
            probas.append([round(float(x), 5) for x in p[0]])
    elif texts:
        probas = [[round(float(x), 5) for x in row] for row in model.predict_proba([t[:2000] for t in texts])]

    saved = None
    if job.get("save"):
        import json
        import os
        import shutil

        shutil.rmtree(OUT_DIR, ignore_errors=True)
        model.model_body.save(f"{OUT_DIR}/body")
        head = model.model_head
        np.savez(f"{OUT_DIR}/head.npz", coef=head.coef_, intercept=head.intercept_, classes=head.classes_)
        with open(f"{OUT_DIR}/labels.json", "w", encoding="utf-8") as fh:
            json.dump({"label_names": job.get("label_names", []), "classes": classes,
                       "versions": VERSIONS, "model_id": job["model_id"]}, fh, indent=1)
        volume.commit()
        size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(OUT_DIR) for f in fs)
        saved = {"volume": VOLUME_NAME, "dir": "setfit-router", "size_mb": round(size / 2**20, 1)}
    return {"classes": classes, "probas": probas, "ms": ms, "train_s": train_s, "saved": saved,
            "gpu": torch.cuda.get_device_name(0)}
