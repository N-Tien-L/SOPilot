---
id: V2-13
title: "Phản hồi câu trả lời và danh sách khoảng trống tri thức"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-17
scope: feedback
priority: P1
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-12]
blocks: []
branch: "feat/feedback-v2-gaps"
assignee: pair
---

# TICKET V2-13: Phản hồi và khoảng trống tri thức

## 1. Bối cảnh & Mục tiêu
FR-16, FR-17. Đưa feedback-service vào core-api ở dạng tối giản, không dashboard analytics.

## 2. Tiêu chí Hoàn thành
- [ ] Up/down vote + bình luận tùy chọn cho một câu trả lời, mỗi user một phiếu mỗi câu.
- [ ] Admin xem câu bị từ chối và bị downvote, đánh dấu đã xử lý; không có quy trình duyệt nhiều bước.
- [ ] Lọc theo `workspace_id` + RLS; member không xem được danh sách của admin.
- [ ] Không có dashboard, export hay xu hướng (ngoài phạm vi PRD §5).

## 3. Hướng dẫn
- **File:** `services/core-api/` module feedback; nguồn: `services/feedback-service`, `services/ai-qa-service/src/services/knowledge_gap.py` (chỉ tham khảo, ngưỡng cũ không dùng lại).

## 4. Kiểm thử
Unit cho quyền và idempotent vote (`./mvnw test`); integration trên Postgres thật (`./mvnw verify`).
