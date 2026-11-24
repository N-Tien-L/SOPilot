package com.sopilot.core.common;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

class GlobalExceptionHandlerTest {

    private final GlobalExceptionHandler handler = new GlobalExceptionHandler();

    @Test
    void aValueThatCannotBeConvertedIsABadRequestThatNamesTheParameterOnly() {
        var e = new MethodArgumentTypeMismatchException("secret-looking-value", UUID.class, "categoryId", null, null);

        var response = handler.handleTypeMismatch(e);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        String body = String.valueOf(response.getBody());
        assertThat(body).contains("VALIDATION_FAILED").contains("categoryId").doesNotContain("secret-looking-value");
    }
}
