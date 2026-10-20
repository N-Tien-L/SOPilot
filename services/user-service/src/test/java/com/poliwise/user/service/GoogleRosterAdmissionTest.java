package com.poliwise.user.service;

import com.poliwise.user.dto.roster.AdmitGoogleLoginRequest;
import com.poliwise.user.entity.EmployeeRoster;
import com.poliwise.user.entity.User;
import com.poliwise.user.entity.UserProfile;
import com.poliwise.user.enums.RosterStatus;
import com.poliwise.user.enums.UserRole;
import com.poliwise.user.exception.RosterDeactivatedException;
import com.poliwise.user.exception.RosterNotFoundException;
import com.poliwise.user.repository.EmployeeRosterRepository;
import com.poliwise.user.repository.UserProfileRepository;
import com.poliwise.user.repository.UserRepository;
import com.poliwise.user.event.UserEventPublisher;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

@ExtendWith(MockitoExtension.class)
class GoogleRosterAdmissionTest {
    @Mock private EmployeeRosterRepository employeeRosterRepository;
    @Mock private UserRepository userRepository;
    @Mock private UserProfileRepository userProfileRepository;
    @Mock private UserEventPublisher userEventPublisher;
    @InjectMocks private EmployeeRosterService service;

    private EmployeeRoster claimed(UUID userId) {
        User user = new User();
        user.setId(userId);
        user.setEmail("original@company.com");
        user.setRole(UserRole.USER);
        EmployeeRoster roster = new EmployeeRoster();
        roster.setEmail(user.getEmail());
        roster.setStatus(RosterStatus.CLAIMED);
        roster.setClaimed(true);
        roster.setClaimedUser(user);
        return roster;
    }

    @Test
    void admission_ShouldUseClaimedUserId_WhenVerifiedEmailChanges() {
        // Arrange
        UUID userId = UUID.randomUUID();
        when(employeeRosterRepository.findByClaimedUserIdForUpdate(userId)).thenReturn(Optional.of(claimed(userId)));
        UserProfile profile = new UserProfile();
        profile.setFullName("Employee");
        when(userProfileRepository.findByUser_Id(userId)).thenReturn(Optional.of(profile));
        // Act
        var response = service.admitGoogleLogin(new AdmitGoogleLoginRequest("new@company.com", userId));
        // Assert
        assertEquals(userId, response.userId());
        verify(employeeRosterRepository, never()).findByEmailIgnoreCaseForUpdate(anyString());
        verifyNoInteractions(userRepository, userEventPublisher);
    }

    @Test
    void admission_ShouldBeIdempotent_WhenClaimedEmailHasNoIdentityYet() {
        // Arrange: recovering after the user-service transaction committed but auth enrollment failed.
        UUID userId = UUID.randomUUID();
        when(employeeRosterRepository.findByEmailIgnoreCaseForUpdate("original@company.com"))
                .thenReturn(Optional.of(claimed(userId)));
        when(userProfileRepository.findByUser_Id(userId)).thenReturn(Optional.of(new UserProfile()));
        // Act
        var response = service.admitGoogleLogin(new AdmitGoogleLoginRequest("ORIGINAL@company.com", null));
        // Assert
        assertEquals(userId, response.userId());
        verifyNoInteractions(userRepository, userEventPublisher);
    }

    @Test
    void admission_ShouldRejectLinkedUser_WhenRosterWasRemoved() {
        // Arrange
        UUID userId = UUID.randomUUID();
        // Act / Assert
        assertThrows(RosterNotFoundException.class,
                () -> service.admitGoogleLogin(new AdmitGoogleLoginRequest("user@company.com", userId)));
        verifyNoInteractions(userRepository, userProfileRepository, userEventPublisher);
    }

    @Test
    void admission_ShouldRejectLinkedUser_WhenRosterIsDeactivated() {
        // Arrange
        UUID userId = UUID.randomUUID();
        EmployeeRoster roster = claimed(userId);
        roster.setStatus(RosterStatus.DEACTIVATED);
        when(employeeRosterRepository.findByClaimedUserIdForUpdate(userId)).thenReturn(Optional.of(roster));
        // Act / Assert
        assertThrows(RosterDeactivatedException.class,
                () -> service.admitGoogleLogin(new AdmitGoogleLoginRequest("user@company.com", userId)));
        verifyNoInteractions(userRepository, userProfileRepository, userEventPublisher);
    }

    @Test
    void admission_ShouldRejectInconsistentClaim_WithoutCreatingAnotherUser() {
        // Arrange
        EmployeeRoster roster = claimed(UUID.randomUUID());
        roster.setClaimedUser(null);
        when(employeeRosterRepository.findByEmailIgnoreCaseForUpdate("user@company.com")).thenReturn(Optional.of(roster));
        // Act / Assert
        assertThrows(ResponseStatusException.class,
                () -> service.admitGoogleLogin(new AdmitGoogleLoginRequest("user@company.com", null)));
        verifyNoInteractions(userRepository, userProfileRepository, userEventPublisher);
    }
}
