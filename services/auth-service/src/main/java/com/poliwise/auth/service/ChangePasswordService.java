package com.poliwise.auth.service;

import com.poliwise.auth.dto.auth.ChangePasswordResponse;
import com.poliwise.auth.dto.auth.MessageResponse;
import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.UUID;

@Service
public class ChangePasswordService {

    private static final Logger log = LoggerFactory.getLogger(ChangePasswordService.class);

    private final UserRepository userRepository;
    private final PasswordService passwordService;

    public ChangePasswordService(UserRepository userRepository, PasswordService passwordService) {
        this.userRepository = userRepository;
        this.passwordService = passwordService;
    }

    @Transactional
    public MessageResponse changePassword(UUID userId, String oldPassword, String newPassword, String confirmPassword) {
        User user = userRepository.findByIdForUpdate(userId)
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        if (user.getStatus() != AccountStatus.ACTIVE) {
            throw new IllegalArgumentException("Cannot change password for inactive user");
        }

        if (!passwordService.verifyPassword(oldPassword, user.getPasswordHash())) {
            log.warn("Invalid old password attempt for user: {}", user.getUsername());
            return MessageResponse.error("Mật khẩu cũ không đúng");
        }

        if (!newPassword.equals(confirmPassword)) {
            return MessageResponse.error("Mật khẩu mới và xác nhận mật khẩu không khớp");
        }

        PasswordService.PasswordStrengthResult strength = passwordService.checkStrength(newPassword);
        if (!strength.isMinLength()) {
            return MessageResponse.error("Mật khẩu mới phải có ít nhất 8 ký tự, bao gồm chữ hoa, chữ thường, số và ký tự đặc biệt");
        }

        if (passwordService.verifyPassword(newPassword, user.getPasswordHash())) {
            return MessageResponse.error("Mật khẩu mới không được trùng với mật khẩu cũ");
        }

        user.setPasswordHash(passwordService.hashPassword(newPassword));
        user.setPasswordChangedAt(OffsetDateTime.now(ZoneOffset.UTC));
        user.setMustChangePassword(false);
        user.setUpdatedAt(OffsetDateTime.now(ZoneOffset.UTC));
        user.setFailedLoginAttempts(0);
        user.setLockedUntil(null);

        userRepository.save(user);

        log.info("Password changed successfully for user: {}", user.getUsername());

        return MessageResponse.ok("Đổi mật khẩu thành công");
    }
}
