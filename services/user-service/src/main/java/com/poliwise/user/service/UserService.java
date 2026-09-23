package com.poliwise.user.service;

import com.poliwise.user.dto.*;
import com.poliwise.user.dto.event.UserRevokedEvent;
import com.poliwise.user.dto.event.UserStatusChangedEvent;
import com.poliwise.user.dto.event.ProfileUpdatedEvent;
import com.poliwise.user.entity.Department;
import com.poliwise.user.entity.User;
import com.poliwise.user.entity.UserProfile;
import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.event.UserEventPublisher;
import com.poliwise.user.exception.InvalidStatusTransitionException;
import com.poliwise.user.exception.UserDeactivatedException;
import com.poliwise.user.exception.UserNotFoundException;
import com.poliwise.user.repository.DepartmentRepository;
import com.poliwise.user.repository.UserRepository;
import com.poliwise.user.repository.UserSpecification;
import com.poliwise.user.repository.UserProfileRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;

import java.util.Map;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.Set;
import java.util.UUID;

@Service
public class UserService {

    private static final Logger log = LoggerFactory.getLogger(UserService.class);

    private static final Set<AccountStatus> ACTIVE_STATUSES = Set.of(AccountStatus.ACTIVE);
    private static final Set<AccountStatus> ALL_STATUSES = Set.of(AccountStatus.values());

    private final UserRepository userRepository;
    private final UserProfileRepository userProfileRepository;
    private final DepartmentRepository departmentRepository;
    private final UserEventPublisher eventPublisher;

    public UserService(UserRepository userRepository,
                       UserProfileRepository userProfileRepository,
                       DepartmentRepository departmentRepository,
                       UserEventPublisher eventPublisher) {
        this.userRepository = userRepository;
        this.userProfileRepository = userProfileRepository;
        this.departmentRepository = departmentRepository;
        this.eventPublisher = eventPublisher;
    }

    // GET PROFILE

    @Transactional(readOnly = true)
    public UserResponse getProfile(UUID userId) {
        User user = findActiveUserById(userId);
        return toResponse(user);
    }

    @Transactional(readOnly = true)
    public UserResponse getProfileAdmin(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found: " + userId));
        return toResponse(user);
    }

    @Transactional(readOnly = true)
    public UserStatusResponse getMyStatus(UUID userId) {
        User user = userRepository.findDetailedById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found: " + userId));
        return new UserStatusResponse(
                user.getId(),
                user.getStatus(),
                user.getRole(),
                user.isActive(),
                null
        );
    }

    // UPDATE PROFILE

    @Transactional
    public UserResponse updateProfile(UUID userId, UpdateProfileRequest request) {
        User user = findActiveUserById(userId);
        UserProfile profile = resolveOrCreateProfile(user);

        Map<String, Object> oldValues = captureProfileValues(profile);
        String[] changedFields = determineChangedFields(request, profile);

        profile.setFullName(request.fullName());
        profile.setPhone(request.phone());
        profile.setPosition(request.position());
        profile.setAvatarUrl(request.avatarUrl());
        profile.setBio(request.bio());
        profile.setDateOfBirth(request.dateOfBirth());
        profile.setUpdatedAt(OffsetDateTime.now());

        userProfileRepository.save(profile);

        User saved = userRepository.save(user);
        log.info("Updated profile for userId={}", userId);

        if (changedFields.length > 0) {
            Map<String, Object> newValues = captureProfileValues(profile);
            ProfileUpdatedEvent event = ProfileUpdatedEvent.create(
                    user.getId(),
                    user.getUsername(),
                    user.getId(),
                    user.getUsername(),
                    oldValues,
                    newValues,
                    changedFields
            );
            eventPublisher.publishProfileUpdated(event);
        }

        return toResponse(saved);
    }

    private Map<String, Object> captureProfileValues(UserProfile p) {
        return Map.of(
                "fullName", p.getFullName() != null ? p.getFullName() : "",
                "phone", p.getPhone() != null ? p.getPhone() : "",
                "position", p.getPosition() != null ? p.getPosition() : "",
                "bio", p.getBio() != null ? p.getBio() : "",
                "dateOfBirth", p.getDateOfBirth() != null ? p.getDateOfBirth().toString() : ""
        );
    }

    private String[] determineChangedFields(UpdateProfileRequest req, UserProfile p) {
        java.util.ArrayList<String> changed = new java.util.ArrayList<>();
        if (!equalsSafe(req.fullName(), p.getFullName())) changed.add("fullName");
        if (!equalsSafe(req.phone(), p.getPhone())) changed.add("phone");
        if (!equalsSafe(req.position(), p.getPosition())) changed.add("position");
        if (!equalsSafe(req.avatarUrl(), p.getAvatarUrl())) changed.add("avatarUrl");
        if (!equalsSafe(req.bio(), p.getBio())) changed.add("bio");
        if (!equalsSafe(req.dateOfBirth(), p.getDateOfBirth() != null ? p.getDateOfBirth().toString() : null)) changed.add("dateOfBirth");
        return changed.toArray(new String[0]);
    }

    private boolean equalsSafe(Object a, Object b) {
        return a == null ? b == null : a.equals(b);
    }

    // CHANGE DEPARTMENT

    // SEARCH (Admin / Manager)

    @Transactional(readOnly = true)
    public PageResponse<UserResponse> searchUsers(UserSearchCriteria criteria, int page, int size, String sortBy, String sortDir) {
        Sort sort = Sort.by(
                Sort.Direction.fromString(sortDir != null ? sortDir : "ASC"),
                sortBy != null ? sortBy : "username"
        );
        Pageable pageable = PageRequest.of(page, size, sort);

        Page<User> result = userRepository.findAll(
                UserSpecification.withFilters(
                        criteria.keyword(),
                        criteria.role(),
                        criteria.status(),
                        criteria.departmentId(),
                        criteria.includeDeleted() == null || !criteria.includeDeleted()
                ),
                pageable
        );

        return toPageResponse(result);
    }

    // CHANGE STATUS

    @Transactional
    public UserResponse changeStatus(UUID userId, ChangeStatusRequest request, UUID changedBy) {
        User user = userRepository.findByIdForUpdate(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found: " + userId));

        AccountStatus previousStatus = user.getStatus();
        AccountStatus newStatus = request.newStatus();

        validateStatusTransition(previousStatus, newStatus);

        user.setStatus(newStatus);

        if (newStatus == AccountStatus.REVOKED) {
            user.setRevokedAt(OffsetDateTime.now());
            user.setDeactivatedAt(null);
        } else if (newStatus == AccountStatus.DEACTIVATED) {
            user.setDeactivatedAt(OffsetDateTime.now());
            user.setRevokedAt(null);
        } else if (previousStatus == AccountStatus.REVOKED) {
            user.setRevokedAt(null);
        } else if (previousStatus == AccountStatus.DEACTIVATED) {
            user.setDeactivatedAt(null);
        }

        if (request.newRole() != null) {
            user.setRole(request.newRole());
        }

        // Set timestamps for status changes
        if (newStatus == AccountStatus.DEACTIVATED && previousStatus != AccountStatus.DEACTIVATED) {
            user.setDeactivatedAt(java.time.OffsetDateTime.now());
        } else if (newStatus == AccountStatus.ACTIVE && previousStatus == AccountStatus.DEACTIVATED) {
            user.setDeactivatedAt(null);
        } else if (newStatus == AccountStatus.REVOKED && previousStatus != AccountStatus.REVOKED) {
            user.setRevokedAt(java.time.OffsetDateTime.now());
        }

        User saved = userRepository.save(user);

        UserStatusChangedEvent event = UserStatusChangedEvent.create(
                user.getId(),
                user.getUsername(),
                previousStatus,
                newStatus,
                user.getRole(),
                changedBy
        );
        eventPublisher.publishStatusChanged(event);

        if (newStatus == AccountStatus.REVOKED) {
            UserRevokedEvent revokedEvent = UserRevokedEvent.create(
                    user.getId(),
                    user.getUsername(),
                    user.getRole(),
                    changedBy,
                    "Status changed to REVOKED"
            );
            eventPublisher.publishRevoked(revokedEvent);
        }

        log.info("Changed status of userId={} from {} to {} by {}", userId, previousStatus, newStatus, changedBy);
        return toResponse(saved);
    }

    // SOFT DELETE (Anonymize PII)

    @Transactional
    public void softDelete(UUID userId, UUID deletedBy) {
        User user = userRepository.findByIdForUpdate(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found: " + userId));

        if (user.getStatus() == AccountStatus.REVOKED) {
            throw new IllegalArgumentException("User already revoked: " + userId);
        }

        user.setUsername("deleted_" + user.getId());
        user.setEmail("deleted_" + user.getId() + "@anonymized.local");
        user.setStatus(AccountStatus.REVOKED);

        if (user.getProfile() != null) {
            UserProfile profile = user.getProfile();
            profile.setFullName("[DELETED]");
            profile.setPhone(null);
            profile.setBio(null);
            profile.setAvatarUrl(null);
            profile.setDateOfBirth(null);
            profile.setEmployeeCode(null);
        }

        userRepository.save(user);

        UserRevokedEvent revokedEvent = UserRevokedEvent.create(
                user.getId(),
                "[DELETED]",
                user.getRole(),
                deletedBy,
                "User soft-deleted and PII anonymized"
        );
        eventPublisher.publishRevoked(revokedEvent);

        log.info("Soft-deleted userId={} by {} -- PII anonymized", userId, deletedBy);
    }

    // UPDATE USER (Admin — role + status + department)
    @Transactional
    public UserResponse updateUser(UUID userId, UpdateUserRequest request, UUID changedBy) {
        User user = userRepository.findByIdForUpdate(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found: " + userId));

        if (request.status() != null && request.status() != user.getStatus()) {
            AccountStatus previousStatus = user.getStatus();
            AccountStatus newStatus = request.status();
            validateStatusTransition(previousStatus, newStatus);
            user.setStatus(newStatus);

            UserStatusChangedEvent event = UserStatusChangedEvent.create(
                    user.getId(),
                    user.getUsername(),
                    previousStatus,
                    newStatus,
                    user.getRole(),
                    changedBy
            );
            eventPublisher.publishStatusChanged(event);

            if (newStatus == AccountStatus.REVOKED) {
                UserRevokedEvent revokedEvent = UserRevokedEvent.create(
                        user.getId(),
                        user.getUsername(),
                        user.getRole(),
                        changedBy,
                        "Status changed to REVOKED via admin update"
                );
                eventPublisher.publishRevoked(revokedEvent);
            }

            log.info("Changed status of userId={} from {} to {} by {}", userId, previousStatus, newStatus, changedBy);
        }

        if (request.role() != null) {
            user.setRole(request.role());
            log.info("Changed role of userId={} to {} by {}", userId, request.role(), changedBy);
        }

        if (request.departmentId() != null) {
            Department department = departmentRepository.findById(request.departmentId())
                    .orElseThrow(() -> new UserNotFoundException(
                            "Department not found: " + request.departmentId()));
            if (!Boolean.TRUE.equals(department.getIsActive())) {
                throw new IllegalArgumentException(
                        "Cannot assign user to inactive department: " + department.getName());
            }
            user.setDepartment(department);
            log.info("Changed department of userId={} to departmentId={} by {}",
                    userId, request.departmentId(), changedBy);
        } else if (request.departmentId() == null && request.status() == null && request.role() == null) {
            // No-op — nothing to update
        }

        User saved = userRepository.save(user);
        return toResponse(saved);
    }

    // STATS

    @Transactional(readOnly = true)
    public UserStatsResponse getStats() {
        long total = userRepository.count();
        long active = userRepository.countByStatus(AccountStatus.ACTIVE);
        return new UserStatsResponse(total, active);
    }

    // INTERNAL HELPERS

    private User findActiveUserById(UUID userId) {
        User user = userRepository.findDetailedById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found: " + userId));

        if (user.getStatus() == AccountStatus.DEACTIVATED) {
            throw new UserDeactivatedException("Account is deactivated");
        }
        if (user.getStatus() == AccountStatus.REVOKED) {
            throw new UserDeactivatedException("Account is revoked");
        }
        return user;
    }

    private UserProfile resolveOrCreateProfile(User user) {
        if (user.getProfile() == null) {
            UserProfile profile = UserProfile.builder()
                    .id(UUID.randomUUID())
                    .user(user)
                    .fullName(user.getUsername())
                    .employeeCode("EMP-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase())
                    .joinedDate(java.time.LocalDate.now())
                    .createdAt(OffsetDateTime.now())
                    .updatedAt(OffsetDateTime.now())
                    .build();
            user.setProfile(profile);
        }
        return user.getProfile();
    }

    private void validateStatusTransition(AccountStatus from, AccountStatus to) {
        if (from == to) {
            throw new InvalidStatusTransitionException("User is already in status: " + from);
        }
        if (from == AccountStatus.REVOKED) {
            throw new InvalidStatusTransitionException(
                    "REVOKED accounts cannot be reactivated via this endpoint");
        }
    }

    private UserResponse toResponse(User user) {
        UserProfile profile = user.getProfile();
        return new UserResponse(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                user.getRole(),
                user.getStatus(),
                user.getDepartment() != null ? user.getDepartment().getId() : null,
                user.getDepartment() != null
                        ? new UserResponse.DepartmentInfo(
                                user.getDepartment().getId(),
                                user.getDepartment().getName(),
                                user.getDepartment().getCode())
                        : null,
                profile != null
                        ? new UserResponse.UserProfileInfo(
                                profile.getId(),
                                profile.getFullName(),
                                profile.getPhone(),
                                profile.getPosition(),
                                profile.getAvatarUrl(),
                                profile.getBio(),
                                profile.getDateOfBirth(),
                                profile.getEmployeeCode(),
                                profile.getJoinedDate())
                        : null,
                user.getCreatedAt(),
                user.getUpdatedAt()
        );
    }

    private PageResponse<UserResponse> toPageResponse(Page<User> page) {
        return new PageResponse<>(
                page.getContent().stream().map(this::toResponse).toList(),
                page.getNumber(),
                page.getSize(),
                page.getTotalElements(),
                page.getTotalPages(),
                page.isFirst(),
                page.isLast()
        );
    }
}
