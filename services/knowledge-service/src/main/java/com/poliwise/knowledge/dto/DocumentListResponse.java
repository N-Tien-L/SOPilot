package com.poliwise.knowledge.dto;

import java.util.List;

public record DocumentListResponse(List<DocumentSummaryDto> data, PaginationDto pagination) {}
