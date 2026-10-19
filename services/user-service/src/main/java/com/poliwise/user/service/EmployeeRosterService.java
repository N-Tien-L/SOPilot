package com.poliwise.user.service;

import com.poliwise.user.dto.event.UserAssignedToDepartmentEvent;
import com.poliwise.user.dto.event.UserRegisteredEvent;
import com.poliwise.user.dto.roster.ClaimRosterRequest;
import com.poliwise.user.dto.roster.AdmitGoogleLoginRequest;
import com.poliwise.user.dto.roster.ClaimRosterResponse;
import com.poliwise.user.dto.roster.RosterResponse;
import com.poliwise.user.entity.EmployeeRoster;
import com.poliwise.user.entity.User;
import com.poliwise.user.entity.UserProfile;
import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.RosterStatus;
import com.poliwise.user.event.UserEventPublisher;
import com.poliwise.user.exception.RosterAlreadyClaimedException;
import com.poliwise.user.exception.RosterDeactivatedException;
import com.poliwise.user.exception.RosterNotFoundException;
import com.poliwise.user.repository.EmployeeRosterRepository;
import com.poliwise.user.repository.EmployeeRosterSpecification;
import com.poliwise.user.repository.UserProfileRepository;
import com.poliwise.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@Service
@RequiredArgsConstructor
@Slf4j
public class EmployeeRosterService {

    private final EmployeeRosterRepository employeeRosterRepository;
    private final UserRepository userRepository;
    private final UserProfileRepository userProfileRepository;
    private final UserEventPublisher userEventPublisher;

    /** Every Google login checks admission. A bound identity follows its claimed user, not email. */
    @Transactional
    public ClaimRosterResponse admitGoogleLogin(AdmitGoogleLoginRequest request) {
        EmployeeRoster roster = (request.userId() == null
                ? employeeRosterRepository.findByEmailIgnoreCaseForUpdate(request.email().trim().toLowerCase(Locale.ROOT))
                : employeeRosterRepository.findByClaimedUserIdForUpdate(request.userId()))
                .orElseThrow(() -> new RosterNotFoundException(
                        "Tài khoản chưa nằm trong danh bạ nhân sự của tổ chức. Vui lòng liên hệ HR."));
        if (roster.getStatus() == RosterStatus.DEACTIVATED) {
            throw new RosterDeactivatedException("Định danh nhân sự đã bị vô hiệu hóa. Vui lòng liên hệ HR.");
        }
        if (roster.isClaimed() && roster.getStatus() == RosterStatus.CLAIMED && roster.getClaimedUser() != null) {
            User user = roster.getClaimedUser();
            if (request.userId() != null && !request.userId().equals(user.getId())) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Roster identity does not match user");
            }
            UserProfile profile = userProfileRepository.findByUser_Id(user.getId())
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.CONFLICT, "Claimed roster has no user profile"));
            return toClaimResponse(user, profile, roster);
        }
        if (request.userId() != null || roster.isClaimed() || roster.getStatus() != RosterStatus.PENDING) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Roster claim state is inconsistent");
        }
        return claimRoster(new ClaimRosterRequest(request.email(), null));
    }

    /**
     * Tra cứu danh bạ nhân sự nạp trước với phân trang và bộ lọc linh hoạt.
     */
    @Transactional(readOnly = true)
    public Page<RosterResponse> searchRoster(
            String keyword,
            UUID departmentId,
            RosterStatus status,
            Boolean isClaimed,
            Pageable pageable) {

        Specification<EmployeeRoster> spec = EmployeeRosterSpecification.withFilters(
                keyword, departmentId, status, isClaimed, true);

        return employeeRosterRepository.findAll(spec, pageable)
                .map(RosterResponse::fromEntity);
    }

    /**
     * Lấy chi tiết một bản ghi danh bạ theo ID.
     */
    @Transactional(readOnly = true)
    public RosterResponse getById(UUID id) {
        return employeeRosterRepository.findById(id)
                .filter(r -> r.getDeletedAt() == null)
                .map(RosterResponse::fromEntity)
                .orElseThrow(() -> new RosterNotFoundException("Không tìm thấy thông tin danh bạ với ID: " + id));
    }

    /**
     * Vô hiệu hóa một bản ghi danh bạ (dành cho HR/Admin khi nhân sự hủy nhận việc).
     */
    @Transactional
    public void deactivateRoster(UUID id, UUID adminUserId) {
        EmployeeRoster roster = employeeRosterRepository.findById(id)
                .filter(r -> r.getDeletedAt() == null)
                .orElseThrow(() -> new RosterNotFoundException("Không tìm thấy thông tin danh bạ với ID: " + id));

        if (roster.isClaimed()) {
            throw new IllegalStateException("Không thể vô hiệu hóa danh bạ của nhân sự đã kích hoạt tài khoản");
        }

        roster.setStatus(RosterStatus.DEACTIVATED);
        roster.setUpdatedBy(adminUserId);
        employeeRosterRepository.save(roster);
        log.info("Roster entry {} has been deactivated by admin {}", id, adminUserId);
    }

    /**
     * Thực thi JIT Claim nguyên tử (Atomic JIT Claim Engine) dành cho auth-service:
     * - Khóa bản ghi danh bạ với Pessimistic Write Lock (FOR UPDATE).
     * - Kiểm tra tính hợp lệ và trạng thái PENDING.
     * - Tạo thực thể User & UserProfile.
     * - Đánh dấu is_claimed=true, status=CLAIMED.
     * - Phát sự kiện RabbitMQ UserRegisteredEvent & UserAssignedToDepartmentEvent.
     */
    @Transactional
    public ClaimRosterResponse claimRoster(ClaimRosterRequest request) {
        String normalizedEmail = request.email().trim().toLowerCase(Locale.ROOT);
        log.info("Processing JIT Claim request for email: {}", normalizedEmail);

        // 1. Khóa bản ghi danh bạ để chống race condition khi click đúp hoặc spam đăng nhập
        EmployeeRoster roster = employeeRosterRepository.findByEmailIgnoreCaseForUpdate(normalizedEmail)
                .orElseThrow(() -> new RosterNotFoundException(
                        "Tài khoản chưa nằm trong danh bạ nhân sự của tổ chức. Vui lòng liên hệ HR."));

        // 2. Validate trạng thái vòng đời
        if (roster.getStatus() == RosterStatus.DEACTIVATED) {
            throw new RosterDeactivatedException(
                    "Định danh nhân sự của tài khoản này đã bị vô hiệu hóa. Vui lòng liên hệ HR.");
        }

        if (roster.isClaimed() || roster.getStatus() == RosterStatus.CLAIMED) {
            throw new RosterAlreadyClaimedException(
                    "Định danh nhân sự này đã được kích hoạt trước đó.");
        }

        // 3. Khởi tạo tài khoản User nếu chưa tồn tại
        User user = userRepository.findByEmailIgnoreCase(normalizedEmail).orElseGet(() -> {
            User newUser = new User();
            newUser.setId(UUID.randomUUID());

            String usernamePrefix = normalizedEmail.split("@")[0].toLowerCase().replaceAll("[^a-z0-9_]", "_");
            if (usernamePrefix.length() < 3) {
                usernamePrefix = usernamePrefix + "_emp";
            }
            if (userRepository.existsByUsernameIgnoreCase(usernamePrefix)) {
                usernamePrefix = usernamePrefix + "_" + UUID.randomUUID().toString().substring(0, 4);
            }

            newUser.setUsername(usernamePrefix);
            newUser.setEmail(normalizedEmail);
            newUser.setPasswordHash("GOOGLE_OAUTH_JIT_UNUSABLE_PASSWORD");
            newUser.setRole(roster.getRole());
            newUser.setStatus(AccountStatus.ACTIVE);
            newUser.setDepartment(roster.getDepartment());

            return userRepository.save(newUser);
        });

        if (user.getStatus() != AccountStatus.ACTIVE) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Account is not active");
        }
        // Enrolling an existing account must not silently change its privileges or department.
        if (user.getRole() != roster.getRole()
                || !java.util.Objects.equals(user.getDepartment() == null ? null : user.getDepartment().getId(),
                        roster.getDepartment() == null ? null : roster.getDepartment().getId())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Existing account role/department differs from roster; contact HR");
        }

        // 4. Khởi tạo hồ sơ UserProfile nếu chưa tồn tại
        UserProfile profile = userProfileRepository.findByUser_Id(user.getId()).orElseGet(() -> {
            UserProfile newProfile = new UserProfile();
            newProfile.setId(UUID.randomUUID());
            newProfile.setUser(user);
            newProfile.setFullName(roster.getFullName());
            newProfile.setPhone(roster.getPhone());
            newProfile.setPosition(roster.getPosition());
            newProfile.setEmployeeCode(roster.getEmployeeCode());
            newProfile.setJoinedDate(LocalDate.now());

            return userProfileRepository.save(newProfile);
        });

        // 5. Cập nhật trạng thái roster sang CLAIMED
        OffsetDateTime now = OffsetDateTime.now();
        roster.setClaimed(true);
        roster.setStatus(RosterStatus.CLAIMED);
        roster.setClaimedAt(now);
        roster.setClaimedUser(user);
        roster.setUpdatedAt(now);
        employeeRosterRepository.save(roster);

        // 6. Phát sự kiện bất đồng bộ sang RabbitMQ
        try {
            userEventPublisher.publishUserRegistered(UserRegisteredEvent.create(
                    user.getId(), user.getUsername(), user.getEmail(), user.getRole()));

            if (roster.getDepartment() != null) {
                userEventPublisher.publishUserAssignedToDepartment(UserAssignedToDepartmentEvent.create(
                        user.getId(),
                        user.getUsername(),
                        roster.getDepartment().getId(),
                        roster.getDepartment().getName(),
                        user.getId()));
            }
        } catch (Exception e) {
            log.error("Failed to publish RabbitMQ event after JIT Claim for user: {}", user.getId(), e);
            // Non-blocking event emission failure in local dev
        }

        log.info("Successfully completed JIT Claim for email={}, assigned userId={}", normalizedEmail, user.getId());

        return toClaimResponse(user, profile, roster);
    }

    private ClaimRosterResponse toClaimResponse(User user, UserProfile profile, EmployeeRoster roster) {
        return new ClaimRosterResponse(
                user.getId(),
                user.getUsername(),
                user.getEmail(),
                profile.getFullName(),
                user.getRole(),
                roster.getDepartment() != null ? roster.getDepartment().getId() : null,
                roster.getDepartment() != null ? roster.getDepartment().getName() : null,
                roster.getDepartment() != null ? roster.getDepartment().getCode() : null
        );
    }
}
