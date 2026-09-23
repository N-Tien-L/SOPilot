"""Image extractor using pytesseract OCR."""

import io
from typing import Optional
from uuid import UUID

import pytesseract
from PIL import Image

from src.services.extractors.base import DocumentExtractor, ExtractedChunk, ExtractedDocument
from src.config.settings import settings


class ImageExtractor(DocumentExtractor):
    """Extracts text from images using OCR."""

    def supported_extensions(self) -> list[str]:
        return [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"]

    async def extract(
        self, file_bytes: bytes, file_key: str, document_id: UUID, version_id: UUID
    ) -> ExtractedDocument:
        image = Image.open(io.BytesIO(file_bytes))

        text, ocr_confidence = self._ocr_image(image)
        language = self._detect_language(text)

        chunks = [
            ExtractedChunk(
                content=text,
                chunk_index=0,
                chunk_type="parent",
            )
        ]

        return ExtractedDocument(
            text=text,
            chunks=chunks,
            page_count=1,
            language=language,
            metadata={
                "extractor": "pytesseract",
                "width": image.width,
                "height": image.height,
                "ocr_confidence": ocr_confidence,
            },
        )

    def _ocr_image(self, image: Image.Image) -> tuple[str, float]:
        """Perform OCR on an image and return (text, avg_confidence)."""
        data = pytesseract.image_to_data(image, lang=settings.ocr_language, output_type=pytesseract.Output.DICT)

        confidences = [c for c in data["conf"] if c > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        text = pytesseract.image_to_string(image, lang=settings.ocr_language)
        return text, avg_confidence / 100.0

    def _detect_language(self, text: str) -> str:
        """Language detection based on character set - supports EN and VI."""
        if not text:
            return "en"
        vietnamese_chars = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡọùúủũụưừứửữựỳýỷỹỵđ")
        vietnamese_count = sum(1 for c in text.lower() if c in vietnamese_chars)
        return "vi" if vietnamese_count > len(text) * 0.05 else "en"