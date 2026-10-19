"""Embedding providers behind one interface, with an on-disk cache keyed by (model, sha256(text))."""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

import numpy as np


def _normalize(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(n == 0, 1, n)


class Embedder:
    name = "base"

    def embed(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        raise NotImplementedError


class HashEmbedder(Embedder):
    """Deterministic lexical hashing embedder. Offline smoke tests ONLY, never report its numbers."""

    def __init__(self, dim: int = 512):
        self.dim = dim
        self.name = f"hash-{dim}"

    def embed(self, texts, is_query=False):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"\w+", t.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0 if (h >> 64) & 1 else -1.0
        return _normalize(out)


class SentenceTransformerEmbedder(Embedder):
    """Local model, e.g. BAAI/bge-m3. Pin `revision` (HF commit hash) for reproducibility."""

    def __init__(self, model: str, revision: str | None = None, query_prefix: str = "", batch_size: int = 16):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model, revision=revision)
        self.model.max_seq_length = min(self.model.max_seq_length or 512, 512)
        self.query_prefix = query_prefix
        self.batch_size = batch_size
        self.name = f"st:{model}@{revision or 'unpinned'}"

    def embed(self, texts, is_query=False):
        if is_query and self.query_prefix:
            texts = [self.query_prefix + t for t in texts]
        v = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(v, dtype=np.float32)


class OpenAICompatibleEmbedder(Embedder):
    """Any /v1/embeddings server (TEI, Ollama, ...)."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None, batch_size: int = 16):
        self.url = base_url.rstrip("/") + "/v1/embeddings"
        self.model, self.api_key, self.batch_size = model, api_key, batch_size
        self.name = f"openai:{model}"

    def embed(self, texts, is_query=False):
        rows = []
        for i in range(0, len(texts), self.batch_size):
            body = json.dumps({"input": texts[i : i + self.batch_size], "model": self.model}).encode()
            req = urllib.request.Request(self.url, body, {"Content-Type": "application/json"})
            if self.api_key:
                req.add_header("Authorization", f"Bearer {self.api_key}")
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)["data"]
            rows += [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]
        return _normalize(np.asarray(rows, dtype=np.float32))


class CachedEmbedder(Embedder):
    """Embed the corpus once; reuse across every retrieval configuration and rerun."""

    def __init__(self, inner: Embedder, cache_dir: Path):
        self.inner, self.name = inner, inner.name
        self.dir = cache_dir / hashlib.sha256(inner.name.encode()).hexdigest()[:16]
        self.dir.mkdir(parents=True, exist_ok=True)

    def _file(self, text: str) -> Path:
        return self.dir / (hashlib.sha256(text.encode()).hexdigest() + ".npy")

    def embed(self, texts, is_query=False):
        if is_query:
            return self.inner.embed(texts, is_query=True)
        vecs: list[np.ndarray | None] = []
        miss: list[int] = []
        for i, t in enumerate(texts):
            f = self._file(t)
            vecs.append(np.load(f) if f.exists() else None)
            if vecs[-1] is None:
                miss.append(i)
        if miss:
            new = self.inner.embed([texts[i] for i in miss])
            for i, v in zip(miss, new):
                np.save(self._file(texts[i]), v)
                vecs[i] = v
        return np.vstack(vecs)


def build_embedder(cfg: dict, cache_dir: Path) -> Embedder:
    kind = cfg["provider"]
    if kind == "hash":
        return HashEmbedder(cfg.get("dim", 512))
    if kind == "sentence-transformers":
        inner = SentenceTransformerEmbedder(cfg["model"], cfg.get("revision"), cfg.get("query_prefix", ""))
    elif kind == "openai":
        inner = OpenAICompatibleEmbedder(cfg["base_url"], cfg["model"], cfg.get("api_key"))
    else:
        raise ValueError(f"unknown embedder provider: {kind}")
    return CachedEmbedder(inner, cache_dir)
