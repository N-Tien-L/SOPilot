package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import org.springframework.http.HttpStatus;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Map;

/**
 * Accepts only a text-layer PDF or a UTF-8 Markdown file up to 20 MB (FR-06, TECH §5.5): the extension
 * and the content must agree. DOCX is deferred (owner, 2026-10-20) and TXT dropped (2026-10-21), so both
 * are refused with {@code 415} and a hint, before anything is stored. Nothing is converted on the server.
 */
public final class UploadValidator {

    public static final long MAX_BYTES = 20L * 1024 * 1024;

    private static final byte[] PDF_MAGIC = "%PDF-".getBytes(StandardCharsets.US_ASCII);
    private static final Map<String, String> HINTS = Map.of(
            "txt", "Plain text files are not supported. Save the file as Markdown (.md) and upload it again.",
            "docx", "Word files are not supported yet. Export the document to a PDF with a text layer and upload that.",
            "doc", "Word files are not supported yet. Export the document to a PDF with a text layer and upload that.");

    private UploadValidator() {
    }

    public enum FileType {
        PDF("application/pdf"), MD("text/markdown");

        private final String mimeType;

        FileType(String mimeType) {
            this.mimeType = mimeType;
        }

        public String mimeType() {
            return mimeType;
        }
    }

    /** {@code sha256} is the raw 32-byte digest of the uploaded bytes. */
    public record Validated(FileType type, String originalName, byte[] sha256, long size) {
        public String sha256Hex() {
            return HexFormat.of().formatHex(sha256);
        }
    }

    public static Validated validate(String originalName, byte[] content) {
        String name = originalName == null ? "" : originalName.strip();
        if (name.isEmpty() || content == null || content.length == 0) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_FAILED", "A non-empty file is required.");
        }
        if (content.length > MAX_BYTES) {
            throw tooLarge();
        }
        String ext = extension(name);
        FileType type = switch (ext) {
            case "pdf" -> {
                requirePdf(content);
                yield FileType.PDF;
            }
            case "md", "markdown" -> {
                requireUtf8Markdown(content);
                yield FileType.MD;
            }
            default -> throw new ApiException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_TYPE",
                    HINTS.getOrDefault(ext, "This file type is not supported. Upload a PDF with a text layer or a Markdown (.md) file."));
        };
        return new Validated(type, name, sha256(content), content.length);
    }

    public static ApiException tooLarge() {
        return new ApiException(HttpStatus.PAYLOAD_TOO_LARGE, "FILE_TOO_LARGE", "The file is larger than 20 MB.");
    }

    private static void requirePdf(byte[] content) {
        if (content.length < PDF_MAGIC.length) {
            throw notPdf();
        }
        for (int i = 0; i < PDF_MAGIC.length; i++) {
            if (content[i] != PDF_MAGIC[i]) {
                throw notPdf();
            }
        }
    }

    private static ApiException notPdf() {
        return new ApiException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_TYPE",
                "The file is not a valid PDF. Upload a PDF with a text layer.");
    }

    private static void requireUtf8Markdown(byte[] content) {
        for (byte b : content) {
            if (b == 0) {
                throw new ApiException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_TYPE",
                        "The file is not a text Markdown file.");
            }
        }
        try {
            StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(content));
        } catch (CharacterCodingException e) {
            throw new ApiException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "INVALID_ENCODING",
                    "The Markdown file is not valid UTF-8. Save it as UTF-8 and upload it again.");
        }
    }

    private static String extension(String name) {
        int dot = name.lastIndexOf('.');
        return dot < 0 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    static byte[] sha256(byte[] content) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(content);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is not available");
        }
    }
}
