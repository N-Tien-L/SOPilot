"""Procedure tables (Responsibility / Step / Description / Form): one chunk per row (§5.4)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from sopilot_ai.docproc.clean.boilerplate import fold
from sopilot_ai.docproc.model import DocElement

_RESPONSIBILITY = re.compile(r"trach nhiem|responsib|nguoi thuc hien|phu trach|\bowner\b|\bwho\b")
_STEP_OR_DESCRIPTION = re.compile(
    r"\bbuoc\b|\bstep\b|\bstt\b|mo ta|noi dung|description|hoat dong|activity|action|cong viec"
    r"|\btask\b")


@dataclass(frozen=True)
class StepRow:
    row: int  # index into ``DocElement.rows``
    content: str


def header_row_count(el: DocElement) -> int:
    return max(el.header_rows, 1)


def is_procedure_table(el: DocElement) -> bool:
    if el.kind != "table" or not el.rows or len(el.rows) < 2:
        return False
    head = [fold(c) for c in el.rows[header_row_count(el) - 1]]
    has_owner = any(_RESPONSIBILITY.search(c) for c in head)
    has_step = any(_STEP_OR_DESCRIPTION.search(c) for c in head)
    return has_owner and has_step


def filled_rows(el: DocElement) -> list[list[str]]:
    """Table cells with merged (``rowspan``) values repeated into each row they cover.

    Without ``cell_spans`` nothing is guessed: an empty cell stays empty.
    """
    assert el.rows
    grid = [list(row) for row in el.rows]
    for row, col, rowspan, _ in el.cell_spans or []:
        if rowspan <= 1 or row >= len(grid) or col >= len(grid[row]):
            continue
        value = el.rows[row][col]
        for covered in range(row + 1, min(row + rowspan, len(grid))):
            if not grid[covered][col].strip():
                grid[covered][col] = value
    return grid


def step_rows(el: DocElement) -> list[StepRow]:
    """``Header: value | Header: value`` per data row; rows empty in the source are skipped."""
    assert el.rows
    skip = header_row_count(el)
    headers = el.rows[skip - 1]
    grid = filled_rows(el)
    steps: list[StepRow] = []
    for index in range(skip, len(grid)):
        if not any(cell.strip() for cell in el.rows[index]):
            continue
        parts = [f"{headers[c].strip() or f'Cột {c + 1}'}: {cell.strip()}"
                 for c, cell in enumerate(grid[index]) if cell.strip()]
        steps.append(StepRow(row=index, content=" | ".join(parts)))
    return steps
