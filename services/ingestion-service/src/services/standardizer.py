import re
import unicodedata
import structlog
from src.models.extraction import StructuredText

logger = structlog.get_logger()


class DocumentPolicyStandardizer:
    """Detects and standardizes Vietnamese document structure."""

    HEADING_PATTERNS = [
        (r"^(CHAPTER|Chapter|Chương|CHƯƠNG)\s+([IVXLCDM]+|\d+)\s*[:\-]?\s*(.*)$", 1),
        (r"^(ARTICLE|Article|Điều|ĐIỀU)\s+(\d+)\s*[:\-]?\s*(.*)$", 2),
        (r"^(CLAUSE|Clause|Khoản|KHOẢN)\s+(\d+)\s*[:\-]?\s*(.*)$", 3),
        (r"^(POINT|Point|Điểm|ĐIỂM)\s+([a-z])\s*[:\-]?\s*(.*)$", 4),
        (r"^(SECTION|Section|Mục|MỤC)\s+(\d+)\s*[:\-]?\s*(.*)$", 2),
        (r"^#{1,6}\s+(.+)$", 1),  # Markdown headings
    ]

    SHORTCODE_PATTERNS = [
        r"\{\{%.*?%\}\}",
        r"\{\{<\s*.*?\s*>}\}",
    ]

    def normalize(self, raw_text: str) -> StructuredText:
        """Normalize text with Unicode normalization, whitespace cleanup, and heading detection."""
        normalized = unicodedata.normalize("NFC", raw_text)

        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)

        for pattern in self.SHORTCODE_PATTERNS:
            normalized = re.sub(pattern, "", normalized)

        headings = []
        sections = []
        current_section = {"title": "", "level": 1, "text": "", "path": []}

        for line in normalized.split("\n"):
            heading_match = None
            for pattern, level in self.HEADING_PATTERNS:
                match = re.match(pattern, line.strip())
                if match:
                    heading_match = (match, level)
                    break

            if heading_match:
                if current_section["text"]:
                    sections.append(current_section.copy())

                heading_text = heading_match[0].group(2) if len(heading_match[0].groups()) >= 2 else line.strip()
                current_section = {
                    "title": heading_text,
                    "level": heading_match[1],
                    "text": "",
                    "path": self._build_path(sections, heading_text),
                }
                headings.append({
                    "text": heading_text,
                    "level": heading_match[1],
                })
            else:
                if current_section["text"]:
                    current_section["text"] += "\n"
                current_section["text"] += line

        if current_section["text"]:
            sections.append(current_section.copy())

        if not sections:
            sections.append({
                "title": "",
                "level": 1,
                "text": normalized,
                "path": [],
            })

        logger.info("text_normalized", headings=len(headings), sections=len(sections))

        return StructuredText(
            normalized_text=normalized,
            headings=headings,
            sections=sections,
        )

    def _build_path(self, sections: list, current_title: str) -> list[str]:
        """Build section path based on hierarchy."""
        path = []
        for section in sections:
            if section["level"] < 3:
                path.append(section["title"])
        path.append(current_title)
        return path
