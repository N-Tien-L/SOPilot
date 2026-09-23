"""
Fast bulk-ingest 010_seed_data.sql into Postgres (streaming version).

Strategy:
- Stream the SQL file in fixed-size byte chunks (no full-load into memory).
- Use a sliding-window parser to extract complete INSERT statements.
- Group N statements into one BEGIN/COMMIT transaction.
- Send via psql stdin.

Usage:
    python fast_ingest_stream.py <sql_file> <batch_size>
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path


# Statement terminator that ends an INSERT block.
# We split on a semicolon followed by newline (and not inside a string).
INSERT_END = re.compile(r";\s*\n", flags=re.MULTILINE)


def stream_inserts(path: Path, yield_batch_size: int):
    """Yield batches of INSERT statement strings by streaming the file.

    We use a simple line-based parser:
    - Lines starting with 'INSERT INTO' begin a statement.
    - A semicolon at end of line ends the statement.
    - We accumulate lines until we find the terminator.
    """
    batch: list[str] = []
    buf: list[str] = []
    in_insert = False
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not in_insert:
                if stripped.startswith("INSERT INTO"):
                    in_insert = True
                    buf = [line]
                    # Single-line INSERT case
                    if stripped.endswith(";"):
                        stmt = "\n".join(buf).strip()
                        # Strip trailing semicolon for our pipeline
                        batch.append(stmt.rstrip(";").strip())
                        buf = []
                        in_insert = False
                        if len(batch) >= yield_batch_size:
                            yield batch
                            batch = []
                # else: skip non-INSERT line
            else:
                buf.append(line)
                # Multi-line: end when we see a line ending in ';'
                if stripped.endswith(";"):
                    stmt = "\n".join(buf).strip()
                    batch.append(stmt.rstrip(";").strip())
                    buf = []
                    in_insert = False
                    if len(batch) >= yield_batch_size:
                        yield batch
                        batch = []
    if batch:
        yield batch


def run_batch(batch: list[str], timeout: int = 900) -> tuple[bool, str]:
    """Send a batch via docker exec psql with explicit BEGIN/COMMIT."""
    sql_lines = ["BEGIN;"]
    sql_lines.extend(batch)
    sql_lines.append("COMMIT;")
    sql = "\n".join(sql_lines) + "\n"
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
            return False, (result.stderr or result.stdout or "")[:2000]
        return True, (result.stdout or "")[:500]
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    except Exception as e:
        return False, f"EXCEPTION: {e}"


def main():
    if len(sys.argv) < 3:
        print("Usage: python fast_ingest_stream.py <sql_file> <batch_size>")
        sys.exit(1)
    sql_path = Path(sys.argv[1])
    batch_size = int(sys.argv[2])

    if not sql_path.exists():
        print(f"ERROR: file not found: {sql_path}")
        sys.exit(1)

    print(f"Ingesting {sql_path}")
    print(f"  size: {sql_path.stat().st_size:,} bytes")
    print(f"  batch_size: {batch_size}")

    start = time.time()
    total = 0
    failed_batches = 0
    failed_stmts = 0

    for i, batch in enumerate(stream_inserts(sql_path, batch_size), 1):
        ok, msg = run_batch(batch, timeout=900)
        total += len(batch)
        elapsed = time.time() - start
        rate = total / elapsed if elapsed > 0 else 0
        if not ok:
            failed_batches += 1
            print(
                f"  [BATCH {i:5d}] FAILED at ~{total:,} stmts "
                f"({rate:,.0f} stmts/s): {msg[:300]}"
            )
            # Fall back to per-statement mode for THIS batch
            for stmt in batch:
                ok2, msg2 = run_batch([stmt], timeout=60)
                if not ok2:
                    failed_stmts += 1
                    print(f"    SKIPPED bad stmt: {stmt[:150]}... err={msg2[:150]}")
        else:
            if i % 5 == 0 or i < 5:
                print(
                    f"  [BATCH {i:5d}] OK  {total:,} stmts "
                    f"in {elapsed:.1f}s ({rate:,.0f} stmts/s)"
                )

    elapsed = time.time() - start
    print(f"\nDone. {total:,} statements in {elapsed:.1f}s "
          f"({total/elapsed:,.0f} stmts/s)")
    print(f"  Failed batches: {failed_batches}")
    print(f"  Failed individual statements: {failed_stmts}")


if __name__ == "__main__":
    main()
