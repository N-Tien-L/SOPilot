-- ============================================================
-- FILE: 010_employee_roster.sql
-- SCHEMA: core
-- PURPOSE: Pre-provisioned Employee Directory for JIT Onboarding
-- AUTHOR: SOPilot Architecture Team
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. ENUM STATUS CHO ROSTER (Nếu chưa tồn tại)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'roster_status' AND typnamespace = 'core'::regnamespace) THEN
        CREATE TYPE core.roster_status AS ENUM ('PENDING', 'CLAIMED', 'DEACTIVATED');
    END IF;
END$$;

-- Đồng bộ kiểu dữ liệu core.user_profiles (nếu đã tồn tại) để đảm bảo toàn vẹn khi claim JIT
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'core' AND table_name = 'user_profiles' AND column_name = 'employee_code'
    ) THEN
        ALTER TABLE core.user_profiles ALTER COLUMN employee_code TYPE VARCHAR(50);
        ALTER TABLE core.user_profiles ALTER COLUMN full_name TYPE VARCHAR(255);
    END IF;
END$$;

-- 2. TABLE: core.employee_roster
CREATE TABLE IF NOT EXISTS core.employee_roster (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Định danh nhân sự
    employee_code VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    position VARCHAR(100),
    
    -- Phân bổ tổ chức & phân quyền
    department_id UUID NOT NULL REFERENCES core.departments(id) ON DELETE RESTRICT,
    role core.user_role NOT NULL DEFAULT 'USER',
    
    -- Vòng đời JIT Provisioning
    status core.roster_status NOT NULL DEFAULT 'PENDING',
    is_claimed BOOLEAN NOT NULL DEFAULT FALSE,
    claimed_at TIMESTAMPTZ,
    claimed_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    
    -- Truy vết Audit & Batch Import
    import_batch_id UUID NOT NULL DEFAULT uuid_generate_v4(),
    created_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,

    -- Ràng buộc dữ liệu (Constraints)
    CONSTRAINT chk_roster_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_roster_claimed_consistency CHECK (
        (is_claimed = FALSE AND claimed_at IS NULL AND claimed_user_id IS NULL) OR
        (is_claimed = TRUE AND claimed_at IS NOT NULL AND claimed_user_id IS NOT NULL)
    )
);

-- 3. CHỈ MỤC TỐI ƯU HÓA TRUY VẤN (INDEXES)
-- Đảm bảo email và mã NV duy nhất không phân biệt hoa thường với các bản ghi đang hoạt động
CREATE UNIQUE INDEX IF NOT EXISTS idx_roster_email_lower_unique 
    ON core.employee_roster (LOWER(email)) 
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_roster_employee_code_unique 
    ON core.employee_roster (employee_code) 
    WHERE deleted_at IS NULL;

-- Tối ưu cho màn hình tra cứu danh bạ chờ kích hoạt của HR
CREATE INDEX IF NOT EXISTS idx_roster_dept_status 
    ON core.employee_roster (department_id, status) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_roster_status 
    ON core.employee_roster (status) 
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_roster_batch_id 
    ON core.employee_roster (import_batch_id);

CREATE INDEX IF NOT EXISTS idx_roster_claimed_user 
    ON core.employee_roster (claimed_user_id) 
    WHERE claimed_user_id IS NOT NULL;

-- 4. TRIGGER TỰ ĐỘNG CẬP NHẬT updated_at
CREATE OR REPLACE FUNCTION core.trg_update_employee_roster_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_employee_roster_updated_at ON core.employee_roster;
CREATE TRIGGER trg_employee_roster_updated_at
    BEFORE UPDATE ON core.employee_roster
    FOR EACH ROW
    EXECUTE FUNCTION core.trg_update_employee_roster_timestamp();

COMMENT ON TABLE core.employee_roster IS 'Danh bạ định danh nhân sự nạp trước phục vụ Google 1-Click JIT Onboarding';
COMMENT ON COLUMN core.employee_roster.employee_code IS 'Mã số nhân viên doanh nghiệp cấp (duy nhất)';
COMMENT ON COLUMN core.employee_roster.status IS 'Trạng thái: PENDING (chờ kích hoạt), CLAIMED (đã đăng nhập), DEACTIVATED (đã hủy)';
