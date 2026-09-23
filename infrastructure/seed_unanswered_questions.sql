-- ============================================================
-- SEED: Unanswered Questions
-- Run this to populate test data for unanswered questions display
-- ============================================================

-- Insert unanswered questions (simple version without foreign key constraints)
INSERT INTO conversation.unanswered_questions (
    id, user_id, question, question_normalized, status, resolved, 
    priority, category, top_similarity_score, trace_id, created_at
)
SELECT 
    uuid_generate_v4(),
    u.id,
    q.question,
    lower(q.question),
    q.status,
    false,
    q.priority,
    q.category,
    q.similarity,
    'seed-' || substr(u.id::text, 1, 8),
    NOW() - (random() * INTERVAL '30 days')
FROM (
    VALUES 
        ('Chính sách thưởng tết năm 2025 được tính như thế nào?', 'THUONG', 'PENDING', 'LOW', 0.25),
        ('Thời gian nghỉ phép năm được quy định ra sao cho nhân viên mới?', 'NGHI_PHEP', 'PENDING', 'NORMAL', 0.18),
        ('Quy trình xin nghỉ ốm cần những giấy tờ gì?', 'NGHI_PHEP', 'REVIEWING', 'NORMAL', 0.22),
        ('Chính sách bảo hiểm xã hội công ty hỗ trợ bao nhiêu phần trăm?', 'BAO_HIEM', 'PENDING', 'HIGH', 0.15),
        ('Tôi muốn biết về quy định mang laptop cá nhân vào công ty?', 'AN_NINH', 'PENDING', 'NORMAL', 0.12),
        ('Quy trình thăng tiến cho vị trí trưởng nhóm như thế nào?', 'THANG_TIEN', 'PENDING', 'HIGH', 0.20),
        ('Chính sách đào tạo nội bộ có chi phí bao nhiêu mỗi năm?', 'DAO_TAO', 'REVIEWING', 'NORMAL', 0.28),
        ('Thời hạn thanh toán lương là ngày mấy hàng tháng?', 'LUONG', 'PENDING', 'URGENT', 0.08),
        ('Quy định về giờ làm việc linh hoạt được áp dụng từ khi nào?', 'GIO_LAM_VIEC', 'PENDING', 'NORMAL', 0.19),
        ('Chính sách hỗ trợ đi lại cho nhân viên remote như thế nào?', 'HO_TRO', 'PENDING', 'LOW', 0.14)
) AS q(question, category, status, priority, similarity)
CROSS JOIN (
    SELECT id FROM poliwise_auth.users WHERE username = 'admin' LIMIT 1
) u(user_id)
ON CONFLICT DO NOTHING;

-- Update resolved field based on status
UPDATE conversation.unanswered_questions 
SET resolved = true 
WHERE status IN ('ANSWERED', 'REJECTED');

-- Show result
SELECT id, question, status, priority, category, created_at 
FROM conversation.unanswered_questions 
ORDER BY created_at DESC 
LIMIT 20;
