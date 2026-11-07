"""RQ4: what does row-level security cost on the retrieval path? (V2-14, PRD-V2 §RQ4, ADR-005)

Same data, same queries, two connections:

* ``app-filter``  superuser connection. RLS is bypassed, so only the application's own
                  ``workspace_id = :wid`` + access filter applies (layer 1 of ADR-005).
* ``app+rls``     ``sopilot_ai_app`` connection with ``app.workspace_id`` set per transaction, exactly how
                  ai-service runs. The same SQL, plus the RLS policy on every table it touches (layers 1 + 2).

Each measured unit is one retrieval transaction: ``search.dense`` then ``search.bm25`` of ai-service, the
real functions, in one ``tenant_tx``. Queries are interleaved (alternating which mode goes first) after a
warm-up, and the top-k of both modes are compared so a latency win can never hide a different answer.

The corpus is synthetic (random unit vectors, Zipf-distributed terms) because this measures the database
path, not retrieval quality; chunk counts per workspace and the number of workspaces are options. It runs
in a disposable container and needs no model, network or ``.env``.

    cd eval && uv run python rq4_rls_latency.py --workspaces 5 --chunks 2000 --queries 300
"""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import secrets
import selectors
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg

REPO = Path(__file__).resolve().parents[1]
IMAGE = "pgvector/pgvector:0.8.0-pg16"
DIM = 1024
MODEL, REVISION = "rq4-synthetic", "r1"
CHUNKS_PER_DOCUMENT = 20


@dataclass(frozen=True)
class Db:
    port: int
    password: str

    def url(self, role: str) -> str:
        return f"postgresql://{role}:{self.password}@127.0.0.1:{self.port}/sopilot"


def start_database() -> tuple[str, Db]:
    if shutil.which("docker") is None or subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        sys.exit("Docker is required")
    name = f"sopilot-rq4-{uuid.uuid4().hex[:8]}"
    password = secrets.token_hex(16)
    subprocess.run([
        "docker", "run", "-d", "--rm", "--name", name, "--tmpfs", "/var/lib/postgresql/data",
        "-e", "POSTGRES_DB=sopilot", "-e", "POSTGRES_USER=postgres", "-e", f"POSTGRES_PASSWORD={password}",
        "-e", f"V2_DB_MIGRATOR_PASSWORD={password}", "-e", f"V2_DB_CORE_APP_PASSWORD={password}",
        "-e", f"V2_DB_AI_APP_PASSWORD={password}",
        "-v", f"{REPO / 'infrastructure/db/init'}:/docker-entrypoint-initdb.d:ro", "-p", "127.0.0.1::5432", IMAGE,
    ], check=True, capture_output=True)
    port_line = subprocess.run(["docker", "port", name, "5432/tcp"], check=True, capture_output=True,
                               text=True).stdout.splitlines()[0]
    db = Db(int(port_line.rsplit(":", 1)[1]), password)
    deadline = time.monotonic() + 120
    while True:
        try:
            psycopg.connect(db.url("sopilot_ai_app"), connect_timeout=2).close()
            break
        except psycopg.OperationalError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)
    with psycopg.connect(db.url("sopilot_migrator"), autocommit=True) as conn:
        conn.execute("CREATE SCHEMA rag")
        for path in sorted((REPO / "infrastructure/db/migrations/rag").glob("V*.sql")):
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
    return name, db


def unit_vectors(rng: np.random.Generator, n: int) -> np.ndarray:
    v = rng.standard_normal((n, DIM)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def vec_text(v: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.6g}" for x in v.tolist()) + "]"


def seed(db: Db, workspaces: list[uuid.UUID], chunks: int, vocab: int, rng: np.random.Generator) -> None:
    """Workspaces x chunks rows via COPY as superuser (RLS is bypassed, so seeding is not what is measured)."""
    zipf = 1.0 / np.arange(1, vocab + 1)
    zipf /= zipf.sum()
    with psycopg.connect(db.url("postgres"), autocommit=True) as conn:
        for wi, wid in enumerate(workspaces):
            docs = [(uuid.uuid4(), uuid.uuid4()) for _ in range(max(1, chunks // CHUNKS_PER_DOCUMENT))]
            vectors = unit_vectors(rng, chunks)
            with conn.cursor() as cur:
                with cur.copy("COPY rag.document_access (workspace_id, document_id, visibility, access_revision, "
                              "active_version_id, title) FROM STDIN") as cp:
                    for doc, ver in docs:
                        cp.write_row((wid, doc, "WORKSPACE", 1, ver, f"doc-{wi}-{doc.hex[:6]}"))
                chunk_ids = [uuid.uuid4() for _ in range(chunks)]
                with cur.copy("COPY rag.chunks (id, workspace_id, document_id, version_id, ordinal, chunk_type, "
                              "section_path, char_start, char_end, content, index_text, token_count, "
                              "content_sha256, embedding, embedding_provider, embedding_model, embedding_dim, "
                              "embedding_revision, lexical_len) FROM STDIN") as cp:
                    for i, cid in enumerate(chunk_ids):
                        doc, ver = docs[i % len(docs)]
                        cp.write_row((cid, wid, doc, ver, i, "PROSE", "{1}", 0, 100, "c", "c", 30,
                                      secrets.token_bytes(32), vec_text(vectors[i]), "local", MODEL, DIM,
                                      REVISION, 30))
                with cur.copy("COPY rag.chunk_terms (workspace_id, chunk_id, term, tf) FROM STDIN") as cp:
                    for cid in chunk_ids:
                        for term in np.unique(rng.choice(vocab, size=30, p=zipf)):
                            cp.write_row((wid, cid, f"t{term}", int(rng.integers(1, 4))))
        conn.execute("ANALYZE rag.chunks")
        conn.execute("ANALYZE rag.chunk_terms")
        conn.execute("ANALYZE rag.document_access")


def percentile(values: list[float], p: float) -> float:
    return float(np.percentile(np.asarray(values), p))


def summarize(ms: list[float]) -> dict[str, float]:
    return {"n": len(ms), "mean": round(statistics.fmean(ms), 3), "p50": round(percentile(ms, 50), 3),
            "p95": round(percentile(ms, 95), 3), "p99": round(percentile(ms, 99), 3), "max": round(max(ms), 3)}


async def run(args: argparse.Namespace) -> dict:
    from sopilot_ai.db.engine import make_engine, tenant_tx
    from sopilot_ai.retrieval import search
    from sopilot_ai.retrieval.access_filter import Principal

    rng = np.random.default_rng(args.seed)
    container, db = start_database()
    try:
        workspaces = [uuid.uuid4() for _ in range(args.workspaces)]
        t0 = time.perf_counter()
        seed(db, workspaces, args.chunks, args.vocab, rng)
        seed_s = time.perf_counter() - t0

        engines = {"app-filter": make_engine(db.url("postgres")), "app+rls": make_engine(db.url("sopilot_ai_app"))}
        queries = [(workspaces[i % len(workspaces)], unit_vectors(rng, 1)[0],
                    [f"t{t}" for t in rng.choice(args.vocab, size=4, replace=False)])
                   for i in range(args.queries + args.warmup)]
        user = uuid.uuid4()

        async def one(mode: str, wid: uuid.UUID, qvec: np.ndarray, terms: list[str]):
            principal = Principal(user, wid, "MEMBER", None)
            t = time.perf_counter()
            async with tenant_tx(engines[mode], wid, user) as conn:
                t1 = time.perf_counter()
                dense = await search.dense(conn, principal, qvec, model=MODEL, revision=REVISION, pool=args.pool)
                t2 = time.perf_counter()
                bm25 = await search.bm25(conn, principal, terms, pool=args.pool)
                t3 = time.perf_counter()
            return {"dense": (t2 - t1) * 1000, "bm25": (t3 - t2) * 1000, "total": (t3 - t) * 1000,
                    "ids": ([h.chunk_id for h in dense[:args.k]], [h.chunk_id for h in bm25[:args.k]])}

        samples: dict[str, dict[str, list[float]]] = {m: {"dense": [], "bm25": [], "total": []} for m in engines}
        mismatches = 0
        for i, (wid, qvec, terms) in enumerate(queries):
            order = list(engines) if i % 2 == 0 else list(reversed(list(engines)))
            results = {}
            for mode in order:
                results[mode] = await one(mode, wid, qvec, terms)
            if i >= args.warmup:
                for mode, r in results.items():
                    for key in ("dense", "bm25", "total"):
                        samples[mode][key].append(r[key])
                if results["app-filter"]["ids"] != results["app+rls"]["ids"]:
                    mismatches += 1

        # Foreign rows must be invisible in both modes (the filter is in the SQL), so this guards the setup.
        stranger = uuid.uuid4()
        async with tenant_tx(engines["app+rls"], stranger, user) as conn:
            leaked = len(await search.dense(conn, Principal(user, stranger, "MEMBER", None), queries[0][1],
                                            model=MODEL, revision=REVISION, pool=args.pool))
        for e in engines.values():
            await e.dispose()

        modes = {m: {k: summarize(v) for k, v in s.items()} for m, s in samples.items()}
        overhead = {k: {"p50_ms": round(modes["app+rls"][k]["p50"] - modes["app-filter"][k]["p50"], 3),
                        "p50_pct": round(100 * (modes["app+rls"][k]["p50"] / modes["app-filter"][k]["p50"] - 1), 1),
                        "p95_ms": round(modes["app+rls"][k]["p95"] - modes["app-filter"][k]["p95"], 3),
                        "p95_pct": round(100 * (modes["app+rls"][k]["p95"] / modes["app-filter"][k]["p95"] - 1), 1)}
                    for k in ("dense", "bm25", "total")}
        return {
            "run_id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
            "config": {"workspaces": args.workspaces, "chunks_per_workspace": args.chunks,
                       "total_chunks": args.workspaces * args.chunks, "queries": args.queries,
                       "warmup": args.warmup, "pool": args.pool, "k": args.k, "vocab": args.vocab,
                       "seed": args.seed, "dim": DIM, "image": IMAGE, "seed_seconds": round(seed_s, 1)},
            "machine": {"platform": platform.platform(), "python": platform.python_version(),
                        "note": "Docker Desktop VM; absolute numbers are machine-specific, compare modes only."},
            "modes": modes, "overhead_rls_vs_app_filter": overhead,
            "top_k_mismatches": mismatches, "stranger_workspace_rows_returned": leaked,
        }
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)


def report(result: dict) -> str:
    c = result["config"]
    lines = [f"# RQ4: RLS retrieval latency ({result['run_id']})", "",
             f"{c['workspaces']} workspaces x {c['chunks_per_workspace']} chunks = {c['total_chunks']} chunks "
             f"({c['dim']}-d), {c['queries']} measured queries after {c['warmup']} warm-up, pool {c['pool']}, "
             f"`{c['image']}`. Latency of one retrieval transaction (ms).", "",
             "| Stage | Mode | mean | p50 | p95 | p99 |", "|---|---|---:|---:|---:|---:|"]
    for stage in ("dense", "bm25", "total"):
        for mode in ("app-filter", "app+rls"):
            m = result["modes"][mode][stage]
            lines.append(f"| {stage} | {mode} | {m['mean']} | {m['p50']} | {m['p95']} | {m['p99']} |")
    lines += ["", "| Stage | RLS overhead p50 | RLS overhead p95 |", "|---|---:|---:|"]
    for stage, o in result["overhead_rls_vs_app_filter"].items():
        lines.append(f"| {stage} | {o['p50_ms']:+} ms ({o['p50_pct']:+}%) | {o['p95_ms']:+} ms ({o['p95_pct']:+}%) |")
    lines += ["", f"Top-{c['k']} differs between the two modes in {result['top_k_mismatches']} of {c['queries']} queries; "
              f"a workspace with no data got {result['stranger_workspace_rows_returned']} rows.", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspaces", type=int, default=5)
    ap.add_argument("--chunks", type=int, default=2000, help="chunks per workspace")
    ap.add_argument("--queries", type=int, default=300)
    ap.add_argument("--warmup", type=int, default=30)
    ap.add_argument("--pool", type=int, default=50, help="candidates per branch, as in ai-service")
    ap.add_argument("--k", type=int, default=10, help="top-k compared between modes")
    ap.add_argument("--vocab", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20261105)
    ap.add_argument("--out", type=Path, default=None, help="default eval/results/rq4-<run_id>")
    args = ap.parse_args()
    # psycopg's async mode cannot use Windows' default ProactorEventLoop.
    loop_factory = (lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())) if sys.platform == "win32" else None
    result = asyncio.run(run(args), loop_factory=loop_factory)
    out = args.out or Path(__file__).parent / "results" / f"rq4-{result['run_id']}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (out / "report.md").write_text(report(result), encoding="utf-8")
    sys.stdout.write(report(result) + "\nwritten to " + str(out) + "\n")


if __name__ == "__main__":
    main()
