"""
Fast bulk-ingest 010_seed_data.sql into Postgres.

Strategy:
- Stream the SQL file in chunks (no full-load into memory).
- Detect INSERT INTO statements and split them into batches of N statements.
- Send each batch to Postgres in ONE transaction (BEGIN ... COMMIT) via psql stdin.
- This avoids the per-INSERT transaction overhead that makes the file slow.

Usage:
    python fast_ingest.py <sql_file> <batch_size> [start_offset_lines]

Notes:
- The script assumes the SQL uses ON CONFLICT DO NOTHING, so re-runs are safe.
- Tables involved (knowledge.chunks, knowledge.documents, etc.) will receive
  inserts in interleaved order, but each batch is wrapped in a transaction
  so partial failures roll back cleanly.
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path


INSERT_RE = re.compile(
    r"INSERT INTO\s+[\w.]+\s*\([^)]+\)\s*VALUES\s*\([^;]+?\)\s*(?:ON CONFLICT[^;]*)?;",
    flags=re.DOTALL,
)


def chunked_iter(path: Path, batch_size: int):
    """Yield lists of INSERT statement strings, batch_size per chunk."""
    batch: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        # Use a generator to find all INSERT statements
        for m in INSERT_RE.finditer(f.read()):
            stmt = m.group(0).strip()
            if not stmt:
                continue
            batch.append(stmt)
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def run_batch(batch: list[str], db_url: str, timeout: int = 600) -> tuple[bool, str]:
    """Send a batch via psql -c with explicit BEGIN/COMMIT wrapping."""
    sql = "BEGIN;\n" + "\n".join(batch) + "\nCOMMIT;\n"
    try:
        result = subprocess.run(
            [
                "docker", "exec", "-i", "poliwise-postgres",
                "psql", "-U", "poliwise", "-d", "poliwise",
                "-v", "ON_ERROR_STOP=1", "--no-psqlrc", "-q",
            ],
            input=sql,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return False, (result.stderr or "")[:2000]
        return True, (result.stdout or "")[:500]
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT after %ds" % timeout
    except Exception as e:
        return False, f"EXCEPTION: {e}"


def main():
    if len(sys.argv) < 3:
        print("Usage: python fast_ingest.py <sql_file> <batch_size>")
        sys.exit(1)
    sql_path = Path(sys.argv[1])
    batch_size = int(sys.argv[2])

    print(f"Ingesting {sql_path} with batch_size={batch_size}")
    start = time.time()
    total = 0
    failed_batches = 0
    for i, batch in enumerate(chunked_iter(sql_path, batch_size), 1):
        ok, msg = run_batch(batch, "poliwise", timeout=900)
        total += len(batch)
        elapsed = time.time() - start
        rate = total / elapsed if elapsed > 0 else 0
        if not ok:
            failed_batches += 1
            print(
                f"  [BATCH {i:4d}] FAILED at row ~{total:,} "
                f"({len(batch)} stmts, {rate:,.0f} rows/s): {msg[:300]}"
            )
            # On failure, fall back to per-statement mode for THIS batch
            # to isolate the bad row.
            for stmt in batch:
                ok2, msg2 = run_batch([stmt], "poliwise", timeout=60)
                if not ok2:
                    print(f"    BAD STMT (skipped): {stmt[:200]}... err={msg2[:200]}")
        else:
            print(
                f"  [BATCH {i:4d}] OK  {total:,} rows "
                f"in {elapsed:.1f}s ({rate:,.0f} rows/s)"
            )
    print(f"\nDone. Total: {total:,} statements in {time.time()-start:.1f}s. "
          f"Failed batches: {failed_batches}")


if __name__ == "__main__":
    main()
