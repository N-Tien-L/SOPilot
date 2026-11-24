package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.document.UploadValidator.FileType;
import com.sopilot.core.document.UploadValidator.Validated;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** FR-06: only text-layer PDF and UTF-8 Markdown, extension and magic bytes must agree. */
class UploadValidatorTest {

    private static byte[] ascii(String s) {
        return s.getBytes(StandardCharsets.US_ASCII);
    }

    private static void rejects(String name, byte[] content, HttpStatus status, String code) {
        assertThatThrownBy(() -> UploadValidator.validate(name, content))
                .isInstanceOfSatisfying(ApiException.class, e -> {
                    assertThat(e.status()).as(name).isEqualTo(status);
                    assertThat(e.code()).as(name).isEqualTo(code);
                });
    }

    @Test
    void acceptsPdfByMagicBytesAndComputesTheDigest() {
        Validated v = UploadValidator.validate("QT-MH-01.PDF", ascii("%PDF-1.7 body"));

        assertThat(v.type()).isEqualTo(FileType.PDF);
        assertThat(v.type().mimeType()).isEqualTo("application/pdf");
        assertThat(v.originalName()).isEqualTo("QT-MH-01.PDF");
        assertThat(v.sha256()).hasSize(32);
        assertThat(v.sha256Hex()).hasSize(64).matches("[0-9a-f]+");
        assertThat(v.size()).isEqualTo(13);
    }

    @Test
    void sameBytesGiveTheSameDigestAndDifferentBytesDoNot() {
        byte[] a = ascii("# a");
        assertThat(UploadValidator.validate("a.md", a).sha256Hex())
                .isEqualTo(UploadValidator.validate("renamed.markdown", a.clone()).sha256Hex())
                .isNotEqualTo(UploadValidator.validate("a.md", ascii("# b")).sha256Hex());
    }

    @Test
    void acceptsUtf8MarkdownWithDiacriticsAndABom() {
        assertThat(UploadValidator.validate("sop.md", "# Quy trình mua hàng\n".getBytes(StandardCharsets.UTF_8)).type())
                .isEqualTo(FileType.MD);
        byte[] bom = new byte[] {(byte) 0xEF, (byte) 0xBB, (byte) 0xBF, '#', ' ', 'x'};
        assertThat(UploadValidator.validate("sop.markdown", bom).type()).isEqualTo(FileType.MD);
    }

    @Test
    void refusesTxtAndWordWithAHintAndOtherTypesGenerically() {
        rejects("a.txt", ascii("text"), HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_TYPE");
        assertThatThrownBy(() -> UploadValidator.validate("a.txt", ascii("text")))
                .hasMessage("UNSUPPORTED_TYPE")
                .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.clientMessage()).contains(".md"));
        assertThatThrownBy(() -> UploadValidator.validate("a.docx", ascii("PK")))
                .isInstanceOfSatisfying(ApiException.class, e -> assertThat(e.clientMessage()).contains("PDF"));
        for (String name : new String[] {"a.doc", "a.xlsx", "a.png", "a.jpg", "a.html", "noextension", "a."}) {
            rejects(name, ascii("x"), HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_TYPE");
        }
    }

    @Test
    void extensionAndContentMustAgree() {
        rejects("fake.pdf", ascii("# markdown"), HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_TYPE");
        rejects("short.pdf", ascii("%PD"), HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_TYPE");
        rejects("nul.md", new byte[] {'#', 0, 'a'}, HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_TYPE");
        rejects("%PDF-.docx", ascii("%PDF-1.7"), HttpStatus.UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_TYPE");
    }

    @Test
    void markdownThatIsNotUtf8IsAnEncodingError() {
        rejects("latin.md", "café".getBytes(StandardCharsets.ISO_8859_1), HttpStatus.UNSUPPORTED_MEDIA_TYPE,
                "INVALID_ENCODING");
        rejects("utf16.md", "# hi".getBytes(StandardCharsets.UTF_16LE), HttpStatus.UNSUPPORTED_MEDIA_TYPE,
                "UNSUPPORTED_TYPE");
    }

    @Test
    void emptyOrNamelessFilesAreBadRequests() {
        rejects("a.md", new byte[0], HttpStatus.BAD_REQUEST, "VALIDATION_FAILED");
        rejects("a.md", null, HttpStatus.BAD_REQUEST, "VALIDATION_FAILED");
        rejects("  ", ascii("# x"), HttpStatus.BAD_REQUEST, "VALIDATION_FAILED");
        rejects(null, ascii("# x"), HttpStatus.BAD_REQUEST, "VALIDATION_FAILED");
    }

    @Test
    void theLimitIsExactlyTwentyMegabytes() {
        byte[] atLimit = new byte[(int) UploadValidator.MAX_BYTES];
        java.util.Arrays.fill(atLimit, (byte) 'a');
        assertThat(UploadValidator.validate("big.md", atLimit).size()).isEqualTo(UploadValidator.MAX_BYTES);

        byte[] over = new byte[(int) UploadValidator.MAX_BYTES + 1];
        java.util.Arrays.fill(over, (byte) 'a');
        rejects("big.md", over, HttpStatus.PAYLOAD_TOO_LARGE, "FILE_TOO_LARGE");
    }
}
