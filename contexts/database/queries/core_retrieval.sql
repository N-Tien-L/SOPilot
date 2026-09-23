-- ============================================================
-- CORE SCHEMA RETRIEVAL SCRIPTS
-- Purpose: Querying users, departments, and profiles
-- ============================================================

-- 1. List all active departments in hierarchy
WITH RECURSIVE dept_tree AS (
    SELECT id, name, code, parent_id, 1 as level
    FROM core.departments
    WHERE parent_id IS NULL AND is_active = TRUE
    UNION ALL
    SELECT d.id, d.name, d.code, d.parent_id, dt.level + 1
    FROM core.departments d
    JOIN dept_tree dt ON d.parent_id = dt.id
    WHERE d.is_active = TRUE
)
SELECT * FROM dept_tree ORDER BY level, name;

-- 2. Find users by department
SELECT 
    u.username, 
    u.email, 
    u.role, 
    d.name as department_name, 
    p.full_name,
    p.position
FROM core.users u
LEFT JOIN core.departments d ON u.department_id = d.id
LEFT JOIN core.user_profiles p ON p.user_id = u.id
WHERE u.deleted_at IS NULL
ORDER BY d.name, u.username;

-- 3. Check login history for specific user
SELECT 
    username, 
    ip_address, 
    status, 
    failure_reason, 
    created_at
FROM core.login_history
ORDER BY created_at DESC
LIMIT 50;

-- 4. Find all admins
SELECT username, email, status FROM core.users WHERE role = 'ADMIN';

-- 5. Check blocked tokens (Blacklist)
SELECT * FROM core.access_token_blacklist ORDER BY blacklisted_at DESC;
