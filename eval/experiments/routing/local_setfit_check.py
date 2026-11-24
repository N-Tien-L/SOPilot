"""Check the downloaded SetFit router on this machine's CPU: reproduction, latency, RAM.

Loads ``body/`` with sentence-transformers and applies ``head.npz`` with numpy
(``softmax(embedding @ coef.T + intercept)``), compares the probabilities with the ones the training
job returned for the frozen test split, then times one question at a time. Run from ``eval/``::

    uv run --extra local python experiments/routing/local_setfit_check.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sopilot_eval.routing import EVAL_ROOT, load_dataset
from sopilot_eval.routing_remote import model_input

RUN = EVAL_ROOT / "results/routing/setfit-bge-m3-pool447-hist-test"
MODEL = EVAL_ROOT / "results/routing/setfit-router-model/setfit-router"


def rss_mb() -> float:
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                    ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]

    kernel, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    c = Counters()
    c.cb = ctypes.sizeof(c)
    psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 2**20


def main() -> None:
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(int(os.environ.get("SETFIT_THREADS", "0")) or torch.get_num_threads())
    t0 = time.perf_counter()
    body = SentenceTransformer(str(MODEL / "body"), device="cpu")
    body.max_seq_length = 128
    head = np.load(MODEL / "head.npz")
    coef, intercept, classes = head["coef"], head["intercept"], head["classes"]
    print(f"load {time.perf_counter() - t0:.1f} s, RSS after load {rss_mb():.0f} MB, "
          f"threads {torch.get_num_threads()}")

    def proba(text: str) -> np.ndarray:
        emb = body.encode([text[:2000]], normalize_embeddings=False, convert_to_numpy=True)
        z = emb @ coef.T + intercept
        z -= z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return (e / e.sum(axis=1, keepdims=True))[0]

    test = load_dataset(EVAL_ROOT / "datasets/routing/test.jsonl")
    ref = {x["id"]: x for x in map(json.loads, (RUN / "per_question.jsonl").read_text(encoding="utf-8").splitlines())}
    texts = [model_input(r, True) for r in test]
    for t in texts[:3]:
        proba(t)  # warm-up
    ms: list[float] = []
    diffs, agree = [], 0
    for r, t in zip(test, texts, strict=True):
        s = time.perf_counter()
        p = proba(t)
        ms.append((time.perf_counter() - s) * 1000)
        want = np.array(ref[r["id"]]["proba"])
        got = np.zeros_like(want)
        got[classes] = p
        diffs.append(float(np.abs(got - want).max()))
        agree += int(got.argmax() == want.argmax())
    a = np.array(ms)
    print(f"rows {len(test)}; argmax agrees with the training job on {agree}; "
          f"max |dp| {max(diffs):.4f}, median {float(np.median(diffs)):.5f}")
    print(f"CPU latency ms: p50 {np.percentile(a, 50):.1f}, p95 {np.percentile(a, 95):.1f}, "
          f"mean {a.mean():.1f}, max {a.max():.1f}; peak RSS {rss_mb():.0f} MB")


if __name__ == "__main__":
    main()
