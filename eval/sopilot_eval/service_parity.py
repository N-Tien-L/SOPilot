"""V2-09 acceptance: ai-service retrieval (through Postgres) vs this harness (TECH-V2-ai-service §6.5).

Same corpus, same docproc chunks, same bge-m3 vectors and the same configuration: every chunk the
harness indexes is written into a disposable pgvector database (real ``rag`` migrations, role
``sopilot_ai_app``, one workspace, one OWNER), then each question runs through
``sopilot_ai.retrieval.retriever.Retriever`` and through ``retrieve_candidates``. Reported: mean
top-10 Jaccard per configuration (target >= 0.95) and the questions below 1.0.

``doc_code_boost`` is set to 0 on the service side: the harness has no document-code step, and
§6.5 compares ranking, not that feature. Needs Docker and ``uv sync --extra local``.

Run: python -m sopilot_eval.service_parity --dataset datasets/sop-main \
        --config configs/rq1-rq3-bge-m3.yaml --split all
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import secrets
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import yaml

from .embedders import build_embedder
from .retrievers import Index, retrieve_candidates
from .run import ROOT, _chunk_key, _chunks_for, load_questions

REPO = ROOT.parent
IMAGE = "pgvector/pgvector:0.8.0-pg16"
TOP = 10
NAMESPACE = uuid.UUID("6f1c2b9e-6a43-4c55-9a43-0d3c1f7a2b10")


@contextmanager
def disposable_database():
    """pgvector on tmpfs with the repo's init scripts and rag migrations; removed afterwards."""
    import psycopg

    name = f"sopilot-parity-{uuid.uuid4().hex[:8]}"
    password = secrets.token_hex(16)
    init_dir = REPO / "infrastructure" / "db" / "init"
    subprocess.run([
        "docker", "run", "-d", "--rm", "--name", name, "--tmpfs", "/var/lib/postgresql/data",
        "-e", "POSTGRES_DB=sopilot", "-e", "POSTGRES_USER=postgres",
        "-e", f"POSTGRES_PASSWORD={password}", "-e", f"V2_DB_MIGRATOR_PASSWORD={password}",
        "-e", f"V2_DB_CORE_APP_PASSWORD={password}", "-e", f"V2_DB_AI_APP_PASSWORD={password}",
        "-v", f"{init_dir}:/docker-entrypoint-initdb.d:ro", "-p", "127.0.0.1::5432", IMAGE,
    ], check=True, capture_output=True)
    try:
        port = subprocess.run(["docker", "port", name, "5432/tcp"], check=True, capture_output=True,
                              text=True).stdout.splitlines()[0].rsplit(":", 1)[1]
        url = f"postgresql://{{role}}:{password}@127.0.0.1:{port}/sopilot"
        deadline = time.monotonic() + 90
        while True:
            try:
                psycopg.connect(url.format(role="sopilot_ai_app"), connect_timeout=2).close()
                break
            except psycopg.OperationalError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(1)
        with psycopg.connect(url.format(role="sopilot_migrator"), autocommit=True) as conn:
            conn.execute("CREATE SCHEMA rag")
            for path in sorted((REPO / "infrastructure/db/migrations/rag").glob("V*.sql")):
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
        yield url.format(role="sopilot_ai_app")
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


class _QueryEmbedder:
    """The harness embedder seen through the service's EmbeddingProvider interface."""

    name = "local"

    def __init__(self, inner, model: str, revision: str, dim: int) -> None:
        self.inner, self.model, self.revision, self.dim = inner, model, revision, dim

    def embed(self, texts, *, is_query: bool):
        return np.asarray(self.inner.embed(list(texts), is_query=is_query), dtype=np.float32)


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return 1.0 if not sa and not sb else len(sa & sb) / len(sa | sb)


async def _service_rankings(url: str, index: Index, embedder, emb_cfg: dict, questions: list[dict],
                            configs: list[dict]) -> tuple[dict[str, dict[str, list[str]]], dict]:
    from sqlalchemy import text

    from sopilot_ai.db.engine import make_engine, tenant_tx, vector_literal
    from sopilot_ai.providers.registry import RetrievalConfig
    from sopilot_ai.retrieval.access_filter import Principal
    from sopilot_ai.retrieval.retriever import Retriever

    model, revision = emb_cfg["model"], emb_cfg.get("revision") or "unpinned"
    engine = make_engine(url)
    ws = uuid.uuid4()
    try:
        keys = await _write_chunks(engine, ws, index, model, revision)
        owner = Principal(uuid.uuid4(), ws, "OWNER")
        qe = _QueryEmbedder(embedder, model, revision, index.matrix.shape[1])
        out: dict[str, dict[str, list[str]]] = {}
        plans: dict[str, str] = {}
        for conf in configs:
            cfg = RetrievalConfig(mode=conf["retriever"], candidate_pool=50, rerank_pool=25,
                                  rrf_weights=tuple(conf.get("weights", [1.0, 1.0])),
                                  rrf_k=conf.get("rrf_k", 60), doc_code_boost=0.0,
                                  cross_lingual_bm25_factor=float(
                                      conf.get("cross_lingual_bm25_factor", 1.0)))
            retriever = Retriever(qe, cfg)
            ranked: dict[str, list[str]] = {}
            for q in questions:
                async with tenant_tx(engine, ws, owner.user_id) as conn:
                    res = await retriever.retrieve(conn, owner, q["question"], query_lang=q.get("lang"))
                ranked[q["id"]] = [keys[c.chunk_id] for c in res.candidates[:TOP]]
            out[conf["name"]] = ranked
        async with tenant_tx(engine, ws) as conn:
            qvec = qe.embed([questions[0]["question"]], is_query=True)[0]
            await conn.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
            plan = (await conn.execute(text(
                "EXPLAIN SELECT id FROM rag.chunks WHERE workspace_id = :w "
                "ORDER BY embedding <=> CAST(:v AS vector) LIMIT 50"),
                {"w": ws, "v": vector_literal(qvec)})).scalars().all()
            plans["dense"] = "\n".join(plan)
        return out, plans
    finally:
        await engine.dispose()


async def _write_chunks(engine, ws: uuid.UUID, index: Index, model: str, revision: str) -> dict[uuid.UUID, str]:
    from sopilot_ai.db.engine import tenant_tx
    from sopilot_ai.db.repositories import access
    from sopilot_ai.db.repositories.ingest import ChunkRow, EmbeddingInfo, ExtractedRow, activate_version
    from sopilot_ai.retrieval.lexical import lexical_len, term_frequencies

    from .retrievers import chunk_text

    by_doc: dict[str, list[int]] = {}
    for i, c in enumerate(index.chunks):
        by_doc.setdefault(c.doc_id or c.doc, []).append(i)
    keys: dict[uuid.UUID, str] = {}
    info = EmbeddingInfo(provider="local", model=model, revision=revision, dim=int(index.matrix.shape[1]))
    for doc_key, idxs in by_doc.items():
        doc_id = uuid.uuid5(NAMESPACE, doc_key)
        ver_id = uuid.uuid5(NAMESPACE, doc_key + "#v1")
        rows = []
        for ordinal, i in enumerate(idxs):
            c = index.chunks[i]
            body = chunk_text(c)
            cid = uuid.uuid4()
            keys[cid] = _chunk_key(c)
            start = c.char_start if c.char_start is not None else ordinal
            end = c.char_end if c.char_end is not None else start + 1
            rows.append(ChunkRow(
                id=cid, ordinal=ordinal, chunk_type="SECTION", section_path=list(c.section_path),
                page_start=c.page, page_end=c.page_end, char_start=start, char_end=max(end, start + 1),
                content=c.text, index_text=body, lang=c.lang, token_count=0,
                content_sha256=hashlib.sha256(body.encode("utf-8")).digest(),
                embedding=index.matrix[i], lexical_len=lexical_len(body),
                terms=dict(term_frequencies(body))))
        extracted = ExtractedRow(structure={}, markdown="", page_index=None, warnings=[],
                                 normalizer_version="parity", page_count=None, language=None,
                                 doc_family="PROSE", boilerplate=[], extracted_meta={},
                                 extractor="eval-parity")
        async with tenant_tx(engine, ws) as conn:
            await access.upsert_access(conn, workspace_id=ws, document_id=doc_id, visibility="WORKSPACE",
                                       department_ids=[], access_revision=1, title=doc_key)
            ok = await activate_version(conn, workspace_id=ws, document_id=doc_id, version_id=ver_id,
                                        title=doc_key, extracted=extracted, chunks=rows, embedding=info)
            if not ok:
                raise RuntimeError(f"activation failed for {doc_key}")
    return keys


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m sopilot_eval.service_parity")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--split", default="all")
    parser.add_argument("--configs", default="dense,bm25,hybrid,hybrid-xl0.3",
                        help="comma-separated config names of the run config to compare")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "service-parity")
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    wanted = args.configs.split(",")
    configs = [c for c in cfg["configs"] if c["name"] in wanted]
    if {c["name"] for c in configs} != set(wanted):
        raise SystemExit(f"unknown config in {wanted}")
    emb_keys = {json.dumps(c["embedder"], sort_keys=True) for c in configs}
    if len(emb_keys) != 1 or any(c.get("rerank") for c in configs):
        raise SystemExit("compare configurations with one embedder and no rerank")
    emb_cfg = configs[0]["embedder"]

    questions, _, _ = load_questions(args.dataset, args.split)
    chunks, _ = _chunks_for(args.dataset, cfg.get("chunking", {}), emb_cfg)
    embedder = build_embedder(emb_cfg, ROOT / ".cache")
    index = Index(chunks, embedder)

    harness: dict[str, dict[str, list[str]]] = {}
    for conf in configs:
        harness[conf["name"]] = {
            q["id"]: [_chunk_key(index.chunks[c["idx"]])
                      for c in retrieve_candidates(index, q["question"], conf, None, pool=25,
                                                   query_lang=q.get("lang"))[:TOP]]
            for q in questions}

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    with disposable_database() as url:
        service, plans = asyncio.run(_service_rankings(url, index, embedder, emb_cfg, questions, configs))

    report = {"dataset": str(args.dataset), "split": args.split, "n_questions": len(questions),
              "n_chunks": len(chunks), "top": TOP, "target": 0.95, "dense_plan": plans.get("dense"),
              "configs": {}}
    for conf in configs:
        name = conf["name"]
        per_q = {qid: _jaccard(harness[name][qid], service[name][qid]) for qid in harness[name]}
        below = sorted((v, qid) for qid, v in per_q.items() if v < 1.0)
        report["configs"][name] = {
            "mean_jaccard": round(float(np.mean(list(per_q.values()))), 4),
            "min_jaccard": round(min(per_q.values()), 4),
            "identical_top10_order": sum(harness[name][q] == service[name][q] for q in per_q),
            "below_1": [{"id": qid, "jaccard": round(v, 4),
                         "harness": harness[name][qid], "service": service[name][qid]}
                        for v, qid in below],
        }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / (time.strftime("%Y%m%d-%H%M%S") + ".json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {name: {k: v for k, v in r.items() if k != "below_1"} | {"n_below_1": len(r["below_1"])}
               for name, r in report["configs"].items()}
    sys.stdout.write(json.dumps({"report": str(path), "configs": summary}, indent=2) + "\n")


if __name__ == "__main__":
    main()
