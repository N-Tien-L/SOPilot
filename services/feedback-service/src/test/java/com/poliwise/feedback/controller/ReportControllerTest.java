package com.poliwise.feedback.controller;

import com.poliwise.feedback.dto.response.ReportDownload;
import com.poliwise.feedback.enums.ExportFormat;
import com.poliwise.feedback.security.JwtAuthenticationToken;
import com.poliwise.feedback.security.UserPrincipal;
import com.poliwise.feedback.service.ReportExportService;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ReportControllerTest {

    @Test
    void downloadStreamsCsvWithCorrectHeaders() throws Exception {
        ReportExportService service = mock(ReportExportService.class);
        ReportController controller = new ReportController(service);
        UUID reportId = UUID.randomUUID();
        UUID userId = UUID.randomUUID();
        byte[] content = "column\nvalue\n".getBytes(StandardCharsets.UTF_8);
        JwtAuthenticationToken authentication = new JwtAuthenticationToken(
                UserPrincipal.builder().userId(userId).username("admin").role("ADMIN").build(),
                "token",
                List.of()
        );
        when(service.openReport(reportId, userId, true)).thenReturn(
                new ReportDownload(new ByteArrayInputStream(content), ExportFormat.CSV, content.length)
        );

        ResponseEntity<StreamingResponseBody> response = controller.download(reportId, authentication);
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        response.getBody().writeTo(output);

        assertThat(response.getStatusCode().value()).isEqualTo(200);
        assertThat(response.getHeaders().getContentType())
                .isEqualTo(MediaType.parseMediaType("text/csv; charset=UTF-8"));
        assertThat(response.getHeaders().getContentDisposition().getFilename()).endsWith(".csv");
        assertThat(response.getHeaders().getContentLength()).isEqualTo(content.length);
        assertThat(output.toByteArray()).isEqualTo(content);
    }
}
