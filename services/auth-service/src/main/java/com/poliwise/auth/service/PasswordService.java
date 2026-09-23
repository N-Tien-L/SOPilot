package com.poliwise.auth.service;

import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;

@Service
public class PasswordService {

    private static final String LOWERCASE = "abcdefghijklmnopqrstuvwxyz";
    private static final String UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    private static final String DIGITS = "0123456789";
    private static final String SPECIAL = "!@#$%^&*";
    private static final String ALL_CHARS = LOWERCASE + UPPERCASE + DIGITS + SPECIAL;

    private static final SecureRandom SECURE_RANDOM = new SecureRandom();

    private final PasswordEncoder passwordEncoder;

    public PasswordService(PasswordEncoder passwordEncoder) {
        this.passwordEncoder = passwordEncoder;
    }

    public String generateSecurePassword() {
        return generateSecurePassword(12);
    }

    public String generateSecurePassword(int length) {
        StringBuilder password = new StringBuilder(length);

        password.append(LOWERCASE.charAt(SECURE_RANDOM.nextInt(LOWERCASE.length())));
        password.append(UPPERCASE.charAt(SECURE_RANDOM.nextInt(UPPERCASE.length())));
        password.append(DIGITS.charAt(SECURE_RANDOM.nextInt(DIGITS.length())));
        password.append(SPECIAL.charAt(SECURE_RANDOM.nextInt(SPECIAL.length())));

        for (int i = 4; i < length; i++) {
            password.append(ALL_CHARS.charAt(SECURE_RANDOM.nextInt(ALL_CHARS.length())));
        }

        String pw = password.toString();
        return shuffle(pw);
    }

    public String hashPassword(String rawPassword) {
        return passwordEncoder.encode(rawPassword);
    }

    public boolean verifyPassword(String rawPassword, String hashedPassword) {
        return passwordEncoder.matches(rawPassword, hashedPassword);
    }

    public PasswordStrengthResult checkStrength(String password) {
        if (password == null || password.isEmpty()) {
            return new PasswordStrengthResult(0, "Rất yếu", false, false, false, false);
        }

        boolean hasLower = password.chars().anyMatch(Character::isLowerCase);
        boolean hasUpper = password.chars().anyMatch(Character::isUpperCase);
        boolean hasDigit = password.chars().anyMatch(Character::isDigit);
        boolean hasSpecial = password.chars().anyMatch(c -> SPECIAL.indexOf(c) >= 0);
        boolean hasMinLength = password.length() >= 8;

        int score = 0;
        if (hasLower) score += 20;
        if (hasUpper) score += 20;
        if (hasDigit) score += 20;
        if (hasSpecial) score += 20;
        if (password.length() >= 12) score += 10;
        if (password.length() >= 16) score += 10;

        String label = switch (score) {
            case 0 -> "Rất yếu";
            case 1, 20 -> "Yếu";
            case 40, 50 -> "Trung bình";
            case 60, 70 -> "Khá";
            case 80, 90 -> "Mạnh";
            default -> "Rất mạnh";
        };

        return new PasswordStrengthResult(score, label, hasLower, hasUpper, hasDigit, hasSpecial);
    }

    public record PasswordStrengthResult(
            int score,
            String label,
            boolean hasLower,
            boolean hasUpper,
            boolean hasDigit,
            boolean hasSpecial
    ) {
        public boolean isMinLength() { return score >= 60; }
        public boolean isStrong() { return score >= 80; }
    }

    private String shuffle(String input) {
        char[] chars = input.toCharArray();
        for (int i = chars.length - 1; i > 0; i--) {
            int j = SECURE_RANDOM.nextInt(i + 1);
            char temp = chars[i];
            chars[i] = chars[j];
            chars[j] = temp;
        }
        return new String(chars);
    }
}
