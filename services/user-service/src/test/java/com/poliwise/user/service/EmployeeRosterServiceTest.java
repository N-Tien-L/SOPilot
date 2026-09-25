package com.poliwise.user.service;

import com.poliwise.user.dto.roster.ClaimRosterRequest;
import com.poliwise.user.dto.roster.ClaimRosterResponse;
import com.poliwise.user.dto.roster.RosterResponse;
import com.poliwise.user.entity.Department;
import com.poliwise.user.entity.EmployeeRoster;
import com.poliwise.user.entity.User;
import com.poliwise.user.entity.UserProfile;
import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.RosterStatus;
import com.poliwise.user.enums.UserRole;
import com.poliwise.user.event.UserEventPublisher;
import com.poliwise.user.exception.RosterAlreadyClaimedException;
import com.poliwise.user.exception.RosterDeactivatedException;
import com.poliwise.user.exception.RosterNotFoundException;
import com.poliwise.user.repository.EmployeeRosterRepository;
import com.poliwise.user.repository.UserProfileRepository;
import com.poliwise.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class EmployeeRosterServiceTest {

    @Mock
    private EmployeeRosterRepository employeeRosterRepository;

    @Mock
    private UserRepository userRepository;

    @Mock
    private UserProfileRepository userProfileRepository;

    @Mock
    private UserEventPublisher userEventPublisher;

    @InjectMocks
    private EmployeeRosterService employeeRosterService;

    private EmployeeRoster sampleRoster;
    private Department department;
    private UUID rosterId;
    private UUID deptId;

    @BeforeEach
    void setUp() {
        rosterId = UUID.randomUUID();
        deptId = UUID.randomUUID();

        department = new Department();
        department.setId(deptId);
        department.setCode("ENG");
        department.setName("Kỹ thuật");
        department.setIsActive(true);

        sampleRoster = new EmployeeRoster();
        sampleRoster.setId(rosterId);
        sampleRoster.setEmployeeCode("EMP001");
        sampleRoster.setFullName("Nguyễn Văn A");
        sampleRoster.setEmail("employee@company.com");
        sampleRoster.setDepartment(department);
        sampleRoster.setPosition("Software Engineer");
        sampleRoster.setPhone("0901234567");
        sampleRoster.setStatus(RosterStatus.PENDING);
        sampleRoster.setClaimed(false);
    }

    @Test
    @DisplayName("claimRoster: Thành công khi email hợp lệ và ở trạng thái PENDING")
    void claimRoster_whenValid_shouldCreateUserAndMarkClaimed() {
        ClaimRosterRequest request = new ClaimRosterRequest(
                "employee@company.com",
                "google-oauth2|123456"
        );

        when(employeeRosterRepository.findByEmailIgnoreCaseForUpdate("employee@company.com"))
                .thenReturn(Optional.of(sampleRoster));

        User mockUser = new User();
        mockUser.setId(UUID.randomUUID());
        mockUser.setEmail(sampleRoster.getEmail());
        mockUser.setUsername(sampleRoster.getEmail());
        mockUser.setRole(UserRole.USER);
        mockUser.setStatus(AccountStatus.ACTIVE);

        when(userRepository.save(any(User.class))).thenReturn(mockUser);
        when(userProfileRepository.save(any(UserProfile.class))).thenReturn(new UserProfile());
        when(employeeRosterRepository.save(any(EmployeeRoster.class))).thenReturn(sampleRoster);

        ClaimRosterResponse response = employeeRosterService.claimRoster(request);

        assertThat(response).isNotNull();
        assertThat(response.email()).isEqualTo("employee@company.com");
        assertThat(response.departmentId()).isEqualTo(deptId);
        assertThat(response.departmentCode()).isEqualTo("ENG");

        // Verify status and claimed updated
        assertThat(sampleRoster.getStatus()).isEqualTo(RosterStatus.CLAIMED);
        assertThat(sampleRoster.isClaimed()).isTrue();
        assertThat(sampleRoster.getClaimedUser()).isEqualTo(mockUser);

        // Verify RabbitMQ events triggered
        verify(userEventPublisher, times(1)).publishUserRegistered(any());
        verify(userEventPublisher, times(1)).publishUserAssignedToDepartment(any());
    }

    @Test
    @DisplayName("claimRoster: Ném RosterNotFoundException khi email không tồn tại trong danh bạ")
    void claimRoster_whenNotFound_shouldThrowRosterNotFoundException() {
        ClaimRosterRequest request = new ClaimRosterRequest(
                "unknown@company.com",
                "google-oauth2|999999"
        );

        when(employeeRosterRepository.findByEmailIgnoreCaseForUpdate("unknown@company.com"))
                .thenReturn(Optional.empty());

        assertThatThrownBy(() -> employeeRosterService.claimRoster(request))
                .isInstanceOf(RosterNotFoundException.class)
                .hasMessageContaining("chưa nằm trong danh bạ nhân sự");

        verify(userRepository, never()).save(any());
    }

    @Test
    @DisplayName("claimRoster: Ném RosterDeactivatedException khi danh bạ đã bị DEACTIVATED")
    void claimRoster_whenDeactivated_shouldThrowRosterDeactivatedException() {
        sampleRoster.setStatus(RosterStatus.DEACTIVATED);

        ClaimRosterRequest request = new ClaimRosterRequest(
                "employee@company.com",
                "google-oauth2|123456"
        );

        when(employeeRosterRepository.findByEmailIgnoreCaseForUpdate("employee@company.com"))
                .thenReturn(Optional.of(sampleRoster));

        assertThatThrownBy(() -> employeeRosterService.claimRoster(request))
                .isInstanceOf(RosterDeactivatedException.class)
                .hasMessageContaining("vô hiệu hóa");

        verify(userRepository, never()).save(any());
    }

    @Test
    @DisplayName("claimRoster: Ném RosterAlreadyClaimedException khi tài khoản đã được claim trước đó")
    void claimRoster_whenAlreadyClaimed_shouldThrowRosterAlreadyClaimedException() {
        sampleRoster.setStatus(RosterStatus.CLAIMED);
        sampleRoster.setClaimed(true);

        ClaimRosterRequest request = new ClaimRosterRequest(
                "employee@company.com",
                "google-oauth2|123456"
        );

        when(employeeRosterRepository.findByEmailIgnoreCaseForUpdate("employee@company.com"))
                .thenReturn(Optional.of(sampleRoster));

        assertThatThrownBy(() -> employeeRosterService.claimRoster(request))
                .isInstanceOf(RosterAlreadyClaimedException.class)
                .hasMessageContaining("đã được kích hoạt");

        verify(userRepository, never()).save(any());
    }

    @Test
    @DisplayName("searchRoster: Tìm kiếm và trả về phân trang thành công")
    void searchRoster_shouldReturnPagedResults() {
        Pageable pageable = PageRequest.of(0, 10);
        Page<EmployeeRoster> pagedRosters = new PageImpl<>(List.of(sampleRoster), pageable, 1);

        when(employeeRosterRepository.findAll(any(Specification.class), eq(pageable)))
                .thenReturn(pagedRosters);

        Page<RosterResponse> result = employeeRosterService.searchRoster("EMP001", null, null, null, pageable);

        assertThat(result.getTotalElements()).isEqualTo(1);
        assertThat(result.getContent().get(0).employeeCode()).isEqualTo("EMP001");
    }

    @Test
    @DisplayName("deactivateRoster: Vô hiệu hóa thành công danh bạ chưa claim")
    void deactivateRoster_whenUnclaimed_shouldSetStatusDeactivated() {
        UUID adminId = UUID.randomUUID();
        when(employeeRosterRepository.findById(rosterId)).thenReturn(Optional.of(sampleRoster));

        employeeRosterService.deactivateRoster(rosterId, adminId);

        assertThat(sampleRoster.getStatus()).isEqualTo(RosterStatus.DEACTIVATED);
        assertThat(sampleRoster.getUpdatedBy()).isEqualTo(adminId);
        verify(employeeRosterRepository, times(1)).save(sampleRoster);
    }

    @Test
    @DisplayName("deactivateRoster: Ném ngoại lệ khi cố vô hiệu hóa danh bạ đã claim")
    void deactivateRoster_whenAlreadyClaimed_shouldThrowIllegalStateException() {
        UUID adminId = UUID.randomUUID();
        sampleRoster.setClaimed(true);
        sampleRoster.setStatus(RosterStatus.CLAIMED);

        when(employeeRosterRepository.findById(rosterId)).thenReturn(Optional.of(sampleRoster));

        assertThatThrownBy(() -> employeeRosterService.deactivateRoster(rosterId, adminId))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("đã kích hoạt tài khoản");

        verify(employeeRosterRepository, never()).save(any());
    }
}
