"""Intermediate document structure (TECH-V2-ai-service §5.2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ElementKind = Literal["heading", "paragraph", "list_item", "table", "page_break", "code"]
ElementRole = Literal["content", "header", "footer", "boilerplate"]


class DocElement(BaseModel):
    kind: ElementKind
    text: str = ""
    level: int | None = None
    number: str | None = None
    rows: list[list[str]] | None = None
    # table: number of leading rows the source marks as column headers (0 = none recognised).
    header_rows: int = 0
    # (row, col, rowspan, colspan) for cells with rowspan > 1 or colspan > 1; None = unknown.
    cell_spans: list[tuple[int, int, int, int]] | None = None
    page: int | None = None
    page_end: int | None = None
    row_pages: list[int] | None = None
    char_start: int | None = None
    char_end: int | None = None
    row_spans: list[tuple[int, int]] | None = None
    role: ElementRole = "content"

    @model_validator(mode="after")
    def _check(self) -> DocElement:
        if self.kind == "table":
            if not self.rows:
                raise ValueError("table needs rows")
            width = len(self.rows[0])
            if width == 0 or any(len(r) != width for r in self.rows):
                raise ValueError("table rows must have equal, non-zero width")
            if self.row_pages is not None and len(self.row_pages) != len(self.rows):
                raise ValueError("row_pages must match rows")
        if self.page is not None and self.page_end is None:
            self.page_end = self.page
        return self


class StructuredDocument(BaseModel):
    file_type: Literal["PDF", "MD"]
    elements: list[DocElement]
    page_count: int | None = None
    frontmatter: dict | None = None
    # Library-reported conversion notes, e.g. {"kind": "...", "pages": [..]} (V2-21 consumes).
    converter_warnings: list[dict] = Field(default_factory=list)


class PageSpan(BaseModel):
    page: int
    char_start: int
    char_end: int


class RenderedDocument(BaseModel):
    markdown: str
    elements: list[DocElement]
    page_index: list[PageSpan]
    normalizer_version: str
