package com.poliwise.knowledge.service;

import lombok.extern.slf4j.Slf4j;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFParagraph;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

/**
 * Extract text content from DOCX files using Apache POI.
 */
@Service
@Slf4j
public class TextExtractionService {

    /**
     * Extract plain text from a DOCX file.
     * Returns empty string if extraction fails.
     */
    public String extractTextFromDocx(InputStream inputStream) {
        try (XWPFDocument document = new XWPFDocument(inputStream)) {
            StringBuilder text = new StringBuilder();
            
            List<XWPFParagraph> paragraphs = document.getParagraphs();
            for (int i = 0; i < paragraphs.size(); i++) {
                XWPFParagraph paragraph = paragraphs.get(i);
                String paragraphText = paragraph.getText();
                if (paragraphText != null && !paragraphText.isBlank()) {
                    text.append(paragraphText);
                    // Add newline for all paragraphs except the last one
                    if (i < paragraphs.size() - 1) {
                        text.append("\n");
                    }
                }
            }
            
            return text.toString();
        } catch (IOException e) {
            log.error("Failed to extract text from DOCX: {}", e.getMessage(), e);
            return "";
        }
    }

    /**
     * Check if file is a DOCX based on filename or content type.
     */
    public boolean isDocxFile(String filename, String contentType) {
        if (filename != null && filename.toLowerCase().endsWith(".docx")) {
            return true;
        }
        return contentType != null && (
            contentType.equals("application/vnd.openxmlformats-officedocument.wordprocessingml.document") ||
            contentType.equals("application/vnd.ms-word.document.macroEnabled.12")
        );
    }
}
