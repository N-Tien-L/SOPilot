package com.poliwise.auth.service;

import com.poliwise.auth.dto.auth.OtpResponse;
import com.poliwise.auth.dto.auth.ResetPasswordWithOtpRequest;
import com.poliwise.auth.dto.auth.SendOtpResponse;
import com.poliwise.auth.dto.auth.VerifyOtpResponse;
import com.poliwise.auth.entity.PasswordResetOtp;
import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.repository.PasswordResetOtpRepository;
import com.poliwise.auth.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

@Service
public class OtpService {

    private static final Logger log = LoggerFactory.getLogger(OtpService.class);
    private static final int OTP_LENGTH = 6;
    private static final int OTP_EXPIRY_MINUTES = 5;
    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private final PasswordResetOtpRepository otpRepository;
    private final UserRepository userRepository;
    private final EmailService emailService;
    private final PasswordService passwordService;

    public OtpService(
            PasswordResetOtpRepository otpRepository,
            UserRepository userRepository,
            EmailService emailService,
            PasswordService passwordService
    ) {
        this.otpRepository = otpRepository;
        this.userRepository = userRepository;
        this.emailService = emailService;
        this.passwordService = passwordService;
    }

    @Transactional
    public SendOtpResponse sendOtp(String email) {
        String normalizedEmail = email.trim().toLowerCase();

        Optional<User> userOpt = userRepository.findByEmailIgnoreCase(normalizedEmail);

        if (userOpt.isEmpty()) {
            log.info("OTP request for non-existent email: {}", maskEmail(normalizedEmail));
            // Return success anyway to prevent email enumeration
            return SendOtpResponse.success(OTP_EXPIRY_MINUTES);
        }

        User user = userOpt.get();

        if (user.getStatus() != AccountStatus.ACTIVE) {
            log.info("OTP request for non-active user: {}", user.getUsername());
            return SendOtpResponse.success(OTP_EXPIRY_MINUTES);
        }

        // Invalidate all previous OTPs for this email
        otpRepository.markAllUnusedForEmail(normalizedEmail, OffsetDateTime.now(ZoneOffset.UTC));

        // Generate new OTP
        String otpCode = generateOtp();
        String resetToken = UUID.randomUUID().toString();
        OffsetDateTime expiresAt = OffsetDateTime.now(ZoneOffset.UTC).plusMinutes(OTP_EXPIRY_MINUTES);

        PasswordResetOtp otp = PasswordResetOtp.builder()
                .email(normalizedEmail)
                .otpCode(otpCode)
                .resetToken(resetToken)
                .expiresAt(expiresAt)
                .used(false)
                .createdAt(OffsetDateTime.now(ZoneOffset.UTC))
                .build();

        otpRepository.save(otp);

        log.info("OTP sent to user: {}", user.getUsername());

        // Send email asynchronously
        emailService.sendOtpEmail(user.getEmail(), user.getUsername(), otpCode);

        return SendOtpResponse.success(OTP_EXPIRY_MINUTES);
    }

    @Transactional(readOnly = true)
    public VerifyOtpResponse verifyOtp(String email, String otpCode) {
        String normalizedEmail = email.trim().toLowerCase();

        Optional<PasswordResetOtp> otpOpt = otpRepository.findByEmailAndOtpCodeAndUsedFalse(normalizedEmail, otpCode);

        if (otpOpt.isEmpty()) {
            log.info("Invalid OTP attempt for email: {}", maskEmail(normalizedEmail));
            return VerifyOtpResponse.invalid();
        }

        PasswordResetOtp otp = otpOpt.get();

        if (otp.isExpired()) {
            log.info("Expired OTP attempt for email: {}", maskEmail(normalizedEmail));
            return VerifyOtpResponse.expired();
        }

        log.info("OTP verified successfully for email: {}", maskEmail(normalizedEmail));
        return VerifyOtpResponse.valid(otp.getResetToken());
    }

    @Transactional
    public OtpResponse resetPassword(ResetPasswordWithOtpRequest request) {
        String normalizedEmail = request.getEmail().trim().toLowerCase();

        // Find valid OTP
        Optional<PasswordResetOtp> otpOpt = otpRepository.findByEmailAndOtpCodeAndUsedFalse(
                normalizedEmail, request.getOtp());

        if (otpOpt.isEmpty()) {
            return OtpResponse.error("Mã OTP không hợp lệ");
        }

        PasswordResetOtp otp = otpOpt.get();

        if (otp.isExpired()) {
            return OtpResponse.error("Mã OTP đã hết hạn");
        }

        // Find user
        Optional<User> userOpt = userRepository.findByEmailIgnoreCase(normalizedEmail);
        if (userOpt.isEmpty()) {
            return OtpResponse.error("Không tìm thấy người dùng");
        }

        User user = userOpt.get();

        // Update password
        String hashedPassword = passwordService.hashPassword(request.getNewPassword());
        user.setPasswordHash(hashedPassword);
        user.setPasswordChangedAt(OffsetDateTime.now(ZoneOffset.UTC));
        user.setMustChangePassword(false);
        user.setUpdatedAt(OffsetDateTime.now(ZoneOffset.UTC));
        user.setFailedLoginAttempts(0);
        user.setLockedUntil(null);

        userRepository.save(user);

        // Mark OTP as used
        otp.setUsed(true);
        otp.setUsedAt(OffsetDateTime.now(ZoneOffset.UTC));
        otpRepository.save(otp);

        // Invalidate all other OTPs for this email
        otpRepository.markAllUnusedForEmail(normalizedEmail, OffsetDateTime.now(ZoneOffset.UTC));

        log.info("Password reset successfully for user: {}", user.getUsername());

        return OtpResponse.success("Đặt lại mật khẩu thành công");
    }

    private String generateOtp() {
        StringBuilder otp = new StringBuilder();
        for (int i = 0; i < OTP_LENGTH; i++) {
            otp.append(SECURE_RANDOM.nextInt(10));
        }
        return otp.toString();
    }

    private String maskEmail(String email) {
        if (email == null || email.length() < 4) return "***";
        int atIndex = email.indexOf('@');
        if (atIndex <= 1) return "***" + email.substring(atIndex);
        return email.substring(0, 2) + "***" + email.substring(atIndex);
    }
}
