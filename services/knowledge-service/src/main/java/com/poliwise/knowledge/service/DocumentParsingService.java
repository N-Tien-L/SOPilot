package com.poliwise.knowledge.service;

import com.poliwise.knowledge.enums.FileType;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.tika.Tika;
import org.apache.tika.exception.TikaException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.io.IOException;

@Service
public class DocumentParsingService {

    private static final Logger log = LoggerFactory.getLogger(DocumentParsingService.class);

    private final Tika tika;

    public DocumentParsingService() {
        this.tika = new Tika();
    }

    public ParsingResult parse(InputStream inputStream, FileType fileType, String filename) {
        try {
            return switch (fileType) {
                case PDF -> parsePdf(inputStream);
                case DOCX, DOC -> parseWord(inputStream);
                case XLSX, XLS -> parseExcel(inputStream);
                case TXT -> parseText(inputStream);
                case PNG, JPG, JPEG -> parseImage(inputStream);
                default -> new ParsingResult("", 0, 0, false, null);
            };
        } catch (Exception e) {
            log.error("Failed to parse file: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to parse document: " + e.getMessage(), e);
        }
    }

    private ParsingResult parsePdf(InputStream inputStream) throws IOException {
        try (PDDocument document = Loader.loadPDF(inputStream.readAllBytes())) {
            PDFTextStripper stripper = new PDFTextStripper();
            String text = stripper.getText(document);
            int pageCount = document.getNumberOfPages();
            int wordCount = countWords(text);

            return new ParsingResult(text, pageCount, wordCount, false, null);
        }
    }

    private ParsingResult parseWord(InputStream inputStream) throws IOException, TikaException {
        // Use Apache Tika for DOC/DOCX extraction
        try (InputStream fis = inputStream) {
            String text = tika.parseToString(fis);
            int wordCount = countWords(text);
            return new ParsingResult(text, 1, wordCount, false, null);
        }
    }

    private ParsingResult parseExcel(InputStream inputStream) throws IOException, TikaException {
        // Use Apache Tika for XLS/XLSX extraction
        try (InputStream fis = inputStream) {
            String text = tika.parseToString(fis);
            int wordCount = countWords(text);
            return new ParsingResult(text, 1, wordCount, false, null);
        }
    }

    private ParsingResult parseText(InputStream inputStream) throws IOException {
        String text = new String(inputStream.readAllBytes(), "UTF-8");
        int wordCount = countWords(text);

        return new ParsingResult(text, 1, wordCount, false, null);
    }

    private ParsingResult parseImage(InputStream inputStream) throws IOException, TikaException {
        // Use Tika for OCR-ready parsing
        String text = tika.parseToString(inputStream);
        int wordCount = countWords(text);
        boolean ocrRequired = text.trim().isEmpty();
        Double confidence = ocrRequired ? 0.0 : 0.95;

        return new ParsingResult(text, 1, wordCount, ocrRequired, confidence);
    }

    public ParsingResult parseWithOcr(InputStream inputStream, FileType fileType) {
        try {
            // For images, Tika can do basic OCR
            String text = tika.parseToString(inputStream);
            int wordCount = countWords(text);
            boolean hasContent = !text.trim().isEmpty();

            return new ParsingResult(text, 1, wordCount, !hasContent, hasContent ? 0.95 : 0.0);
        } catch (Exception e) {
            log.error("OCR parsing failed: {}", e.getMessage());
            return new ParsingResult("", 1, 0, true, 0.0);
        }
    }

    private int countWords(String text) {
        if (text == null || text.isBlank()) {
            return 0;
        }
        return text.trim().split("\\s+").length;
    }

    public record ParsingResult(
            String text,
            int pageCount,
            int wordCount,
            boolean ocrRequired,
            Double ocrConfidence
    ) {}
}