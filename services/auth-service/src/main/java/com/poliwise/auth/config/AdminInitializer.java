package com.poliwise.auth.config;

import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import com.poliwise.auth.enums.UserRole;
import com.poliwise.auth.repository.UserRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.UUID;

/**
 * Initializes default admin account on application startup.
 * Creates the admin user only if it does not already exist.
 * Generates a random password on first deployment.
 */
@Component
@ConditionalOnProperty(prefix = "poliwise.bootstrap.admin", name = "enabled", havingValue = "true")
@Slf4j
public class AdminInitializer implements CommandLineRunner {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final String adminUsername;
    private final String adminEmail;
    private final String adminPassword;

    private static final UserRole ADMIN_ROLE = UserRole.ADMIN;

    public AdminInitializer(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            @Value("${ADMIN_USERNAME}") String adminUsername,
            @Value("${ADMIN_EMAIL}") String adminEmail,
            @Value("${ADMIN_PASSWORD}") String adminPassword) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.adminUsername = requireConfigured("ADMIN_USERNAME", adminUsername);
        this.adminEmail = requireConfigured("ADMIN_EMAIL", adminEmail);
        this.adminPassword = requireConfigured("ADMIN_PASSWORD", adminPassword);
    }

    private static String requireConfigured(String name, String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalStateException(name + " is required when admin bootstrap is enabled");
        }
        return value;
    }

    @Override
    @Transactional
    public void run(String... args) {
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);

        if (userRepository.existsByUsernameIgnoreCase(adminUsername)) {
            log.info("Admin account '{}' already exists, verifying credentials...", adminUsername);

            // Optional: Reset password to ensure it matches current ADMIN_PASSWORD env var
            // This handles the case where the password was set with a different value
            var existingAdmin = userRepository.findByUsernameIgnoreCase(adminUsername);
            if (existingAdmin.isPresent()) {
                User admin = existingAdmin.get();

                // Check if password needs resetting (compare encoded password)
                // If password doesn't match, update it
                if (!passwordEncoder.matches(adminPassword, admin.getPasswordHash())) {
                    log.warn("Admin password mismatch detected! Resetting to current ADMIN_PASSWORD...");
                    admin.setPasswordHash(passwordEncoder.encode(adminPassword));
                    admin.setUpdatedAt(now);
                    userRepository.save(admin);
                    log.info("Admin account '{}' password has been reset successfully.", adminUsername);
                } else {
                    log.info("Admin account '{}' credentials verified.", adminUsername);
                }
            }
            return;
        }

        User admin = User.builder()
                .id(UUID.randomUUID())
                .username(adminUsername.toLowerCase())
                .email(adminEmail.toLowerCase())
                .passwordHash(passwordEncoder.encode(adminPassword))
                .role(ADMIN_ROLE)
                .status(AccountStatus.ACTIVE)
                .failedLoginAttempts(0)
                .mustChangePassword(true)
                .passwordChangedAt(now)
                .createdAt(now)
                .updatedAt(now)
                .build();

        userRepository.save(admin);
        log.info("Admin account '{}' created successfully. PASSWORD MUST BE CHANGED ON FIRST LOGIN.",
                adminUsername);
    }
}
