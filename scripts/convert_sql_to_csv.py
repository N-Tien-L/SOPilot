"""
Convert INSERT statements in 010_seed_data.sql into COPY-compatible CSV files.

Strategy:
- Read SQL file once, stream-parse INSERT blocks.
- For each table (chunks, documents, document_versions, document_metadata, ...),
  write rows into a CSV file.
- Use Python csv module with QUOTE_MINIMAL, escape double-quotes properly.
- Output files to ./csv_output/ with one CSV per table.

Usage:
    python convert_sql_to_csv.py <input.sql> <output_dir>
"""

import csv
import os
import re
import sys
import time
from pathlib import Path


# Map SQL type cast to Python value handling
# Columns that need jsonb-array / array literal preservation
def normalize_array_literal(v: str) -> str:
    """Convert SQL ARRAY['a','b']::type[] into Postgres array literal {a,b}.

    PostgreSQL array literals use braces: {"a","b","c"}.
    Empty array is '{}'.
    """
    v = v.strip()
    if v.upper() == "NULL":
        return ""
    # Handle ARRAY[...]
    m = re.match(
        r"^ARRAY\[(.*)\](?:::[a-zA-Z_][\w\[\]]*)?$", v, flags=re.DOTALL
    )
    if m:
        inner = m.group(1)
        # inner looks like: 'USER', 'MANAGER', 'ADMIN' or 'uuid1', 'uuid2'
        items = []
        # Find string literals or quoted items
        for item in re.finditer(r"'((?:[^']|'')*)'", inner):
            items.append('"' + item.group(1).replace('"', '\\"') + '"')
        return "{" + ",".join(items) + "}"
    return v


def normalize_vector_literal(v: str) -> str:
    """Vector literal '[1.0, 2.0, ...]'::vector stays as text. Strip the cast."""
    v = v.strip()
    if v.upper() == "NULL":
        return ""
    # Strip trailing ::vector or ::vector(1024)
    v = re.sub(r"::vector(?:\(\d+\))?$", "", v).strip()
    # Remove surrounding single quotes if present
    if v.startswith("'") and v.endswith("'"):
        v = v[1:-1].replace("''", "'")
    return v


def normalize_string_literal(v: str) -> str:
    """Strip outer single quotes from a SQL string literal."""
    v = v.strip()
    if v.upper() == "NULL":
        return ""
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1].replace("''", "'")
    return v


def normalize_number(v: str) -> str:
    v = v.strip()
    if v.upper() == "NULL":
        return ""
    return v


def normalize_bool(v: str) -> str:
    v = v.strip()
    if v.upper() == "NULL":
        return ""
    return v.lower()


def normalize_uuid(v: str) -> str:
    v = v.strip()
    if v.upper() == "NULL":
        return ""
    return v.strip("'")


def normalize_json(v: str) -> str:
    v = v.strip()
    if v.upper() == "NULL":
        return ""
    if v.startswith("'") and v.endswith("'"):
        v = v[1:-1].replace("''", "'")
    return v


def normalize_timestamp(v: str) -> str:
    v = v.strip()
    if v.upper() == "NULL":
        return ""
    return v.strip("'")


# Column types per table (in order matching the INSERT column list)
# Built by inspecting real INSERT statements in the seed file.
COLUMN_TYPES: dict[str, dict[str, callable]] = {
    "knowledge.chunks": {
        "id": normalize_uuid,
        "document_id": normalize_uuid,
        "document_version_id": normalize_uuid,
        "document_version": normalize_number,
        "chunk_index": normalize_number,
        "chunk_type": normalize_string_literal,
        "parent_chunk_id": normalize_uuid,
        "content": normalize_string_literal,
        "content_length": normalize_number,
        "section_title": normalize_string_literal,
        "section_level": normalize_number,
        "section_path": normalize_array_literal,
        "start_char_index": normalize_number,
        "end_char_index": normalize_number,
        "token_count": normalize_number,
        "embedding_vector": normalize_vector_literal,
        "embedding_model": normalize_string_literal,
        "embedding_dimension": normalize_number,
        "allowed_roles": normalize_array_literal,
        "allowed_departments": normalize_array_literal,
        "allowed_users": normalize_array_literal,
        "access_level": normalize_string_literal,
        "is_latest": normalize_bool,
        "metadata": normalize_json,
    },
    "knowledge.documents": {
        "id": normalize_uuid,
        "original_filename": normalize_string_literal,
        "file_type": normalize_string_literal,
        "file_size_bytes": normalize_number,
        "mime_type": normalize_string_literal,
        "file_key": normalize_string_literal,
        "status": normalize_string_literal,
        "current_version": normalize_number,
        "language": normalize_string_literal,
        "chunking_strategy": normalize_string_literal,
        "uploaded_by": normalize_uuid,
        "created_at": normalize_timestamp,
        "updated_at": normalize_timestamp,
    },
    "knowledge.document_versions": {
        "id": normalize_uuid,
        "document_id": normalize_uuid,
        "version_number": normalize_number,
        "file_key": normalize_string_literal,
        "file_size_bytes": normalize_number,
        "content_hash": normalize_string_literal,
        "language": normalize_string_literal,
        "created_by": normalize_uuid,
        "created_at": normalize_timestamp,
    },
    "metadata.document_metadata": {
        "id": normalize_uuid,
        "document_id": normalize_uuid,
        "title": normalize_string_literal,
        "description": normalize_string_literal,
        "document_type": normalize_string_literal,
        "category_id": normalize_uuid,
        "department_id": normalize_uuid,
        "access_level": normalize_string_literal,
        "status": normalize_string_literal,
        "current_version": normalize_number,
        "created_by": normalize_uuid,
        "updated_by": normalize_uuid,
        "published_by": normalize_uuid,
        "published_at": normalize_timestamp,
        "effective_date": normalize_timestamp,
        "created_at": normalize_timestamp,
        "updated_at": normalize_timestamp,
    },
}


# Regex to match an INSERT block: from "INSERT INTO table (" through ";"
INSERT_RE = re.compile(
    r"INSERT INTO\s+([\w.]+)\s*\(([^)]+)\)\s*VALUES\s*\((.*?)\)\s*(?:ON CONFLICT[^;]*)?;",
    flags=re.DOTALL,
)


def split_values(value_block: str) -> list[str]:
    """Split a VALUES tuple body into individual value expressions.

    Handles nested parentheses, single-quoted strings with '' escapes,
    and dollar-quoted strings (E'...').
    """
    parts = []
    depth = 0
    cur = []
    i = 0
    in_string = False
    string_char = None
    while i < len(value_block):
        c = value_block[i]
        if in_string:
            cur.append(c)
            if c == "\\" and i + 1 < len(value_block):
                cur.append(value_block[i + 1])
                i += 2
                continue
            if c == string_char:
                # Check for '' escape
                if i + 1 < len(value_block) and value_block[i + 1] == string_char:
                    cur.append(value_block[i + 1])
                    i += 2
                    continue
                in_string = False
                string_char = None
            i += 1
            continue
        if c in ("'", '"'):
            in_string = True
            string_char = c
            cur.append(c)
            i += 1
            continue
        if c == "E" and i + 1 < len(value_block) and value_block[i + 1] == "'":
            # E'...' string
            cur.append(c)
            cur.append(value_block[i + 1])
            i += 2
            in_string = True
            string_char = "'"
            continue
        if c == "(":
            depth += 1
            cur.append(c)
        elif c == ")":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    if cur:
        parts.append("".join(cur).strip())
    return parts


def parse_insert_block(match: re.Match) -> tuple[str, list[str], list[str]] | None:
    table = match.group(1).strip()
    cols_str = match.group(2)
    vals_str = match.group(3)
    cols = [c.strip() for c in cols_str.split(",")]
    vals = split_values(vals_str)
    if len(cols) != len(vals):
        return None
    return table, cols, vals


def convert_sql_to_csv(input_path: Path, output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)

    writers: dict[str, csv.writer] = {}
    files: dict[str, any] = {}
    counts: dict[str, int] = {}
    column_order: dict[str, list[str]] = {}

    def get_writer(table: str, columns: list[str]) -> csv.writer:
        if table in writers:
            return writers[table]
        safe_name = table.replace(".", "_") + ".csv"
        f = open(output_dir / safe_name, "w", newline="", encoding="utf-8")
        files[table] = f
        w = csv.writer(
            f,
            quoting=csv.QUOTE_MINIMAL,
            quotechar='"',
            doublequote=True,
            escapechar="\\",
        )
        # Normalize column names: lowercase for Postgres COPY compatibility
        normalized = [c.lower() for c in columns]
        w.writerow(normalized)
        column_order[table] = normalized
        writers[table] = w
        counts.setdefault(table, 0)
        return w

    start = time.time()
    bytes_read = 0
    last_report = start

    with open(input_path, "r", encoding="utf-8") as f:
        # Read whole file (3.8M lines, ~880MB). Chunked regex would be ideal but
        # we use mmap-friendly streaming via finditer on text.
        content = f.read()

    print(f"Read {len(content):,} bytes in {time.time()-start:.1f}s")

    parse_start = time.time()
    matched = 0
    skipped = 0
    for m in INSERT_RE.finditer(content):
        result = parse_insert_block(m)
        if result is None:
            skipped += 1
            continue
        table, cols, vals = result
        normalizers = COLUMN_TYPES.get(table)
        if normalizers is None:
            skipped += 1
            continue
        writer = get_writer(table, cols)
        row = []
        for col, val in zip(cols, vals):
            norm = normalizers.get(col.lower())
            if norm is None:
                # Unknown column - store raw
                row.append(val.strip())
            else:
                row.append(norm(val))
        writer.writerow(row)
        counts[table] = counts.get(table, 0) + 1
        matched += 1
        if matched % 10000 == 0:
            now = time.time()
            print(
                f"  parsed {matched:,} rows in {now-parse_start:.1f}s "
                f"({matched/(now-parse_start):,.0f} rows/s)"
            )

    for f in files.values():
        f.close()

    print(f"\nDone. Parsed {matched:,} INSERT blocks, skipped {skipped}.")
    print("Row counts per table:")
    for t, c in sorted(counts.items()):
        print(f"  {t}: {c:,}")

    return counts


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_sql_to_csv.py <input.sql> <output_dir>")
        sys.exit(1)
    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    convert_sql_to_csv(input_path, output_dir)
