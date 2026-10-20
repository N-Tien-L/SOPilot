package com.poliwise.user.dto.roster;

import com.poliwise.user.entity.EmployeeRoster;
import com.poliwise.user.enums.RosterStatus;
import com.poliwise.user.enums.UserRole;

import java.time.OffsetDateTime;
import java.util.UUID;

public record RosterResponse(
        UUID id,
        String employeeCode,
        String email,
        String fullName,
        String phone,
        String position,
        UUID departmentId,
        String departmentName,
        String departmentCode,
        UserRole role,
        RosterStatus status,
        boolean isClaimed,
        OffsetDateTime claimedAt,
        UUID claimedUserId,
        UUID importBatchId,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static RosterResponse fromEntity(EmployeeRoster roster) {
        if (roster == null) {
            return null;
        }
        UUID deptId = roster.getDepartment() != null ? roster.getDepartment().getId() : null;
        String deptName = roster.getDepartment() != null ? roster.getDepartment().getName() : null;
        String deptCode = roster.getDepartment() != null ? roster.getDepartment().getCode() : null;
        UUID claimedUid = roster.getClaimedUser() != null ? roster.getClaimedUser().getId() : null;

        return new RosterResponse(
                roster.getId(),
                roster.getEmployeeCode(),
                roster.getEmail(),
                roster.getFullName(),
                roster.getPhone(),
                roster.getPosition(),
                deptId,
                deptName,
                deptCode,
                roster.getRole(),
                roster.getStatus(),
                roster.isClaimed(),
                roster.getClaimedAt(),
                claimedUid,
                roster.getImportBatchId(),
                roster.getCreatedAt(),
                roster.getUpdatedAt()
        );
    }
}
