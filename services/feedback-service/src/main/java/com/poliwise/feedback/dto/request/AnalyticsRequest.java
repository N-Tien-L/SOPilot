package com.poliwise.feedback.dto.request;

import java.time.LocalDate;
import java.util.UUID;

public record AnalyticsRequest(
        LocalDate fromDate,
        LocalDate toDate,
        UUID departmentId
) {}
