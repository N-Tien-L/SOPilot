-- ============================================================
-- FILE: 007_seed_data.sql
-- SCHEMA: ALL
-- Contains: Default seed data for initial deployment
-- ============================================================
-- Seed data for categories, tags, and default admin user.
-- Safe to re-run (uses ON CONFLICT DO NOTHING).
-- Note: UUIDs generated with uuid_generate_v4() for security
-- ============================================================

-- ============================================================
-- SEED: Categories
-- ============================================================
INSERT INTO metadata.categories (id, name, slug, description, display_order, is_active) VALUES
    (uuid_generate_v4(), 'Chính sách nhân sự', 'chinh-sach-nhan-su', 'Các chính sách liên quan đến nhân sự và tuyển dụng', 1, TRUE),
    (uuid_generate_v4(), 'Quy chế tài chính', 'quy-che-tai-chinh', 'Quy chế về tài chính và ngân sách', 2, TRUE),
    (uuid_generate_v4(), 'Quy định văn hóa', 'quy-dinh-van-hoa', 'Quy định về văn hóa doanh nghiệp', 3, TRUE),
    (uuid_generate_v4(), 'An toàn lao động', 'an-toan-lao-dong', 'Quy định về an toàn và vệ sinh lao động', 4, TRUE),
    (uuid_generate_v4(), 'Quy trình nghiệp vụ', 'quy-trinh-nghiep-vu', 'Các quy trình nghiệp vụ nội bộ', 5, TRUE)
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- SEED: Tags
-- ============================================================
INSERT INTO metadata.tags (id, name, slug, color) VALUES
    (uuid_generate_v4(), 'Quan trọng', 'quan-trong', '#ef4444'),
    (uuid_generate_v4(), 'Mới', 'moi', '#22c55e'),
    (uuid_generate_v4(), 'Cập nhật', 'cap-nhat', '#3b82f6'),
    (uuid_generate_v4(), 'Cần xem xét', 'can-xem-xet', '#f59e0b'),
    (uuid_generate_v4(), 'Nội bộ', 'noin-bo', '#8b5cf6')
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- SEED: Default Admin User
-- ============================================================
-- NOTE: Admin user is created by AdminInitializer.java at service startup
-- This script creates the admin profile after the user exists
INSERT INTO core.user_profiles (id, user_id, full_name)
VALUES (
    uuid_generate_v4(),
    (SELECT id FROM core.users WHERE username = 'admin' LIMIT 1),
    'System Administrator'
)
ON CONFLICT (user_id) DO NOTHING;

-- ============================================================
-- SEED: Default Department
-- ============================================================
INSERT INTO core.departments (id, name, code, description, is_active)
VALUES (
    uuid_generate_v4(),
    'Quản trị hệ thống',
    'ADMIN',
    'Phòng ban quản trị hệ thống',
    TRUE
)
ON CONFLICT (code) DO NOTHING;
