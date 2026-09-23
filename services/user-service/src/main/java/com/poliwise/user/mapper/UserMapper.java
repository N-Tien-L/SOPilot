package com.poliwise.user.mapper;

import com.poliwise.user.dto.UserResponse;
import com.poliwise.user.entity.Department;
import com.poliwise.user.entity.User;
import com.poliwise.user.entity.UserProfile;

public class UserMapper {

    private UserMapper() {}

    public static UserResponse toResponse(User user) {
        if (user == null) return null;

        return new UserResponse(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.getRole(),
                user.getStatus(),
                user.getDepartment() != null ? user.getDepartment().getId() : null,
                toDepartmentInfo(user.getDepartment()),
                toProfileInfo(user.getProfile()),
                user.getCreatedAt(),
                user.getUpdatedAt()
        );
    }

    public static UserResponse.DepartmentInfo toDepartmentInfo(Department department) {
        if (department == null) return null;
        return new UserResponse.DepartmentInfo(
                department.getId(),
                department.getName(),
                department.getCode()
        );
    }

    public static UserResponse.UserProfileInfo toProfileInfo(UserProfile profile) {
        if (profile == null) return null;
        return new UserResponse.UserProfileInfo(
                profile.getId(),
                profile.getFullName(),
                profile.getPhone(),
                profile.getPosition(),
                profile.getAvatarUrl(),
                profile.getBio(),
                profile.getDateOfBirth(),
                profile.getEmployeeCode(),
                profile.getJoinedDate()
        );
    }
}
