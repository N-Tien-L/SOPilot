package com.poliwise.user.dto.roster;

public record RosterRowError(
        int row,
        String employeeCode,
        String email,
        String reason
) {}
