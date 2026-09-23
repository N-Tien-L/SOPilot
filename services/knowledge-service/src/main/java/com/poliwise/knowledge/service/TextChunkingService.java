package com.poliwise.knowledge.service;

import com.poliwise.knowledge.config.KnowledgeProperties;
import com.poliwise.knowledge.enums.ChunkingStrategy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class TextChunkingService {

    private static final Logger log = LoggerFactory.getLogger(TextChunkingService.class);

    private final KnowledgeProperties properties;

    public TextChunkingService(KnowledgeProperties properties) {
        this.properties = properties;
    }

    public List<Chunk> chunk(String text, ChunkingStrategy strategy, Integer customChunkSize, Integer customOverlap) {
        int chunkSize = customChunkSize != null ? customChunkSize : properties.getChunking().getDefaultChunkSize();
        int overlap = customOverlap != null ? customOverlap : properties.getChunking().getDefaultOverlap();

        return switch (strategy) {
            case RECURSIVE -> recursiveCharacterSplit(text, chunkSize, overlap);
            case FIXED_SIZE -> fixedSizeChunk(text, chunkSize, overlap);
            case SENTENCE -> sentenceChunk(text, chunkSize, overlap);
            case SEMANTIC -> semanticChunk(text, chunkSize, overlap);
        };
    }

    private List<Chunk> recursiveCharacterSplit(String text, int chunkSize, int overlap) {
        List<Chunk> chunks = new ArrayList<>();
        if (text == null || text.isBlank()) {
            return chunks;
        }

        List<String> separators = List.of(
                "\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "
        );

        int start = 0;
        int index = 0;
        int chunkIndex = 0;

        while (start < text.length()) {
            int end = Math.min(start + chunkSize, text.length());

            // Try to split at a separator near the end
            if (end < text.length()) {
                for (String sep : separators) {
                    int sepIdx = text.lastIndexOf(sep, end);
                    if (sepIdx > start + chunkSize / 2) {
                        end = sepIdx + sep.length();
                        break;
                    }
                }
            }

            String chunkText = text.substring(start, end).trim();
            if (!chunkText.isEmpty()) {
                chunks.add(new Chunk(chunkIndex++, start, end, chunkText));
            }

            start = end - overlap;
            if (start <= (chunks.isEmpty() ? 0 : chunks.get(chunks.size() - 1).startChar())) {
                start = end;
            }
        }

        return chunks;
    }

    private List<Chunk> fixedSizeChunk(String text, int chunkSize, int overlap) {
        List<Chunk> chunks = new ArrayList<>();
        if (text == null || text.isBlank()) {
            return chunks;
        }

        int start = 0;
        int chunkIndex = 0;

        while (start < text.length()) {
            int end = Math.min(start + chunkSize, text.length());
            String chunkText = text.substring(start, end).trim();

            if (!chunkText.isEmpty()) {
                chunks.add(new Chunk(chunkIndex++, start, end, chunkText));
            }

            start = end - overlap;
            if (start <= 0) {
                break;
            }
        }

        log.debug("Created {} chunks using FIXED_SIZE strategy", chunks.size());
        return chunks;
    }

    private List<Chunk> sentenceChunk(String text, int targetSize, int overlap) {
        List<Chunk> chunks = new ArrayList<>();
        if (text == null || text.isBlank()) {
            return chunks;
        }

        // Split by sentence endings
        String[] sentences = text.split("(?<=[.!?])\\s+");
        StringBuilder currentChunk = new StringBuilder();
        int chunkIndex = 0;
        int chunkStart = 0;

        for (String sentence : sentences) {
            if (currentChunk.length() + sentence.length() > targetSize && currentChunk.length() > 0) {
                // Finish current chunk
                String chunkText = currentChunk.toString().trim();
                if (!chunkText.isEmpty()) {
                    int chunkEnd = chunkStart + chunkText.length();
                    chunks.add(new Chunk(chunkIndex++, chunkStart, chunkEnd, chunkText));
                    chunkStart = chunkEnd - overlap;
                }

                // Start new chunk with overlap
                String overlapText = currentChunk.toString();
                int overlapStart = Math.max(0, overlapText.length() - overlap);
                currentChunk = new StringBuilder(overlapText.substring(overlapStart));
            }

            currentChunk.append(sentence).append(" ");
        }

        // Add remaining chunk
        String remaining = currentChunk.toString().trim();
        if (!remaining.isEmpty()) {
            int finalChunkEnd = chunkStart + remaining.length();
            chunks.add(new Chunk(chunkIndex, chunkStart, finalChunkEnd, remaining));
        }

        log.debug("Created {} chunks using SENTENCE strategy", chunks.size());
        return chunks;
    }

    private List<Chunk> semanticChunk(String text, int targetSize, int overlap) {
        // Semantic chunking: split by paragraphs first, then merge small ones
        List<Chunk> chunks = new ArrayList<>();
        if (text == null || text.isBlank()) {
            return chunks;
        }

        // Split by double newlines (paragraphs)
        String[] paragraphs = text.split("\\n\\s*\\n");
        StringBuilder currentChunk = new StringBuilder();
        int chunkIndex = 0;
        int charPosition = 0;

        for (String paragraph : paragraphs) {
            paragraph = paragraph.trim();
            if (paragraph.isEmpty()) continue;

            if (currentChunk.length() + paragraph.length() + 2 > targetSize && currentChunk.length() > 0) {
                // Finish current chunk
                String chunkText = currentChunk.toString().trim();
                if (!chunkText.isEmpty()) {
                    int chunkEnd = charPosition + chunkText.length();
                    chunks.add(new Chunk(chunkIndex++, charPosition, chunkEnd, chunkText));
                    charPosition = chunkEnd - overlap;
                }

                // Keep overlap
                String overlapText = currentChunk.toString();
                int overlapStart = Math.max(0, overlapText.length() - overlap);
                currentChunk = new StringBuilder(overlapText.substring(overlapStart));
            }

            currentChunk.append(paragraph).append("\n\n");
        }

        // Add remaining
        String remaining = currentChunk.toString().trim();
        if (!remaining.isEmpty()) {
            int finalChunkEnd = charPosition + remaining.length();
            chunks.add(new Chunk(chunkIndex, charPosition, finalChunkEnd, remaining));
        }

        log.debug("Created {} chunks using SEMANTIC strategy", chunks.size());
        return chunks;
    }

    public record Chunk(
            int index,
            int startChar,
            int endChar,
            String text
    ) {}
}