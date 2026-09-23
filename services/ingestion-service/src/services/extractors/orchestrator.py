"""Extraction orchestrator - routes to format-specific extractors."""

import structlog
from uuid import UUID

from src.services.extractors.base import ExtractedDocument
from src.services.extractors.pdf import PDFExtractor
from src.services.extractors.docx import DOCXExtractor
from src.services.extractors.markdown import MarkdownExtractor
from src.services.extractors.image import ImageExtractor
from src.services.extractors.text import TextExtractor

logger = structlog.get_logger()


class ExtractionOrchestrator:
    """Routes to appropriate extractor based on file extension."""

    def __init__(self):
        self._extractors: dict[str, any] = {}
        self._register_default_extractors()

    def _register_default_extractors(self) -> None:
        """Register all built-in extractors."""
        extractors = [
            PDFExtractor(),
            DOCXExtractor(),
            MarkdownExtractor(),
            ImageExtractor(),
            TextExtractor(),
        ]

        for extractor in extractors:
            for ext in extractor.supported_extensions():
                self._extractors[ext] = extractor

        logger.info("extractors_registered", extensions=list(self._extractors.keys()))

    def register(self, extractor) -> None:
        """Register a custom extractor."""
        for ext in extractor.supported_extensions():
            self._extractors[ext] = extractor

    async def extract(
        self, file_bytes: bytes, file_key: str, document_id: UUID, version_id: UUID
    ) -> ExtractedDocument:
        """Route to appropriate extractor based on file extension."""
        ext = self._get_extension(file_key)
        extractor = self._extractors.get(ext)

        if not extractor:
            raise ValueError(f"No extractor for extension: {ext}")

        logger.info(
            "extraction_started",
            file_key=file_key,
            extractor=extractor.__class__.__name__,
        )

        result = await extractor.extract(file_bytes, file_key, document_id, version_id)

        logger.info(
            "extraction_completed",
            file_key=file_key,
            text_length=len(result.text),
            chunk_count=len(result.chunks),
            page_count=result.page_count,
        )

        return result

    def _get_extension(self, file_key: str) -> str:
        """Extract lowercase file extension from a file key."""
        if "." in file_key:
            return "." + file_key.rsplit(".", 1)[-1].lower()
        return ""


orchestrator = ExtractionOrchestrator()