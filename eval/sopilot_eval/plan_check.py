"""Check V2 ticket counters, table, DAG and reverse dependencies without mutation."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


def validate_plan(root: Path = ROOT) -> dict:
    plan_path = root / "docs/03-plans/PLAN-V2-sopilot-mvp.md"
    plan = frontmatter(plan_path)
    text = plan_path.read_text(encoding="utf-8")
    tickets = {}
    for path in sorted((root / "docs/03-plans/tickets").glob("V2-*.md")):
        meta = frontmatter(path)
        if meta["id"] in tickets:
            raise ValueError("duplicate V2 ticket ID")
        if meta["size"] == "XL":
            raise ValueError(f"unsplit XL ticket: {meta['id']}")
        tickets[meta["id"]] = meta
    for key, expected in {
        "total_tickets": len(tickets),
        "completed_tickets": sum(t["status"] == "done" for t in tickets.values()),
        "review_tickets": sum(t["status"] == "review" for t in tickets.values()),
        "implemented_tickets": sum(
            t["status"] in {"done", "review"} for t in tickets.values()
        ),
    }.items():
        if plan[key] != expected:
            raise ValueError(f"counter mismatch: {key}")
    edges = set()
    for tid, ticket in tickets.items():
        if ticket["parent_plan"] != plan["id"]:
            raise ValueError(f"wrong parent plan: {tid}")
        row = re.findall(r"^\| `" + re.escape(tid) + r"` \|(.+)$", text, re.MULTILINE)
        if len(row) != 1:
            raise ValueError(f"missing/duplicate plan row: {tid}")
        columns = [column.strip() for column in row[0].split("|")]
        if (
            columns[1] != ticket["scope"]
            or columns[2] != ticket["size"]
            or columns[4] != ticket["status"]
        ):
            raise ValueError(f"plan row metadata mismatch: {tid}")
        if set(re.findall(r"V2-\d+", columns[3])) != set(ticket["depends_on"]):
            raise ValueError(f"plan row dependency mismatch: {tid}")
        for dep in ticket["depends_on"]:
            if dep not in tickets:
                raise ValueError(f"unknown dependency: {dep}")
            edges.add((dep, tid))
        expected_blocks = {
            other for other, meta in tickets.items() if tid in meta["depends_on"]
        }
        if set(ticket["blocks"]) != expected_blocks:
            raise ValueError(f"reverse dependency mismatch: {tid}")
    visiting, visited = set(), set()

    def visit(tid: str) -> None:
        if tid in visiting:
            raise ValueError("dependency cycle")
        if tid not in visited:
            visiting.add(tid)
            for dep in tickets[tid]["depends_on"]:
                visit(dep)
            visiting.remove(tid)
            visited.add(tid)

    for tid in tickets:
        visit(tid)
    diagram = re.search(r"```mermaid\n(.*?)```", text, re.DOTALL).group(1)
    diagram_edges = {
        (f"V2-{left}", f"V2-{right}")
        for left, right in re.findall(r"V(\d+) --> V(\d+)", diagram)
    }
    if diagram_edges != edges:
        raise ValueError("Mermaid DAG differs from ticket dependencies")
    closure = set()

    def collect(tid: str) -> None:
        for dep in tickets[tid]["depends_on"]:
            if dep not in closure:
                closure.add(dep)
                collect(dep)

    collect("V2-18")
    if closure != set(tickets) - {"V2-18"}:
        raise ValueError("handover does not wait for every ticket")
    return {
        "tickets": len(tickets),
        "edges": len(edges),
        "counters_match": True,
        "acyclic": True,
        "handover_covers_all_tickets": True,
    }


if __name__ == "__main__":
    sys.stdout.write(json.dumps(validate_plan(), indent=2) + "\n")
