"""Plain text extractor - handles .txt and other text files."""

from uuid import UUID

from src.services.extractors.base import DocumentExtractor, ExtractedChunk, ExtractedDocument


class TextExtractor(DocumentExtractor):
    """Extracts text from plain text files."""

    def supported_extensions(self) -> list[str]:
        return [".txt", ".text"]

    async def extract(
        self, file_bytes: bytes, file_key: str, document_id: UUID, version_id: UUID
    ) -> ExtractedDocument:
        text = file_bytes.decode("utf-8", errors="replace")
        
        # Simple chunking by paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        
        chunks = []
        for i, para in enumerate(paragraphs):
            chunks.append(
                ExtractedChunk(
                    content=para,
                    chunk_index=i,
                    chunk_type="parent",
                    section_title=f"Paragraph {i + 1}",
                    section_level=1,
                )
            )
        
        # If no paragraphs, use entire text as single chunk
        if not chunks:
            chunks.append(
                ExtractedChunk(
                    content=text.strip() or "(empty file)",
                    chunk_index=0,
                    chunk_type="parent",
                )
            )

        return ExtractedDocument(
            text=text,
            chunks=chunks,
            page_count=1,
            language=self._detect_language(text),
            metadata={"extractor": "text"},
        )

    def _detect_language(self, text: str) -> str:
        """Language detection based on character set - supports EN and VI."""
        if not text:
            return "en"
        vietnamese_chars = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡọùúủũụưừứửữựỳýỷỹỵđ")
        vietnamese_count = sum(1 for c in text.lower() if c in vietnamese_chars)
        return "vi" if vietnamese_count > len(text) * 0.05 else "en"
