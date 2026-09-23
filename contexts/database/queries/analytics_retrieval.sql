-- ============================================================
-- ANALYTICS SCHEMA RETRIEVAL SCRIPTS
-- Purpose: Querying feedback, usage stats, and audit logs
-- ============================================================

-- 1. Check user feedback on AI answers
SELECT 
    f.type, 
    f.comment, 
    f.question_text, 
    f.answer_text, 
    f.created_at
FROM analytics.feedbacks f
ORDER BY f.created_at DESC;

-- 2. Daily usage summary (Last 7 days)
SELECT 
    date, 
    total_questions, 
    total_requests, 
    total_errors, 
    total_tokens_used
FROM analytics.daily_aggregates
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC;

-- 3. Audit log for specific sensitive actions
SELECT 
    username, 
    action, 
    resource_type, 
    resource_name, 
    created_at
FROM analytics.audit_logs
WHERE action IN ('USER_REVOKE', 'DOCUMENT_DELETE', 'SETTINGS_UPDATE')
ORDER BY created_at DESC;

-- 4. Calculate overall satisfaction rate
SELECT 
  COUNT(*) FILTER (WHERE type = 'LIKE') * 100.0 / COUNT(*) as satisfaction_percentage
FROM analytics.feedbacks;

-- 5. List popular questions from analytics
SELECT 
    question_sample, 
    ask_count, 
    unique_users_count, 
    total_likes
FROM analytics.popular_questions
ORDER BY ask_count DESC
LIMIT 20;
