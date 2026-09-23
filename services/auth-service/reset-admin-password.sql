-- ===========================================
-- Reset Admin Password Script
-- Run this if admin account exists but password is unknown
-- ===========================================

-- Default password: Admin@123456
-- BCrypt hash for 'Admin@123456' (cost factor 12)
UPDATE core.users
SET 
    password_hash = '$2b$12$2vAYpN1.GYZ1Ze8xXe1TB.xWw/cB8z5uTyqc/7rqMRkmtG4Mw39Ka',
    failed_login_attempts = 0,
    status = 'ACTIVE',
    locked_until = NULL,
    updated_at = NOW()
WHERE username = 'admin';

-- Verify the update
SELECT username, email, role, status, created_at, updated_at 
FROM core.users
WHERE username = 'admin';

-- If you need to set a custom password, generate a BCrypt hash for it first
-- Example: password = 'MyNewPassword123' -> generate hash using BCrypt tool
