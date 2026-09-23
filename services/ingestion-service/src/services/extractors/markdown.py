"""Markdown extractor with frontmatter parsing."""

import re
from typing import Optional
from uuid import UUID

from src.services.extractors.base import DocumentExtractor, ExtractedChunk, ExtractedDocument


class MarkdownExtractor(DocumentExtractor):
    """Extracts text and structure from Markdown files."""

    def supported_extensions(self) -> list[str]:
        return [".md", ".markdown"]

    async def extract(
        self, file_bytes: bytes, file_key: str, document_id: UUID, version_id: UUID
    ) -> ExtractedDocument:
        text = file_bytes.decode("utf-8", errors="replace")

        metadata = {}
        if text.startswith("---"):
            text, metadata = self._parse_frontmatter(text)

        chunks = self._chunk_by_headings(text, file_key)
        language = self._detect_language(text)

        return ExtractedDocument(
            text=text,
            chunks=chunks,
            page_count=1,
            language=language,
            metadata=metadata,
        )

    def _parse_frontmatter(self, text: str) -> tuple[str, dict]:
        """Parse YAML frontmatter from markdown."""
        parts = text.split("---", 2)
        if len(parts) < 3:
            return text, {}

        frontmatter_raw = parts[1]
        content = parts[2].strip()

        metadata = {}
        for line in frontmatter_raw.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        return content, metadata

    def _chunk_by_headings(self, text: str, file_key: str) -> list[ExtractedChunk]:
        """Split markdown into chunks by headings."""
        chunks = []
        current_index = 0
        current_section = []
        current_heading = None
        current_level = None

        lines = text.split("\n")

        for line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                if current_section:
                    chunks.append(
                        ExtractedChunk(
                            content="\n".join(current_section).strip(),
                            chunk_index=current_index,
                            chunk_type="parent",
                            section_title=current_heading,
                            section_level=current_level,
                        )
                    )
                    current_index += 1
                    current_section = []

                current_level = len(heading_match.group(1))
                current_heading = heading_match.group(2).strip()
            else:
                current_section.append(line)

        if current_section:
            chunks.append(
                ExtractedChunk(
                    content="\n".join(current_section).strip(),
                    chunk_index=current_index,
                    chunk_type="parent",
                    section_title=current_heading,
                    section_level=current_level,
                )
            )

        if not chunks:
            chunks.append(
                ExtractedChunk(
                    content=text.strip(),
                    chunk_index=0,
                    chunk_type="parent",
                )
            )

        return chunks

    def _detect_language(self, text: str) -> str:
        """Language detection based on character set - supports EN and VI."""
        if not text:
            return "en"
        vietnamese_chars = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡọùúủũụưừứửữựỳýỷỹỵđ")
        vietnamese_count = sum(1 for c in text.lower() if c in vietnamese_chars)
        return "vi" if vietnamese_count > len(text) * 0.05 else "en"