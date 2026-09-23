package com.poliwise.knowledge.dto;

public record PaginationDto(int page, int limit, long total, int totalPages) {}
