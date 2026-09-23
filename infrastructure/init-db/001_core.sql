-- ============================================================
-- FILE: 001_core.sql
-- SCHEMA: CORE
-- Contains: Users, Auth, Departments
-- ============================================================
-- Single source of truth for core database schema.
-- All columns defined upfront - no ALTER statements needed.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- ENUM TYPES
-- ============================================================
CREATE TYPE core.user_role AS ENUM ('USER', 'MANAGER', 'ADMIN');
CREATE TYPE core.account_status AS ENUM ('ACTIVE', 'DEACTIVATED', 'REVOKED');
CREATE TYPE core.login_status AS ENUM ('SUCCESS', 'FAILED_CREDENTIALS', 'FAILED_DEACTIVATED', 'FAILED_REVOKED', 'FAILED_LOCKED');

-- ============================================================
-- TABLE: core.departments
-- ============================================================
CREATE TABLE core.departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) UNIQUE NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES core.departments(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: core.users
-- ============================================================
CREATE TABLE core.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role core.user_role NOT NULL DEFAULT 'USER',
    status core.account_status NOT NULL DEFAULT 'ACTIVE',
    department_id UUID REFERENCES core.departments(id) ON DELETE SET NULL,

    -- Security fields
    failed_login_attempts INT DEFAULT 0,
    locked_until TIMESTAMPTZ,
    password_changed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    must_change_password BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deactivated_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,

    -- Strike/Violation tracking (3 -> warn, 5 -> deactivate, 10 -> revoke)
    strike_count INT DEFAULT 0,
    last_violation_at TIMESTAMPTZ,

    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_username_format CHECK (username ~* '^[a-z0-9_]{3,50}$'),
    CONSTRAINT chk_status_revoked CHECK (status != 'REVOKED' OR revoked_at IS NOT NULL),
    CONSTRAINT chk_status_deactivated CHECK (status != 'DEACTIVATED' OR deactivated_at IS NOT NULL)
);

-- ============================================================
-- TABLE: core.user_profiles
-- ============================================================
CREATE TABLE core.user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    full_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    position VARCHAR(100),
    avatar_url VARCHAR(500),
    bio TEXT,
    date_of_birth DATE,
    employee_code VARCHAR(20) UNIQUE,
    joined_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

-- ============================================================
-- TABLE: core.refresh_tokens
-- ============================================================
CREATE TABLE core.refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    device_info VARCHAR(500),
    ip_address VARCHAR(45),
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    revoked_reason VARCHAR(100),
    replaced_by UUID REFERENCES core.refresh_tokens(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_active_token_hash UNIQUE (token_hash)
);

-- ============================================================
-- TABLE: core.password_reset_tokens
-- ============================================================
CREATE TABLE core.password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_password_reset_token_lifecycle CHECK (used_at IS NULL OR used_at >= created_at)
);

-- ============================================================
-- TABLE: core.access_token_blacklist
-- ============================================================
CREATE TABLE core.access_token_blacklist (
    jti VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL,
    expired_at TIMESTAMPTZ NOT NULL,
    blacklisted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    reason VARCHAR(100)
);

-- ============================================================
-- TABLE: core.login_history
-- ============================================================
CREATE TABLE core.login_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    username VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    device_type VARCHAR(50),
    location VARCHAR(200),
    status core.login_status NOT NULL,
    failure_reason VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: core.password_reset_otp
-- ============================================================
CREATE TABLE core.password_reset_otp (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL,
    otp_code VARCHAR(6) NOT NULL,
    reset_token VARCHAR(255),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    used_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE core.password_reset_otp IS 'Stores OTP codes for password reset functionality';
COMMENT ON COLUMN core.password_reset_otp.otp_code IS '6-digit OTP code sent to user email';
COMMENT ON COLUMN core.password_reset_otp.reset_token IS 'Unique token to prevent race conditions during reset';
COMMENT ON COLUMN core.password_reset_otp.expires_at IS 'Timestamp when OTP expires (default 5 minutes)';

-- ============================================================
-- INDEXES: Core schema
-- ============================================================
CREATE INDEX idx_core_departments_parent_id ON core.departments(parent_id);
CREATE INDEX idx_core_departments_code ON core.departments(code);

CREATE INDEX idx_core_users_email ON core.users(email);
CREATE INDEX idx_core_users_username ON core.users(username);
CREATE INDEX idx_core_users_status ON core.users(status);
CREATE INDEX idx_core_users_role ON core.users(role);
CREATE INDEX idx_core_users_department_id ON core.users(department_id);
CREATE INDEX idx_core_users_deleted_at ON core.users(deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_core_user_profiles_full_name ON core.user_profiles(full_name);
CREATE INDEX idx_core_user_profiles_employee_code ON core.user_profiles(employee_code);
CREATE INDEX idx_core_user_profiles_user_id ON core.user_profiles(user_id);

CREATE INDEX idx_core_refresh_tokens_user_id ON core.refresh_tokens(user_id);
CREATE INDEX idx_core_refresh_tokens_token_hash ON core.refresh_tokens(token_hash) WHERE revoked = FALSE;

CREATE INDEX idx_core_password_reset_tokens_user_id ON core.password_reset_tokens(user_id);
CREATE INDEX idx_core_password_reset_tokens_active ON core.password_reset_tokens(token_hash, expires_at)
    WHERE used_at IS NULL;

CREATE INDEX idx_core_access_token_blacklist_user_id ON core.access_token_blacklist(user_id);
CREATE INDEX idx_core_access_token_blacklist_expired_at ON core.access_token_blacklist(expired_at);

CREATE INDEX idx_core_login_history_user_id ON core.login_history(user_id);
CREATE INDEX idx_core_login_history_created_at ON core.login_history(created_at DESC);

CREATE INDEX idx_password_reset_otp_email ON core.password_reset_otp(email);
CREATE INDEX idx_password_reset_otp_email_used ON core.password_reset_otp(email, used) WHERE used = FALSE;
CREATE INDEX idx_password_reset_otp_expires ON core.password_reset_otp(expires_at);
