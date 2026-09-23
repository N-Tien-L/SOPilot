"""PDF extractor using PyMuPDF with OCR fallback."""

import io
from typing import Optional
from uuid import UUID

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from src.services.extractors.base import DocumentExtractor, ExtractedChunk, ExtractedDocument
from src.config.settings import settings


class PDFExtractor(DocumentExtractor):
    """Extracts text and structure from PDF files."""

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    async def extract(
        self, file_bytes: bytes, file_key: str, document_id: UUID, version_id: UUID
    ) -> ExtractedDocument:
        chunks = []
        text_parts = []
        page_count = 0
        current_index = 0
        ocr_confidences = []

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            page_count = len(doc)

            for page_num, page in enumerate(doc):
                page_text, ocr_conf = self._extract_page_text(page, page_num)
                if ocr_conf is not None:
                    ocr_confidences.append(ocr_conf)

                if page_text.strip():
                    text_parts.append(page_text)
                    chunks.append(
                        ExtractedChunk(
                            content=page_text,
                            chunk_index=current_index,
                            chunk_type="parent",
                            page_number=page_num + 1,
                        )
                    )
                    current_index += 1

        full_text = "\n".join(text_parts)
        language = self._detect_language(full_text)
        avg_ocr_confidence = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else None

        return ExtractedDocument(
            text=full_text,
            chunks=chunks,
            page_count=page_count,
            language=language,
            metadata={
                "extractor": "pymupdf",
                "ocr_fallback": True,
                "ocr_confidence": round(avg_ocr_confidence, 4) if avg_ocr_confidence is not None else None,
            },
        )

    def _extract_page_text(self, page, page_num: int) -> tuple[str, Optional[float]]:
        """Extract text from a single PDF page, with OCR fallback.
        Returns (text, ocr_confidence) where confidence is None if no OCR was used.
        """
        page_text = page.get_text("text").strip()

        if not page_text or len(page_text) < settings.ocr_fallback_min_text_length:
            pix = page.get_pixmap(dpi=300)
            image_bytes = pix.tobytes("png")
            page_text, ocr_conf = self._ocr_page(image_bytes)
            if page_text.strip():
                return page_text, ocr_conf

        return page_text, None

    def _ocr_page(self, image_bytes: bytes) -> tuple[str, float]:
        """Perform OCR on an image and return (text, avg_confidence)."""
        image = Image.open(io.BytesIO(image_bytes))
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