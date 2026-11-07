package com.sopilot.core.document;

import com.sopilot.core.common.ApiException;
import com.sopilot.core.common.Cursor;
import org.junit.jupiter.api.Test;

import java.time.OffsetDateTime;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentHelpersTest {

    @Test
    void titleIsTheFileNameWithoutItsExtension() {
        assertThat(DocumentService.titleFrom("QT-MH-01.pdf")).isEqualTo("QT-MH-01");
        assertThat(DocumentService.titleFrom("Quy trình v1.2.final.md")).isEqualTo("Quy trình v1.2.final");
        assertThat(DocumentService.titleFrom(".md")).isEqualTo(".md");
        assertThat(DocumentService.titleFrom("x".repeat(300) + ".md")).hasSize(200);
    }

    @Test
    void objectKeyHasNoFileNameInIt() {
        UUID w = UUID.randomUUID();
        UUID d = UUID.randomUUID();
        UUID v = UUID.randomUUID();

        assertThat(DocumentService.objectKey(w, d, v))
                .isEqualTo("workspaces/" + w + "/documents/" + d + "/versions/" + v);
    }

    @Test
    void everyKnownFailureCodeHasAFixedMessageAndUnknownOnesAreGeneric() {
        for (String code : new String[] {"NO_TEXT_LAYER", "ENCRYPTED_PDF", "CORRUPT_FILE", "UNSUPPORTED_TYPE",
                "INVALID_ENCODING", "EMPTY_CONTENT", "EXTRACTION_ERROR", "EMBEDDING_ERROR", "OBJECT_NOT_FOUND",
                "RETRY_EXHAUSTED", "DISPATCH_FAILED"}) {
            assertThat(FailureMessages.normalize(code)).isEqualTo(code);
            assertThat(FailureMessages.forCode(code)).isNotBlank();
        }
        assertThat(FailureMessages.normalize("java.lang.NullPointerException")).isEqualTo("EXTRACTION_ERROR");
        assertThat(FailureMessages.normalize(null)).isEqualTo("EXTRACTION_ERROR");
        assertThat(FailureMessages.forCode("whatever")).isNotBlank();
    }

    @Test
    void effectiveDateIsParsedLeniently() {
        assertThat(VersionStatusService.parseDate("2026-01-15")).isEqualTo(java.time.LocalDate.of(2026, 1, 15));
        assertThat(VersionStatusService.parseDate(" 2026-01-15 ")).isNotNull();
        assertThat(VersionStatusService.parseDate("15/01/2026")).isNull();
        assertThat(VersionStatusService.parseDate("tháng 1 năm 2026")).isNull();
        assertThat(VersionStatusService.parseDate("")).isNull();
        assertThat(VersionStatusService.parseDate(null)).isNull();
    }

    @Test
    void cursorRoundTripsAndRejectsGarbage() {
        Cursor cursor = new Cursor(OffsetDateTime.parse("2026-11-05T08:00:00.123456Z"), UUID.randomUUID());

        assertThat(Cursor.decode(cursor.encode())).isEqualTo(cursor);
        assertThat(Cursor.decode(null)).isNull();
        assertThat(Cursor.decode(" ")).isNull();
        assertThatThrownBy(() -> Cursor.decode("garbage!")).isInstanceOf(ApiException.class);
        assertThat(Cursor.limit(null)).isEqualTo(20);
        assertThat(Cursor.limit(0)).isEqualTo(1);
        assertThat(Cursor.limit(1000)).isEqualTo(100);
    }
}
