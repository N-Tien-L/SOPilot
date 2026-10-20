-- ============================================================
-- VERIFICATION TEST SUITE CHO TICKET M1-01 (010_employee_roster.sql)
-- ============================================================

\set ON_ERROR_STOP on

BEGIN;

-- Lấy Department mẫu từ seed
DO $$
DECLARE
    v_dept_id UUID;
    v_roster_id UUID;
    v_created_at TIMESTAMPTZ;
    v_updated_at TIMESTAMPTZ;
BEGIN
    SELECT id INTO v_dept_id FROM core.departments WHERE code = 'ADMIN' LIMIT 1;
    IF v_dept_id IS NULL THEN
        RAISE EXCEPTION 'Department ADMIN must exist in core.departments';
    END IF;

    -- T1: Happy path insert
    INSERT INTO core.employee_roster (employee_code, email, full_name, department_id, position)
    VALUES ('EMP001', 'alex.nguyen@sopilot.com', 'Alex Nguyen', v_dept_id, 'Software Engineer')
    RETURNING id, created_at, updated_at INTO v_roster_id, v_created_at, v_updated_at;

    RAISE NOTICE '>>> TEST 1 PASS: Insert hợp lệ thành công (ID: %)', v_roster_id;

    -- T2: Trigger updated_at
    PERFORM pg_sleep(0.02);
    UPDATE core.employee_roster 
    SET position = 'Senior Software Engineer' 
    WHERE id = v_roster_id;

    SELECT updated_at INTO v_updated_at FROM core.employee_roster WHERE id = v_roster_id;
    IF v_updated_at <= v_created_at THEN
        RAISE EXCEPTION 'Trigger trg_employee_roster_updated_at không hoạt động chính xác';
    END IF;
    RAISE NOTICE '>>> TEST 2 PASS: Trigger updated_at hoạt động chính xác (%)', v_updated_at;
END $$;

-- T3: Chặn trùng email hoa/thường (LOWER(email))
DO $$
DECLARE
    v_dept_id UUID;
BEGIN
    SELECT id INTO v_dept_id FROM core.departments WHERE code = 'ADMIN' LIMIT 1;
    BEGIN
        INSERT INTO core.employee_roster (employee_code, email, full_name, department_id)
        VALUES ('EMP002', 'ALEX.NGUYEN@sopilot.com', 'Duplicate Alex', v_dept_id);
        RAISE EXCEPTION 'TEST 3 FAILED: Không chặn được email trùng hoa thường';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE '>>> TEST 3 PASS: Unique index chặn trùng email hoa/thường thành công';
    END;
END $$;

-- T4: Chặn trùng mã nhân viên (employee_code)
DO $$
DECLARE
    v_dept_id UUID;
BEGIN
    SELECT id INTO v_dept_id FROM core.departments WHERE code = 'ADMIN' LIMIT 1;
    BEGIN
        INSERT INTO core.employee_roster (employee_code, email, full_name, department_id)
        VALUES ('EMP001', 'other.email@sopilot.com', 'Other Person', v_dept_id);
        RAISE EXCEPTION 'TEST 4 FAILED: Không chặn được trùng employee_code';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE '>>> TEST 4 PASS: Unique index chặn trùng employee_code thành công';
    END;
END $$;

-- T5: Ràng buộc định dạng email (chk_roster_email_format)
DO $$
DECLARE
    v_dept_id UUID;
BEGIN
    SELECT id INTO v_dept_id FROM core.departments WHERE code = 'ADMIN' LIMIT 1;
    BEGIN
        INSERT INTO core.employee_roster (employee_code, email, full_name, department_id)
        VALUES ('EMP003', 'invalid-email-format', 'Invalid Email User', v_dept_id);
        RAISE EXCEPTION 'TEST 5 FAILED: Không chặn được email sai định dạng';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE '>>> TEST 5 PASS: Constraint chk_roster_email_format chặn email lỗi thành công';
    END;
END $$;

-- T6: Ràng buộc tính nhất quán is_claimed (chk_roster_claimed_consistency)
-- TH1: is_claimed = true nhưng claimed_at / user_id là NULL
DO $$
DECLARE
    v_dept_id UUID;
BEGIN
    SELECT id INTO v_dept_id FROM core.departments WHERE code = 'ADMIN' LIMIT 1;
    BEGIN
        INSERT INTO core.employee_roster (employee_code, email, full_name, department_id, is_claimed)
        VALUES ('EMP004', 'claimed.fail@sopilot.com', 'Claimed Fail', v_dept_id, TRUE);
        RAISE EXCEPTION 'TEST 6 FAILED: Không chặn được is_claimed = true thiếu claimed_at/claimed_user_id';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE '>>> TEST 6 PASS: Constraint chk_roster_claimed_consistency chặn state không nhất quán thành công';
    END;
END $$;

-- T7: Khóa ngoại ON DELETE RESTRICT bảo vệ Department
DO $$
DECLARE
    v_dept_id UUID;
BEGIN
    SELECT id INTO v_dept_id FROM core.departments WHERE code = 'ADMIN' LIMIT 1;
    BEGIN
        DELETE FROM core.departments WHERE id = v_dept_id;
        RAISE EXCEPTION 'TEST 7 FAILED: Cho phép xóa Department đang có nhân viên trong roster';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE '>>> TEST 7 PASS: ON DELETE RESTRICT ngăn xóa phòng ban thành công';
    END;
END $$;

-- Dọn dẹp dữ liệu test bằng ROLLBACK an toàn
ROLLBACK;
