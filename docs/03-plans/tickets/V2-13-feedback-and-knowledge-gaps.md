---
id: V2-13
title: "Phản hồi câu trả lời và danh sách khoảng trống tri thức"
type: feat
status: todo
created: 2026-10-17
updated: 2026-11-09
author: "Owner"
scope: ai-qa
priority: P1
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-12]
blocks: [V2-15]
branch: "feat/ai-qa-v2-feedback-gaps"
assignee: pair
---

# TICKET V2-13: Phản hồi và khoảng trống tri thức

## 1. Bối cảnh & Mục tiêu
FR-16, FR-17. Thay feedback-service bằng phần tối giản trong ai-service, không dashboard analytics. Owner chốt 2026-10-20 (TECH-V2-core-api §11 Q1, ADR-004 §4.1): đặt ở ai-service vì câu hỏi, câu trả lời và cờ từ chối nằm trong schema `rag`. Thiết kế: TECH-V2-ai-service §7.6.

## 2. Tiêu chí Hoàn thành
- [ ] Up/down vote + bình luận tùy chọn cho một câu trả lời, mỗi user một phiếu mỗi câu.
- [ ] Admin xem câu bị từ chối và bị downvote, đánh dấu đã xử lý; không có quy trình duyệt nhiều bước. Sửa 2026-10-21 (owner chốt D2, TECH-V2-ai-service §7.6): danh sách gồm câu có `refusal_reason` là `NO_EVIDENCE` hoặc `GENERATOR_NOT_FOUND`, câu bị downvote và câu `ANSWERED` có `checks.citationCount = 0`; **loại** `OUT_OF_SCOPE`, `INPUT_INVALID`, `TEMPLATE`, `REFUSED_GUARD`.
- [ ] Sửa 2026-10-21 (D8): câu hỏi trong danh sách là bản đã che PII (tính lại bằng `qa/pii.py` khi trả lời, không lưu bản thứ hai); test với câu chứa email và số điện thoại.
- [ ] Lọc theo `workspace_id` + RLS; member không xem được danh sách của admin; danh sách không kèm tên người hỏi (FR-15).
- [ ] Không có dashboard, export hay xu hướng (ngoài phạm vi PRD §5).
- [ ] (Chuyển từ V2-14) Bộ cách ly tenant phủ API feedback và danh sách khoảng trống tri thức: ≥ 3 workspace có "chuỗi bí mật", không trả phiếu, bình luận hay câu hỏi của workspace khác; chạy trong `tenant-isolation.yml`.

## 3. Hướng dẫn
- **File:** `services/ai-service/` (bảng `rag.message_feedback`, `rag.knowledge_gap_status`, API `/ai/v1/messages/{id}/feedback`, `/ai/v1/knowledge-gaps`); nguồn: `services/feedback-service`, `services/ai-qa-service/src/services/knowledge_gap.py` (chỉ tham khảo, ngưỡng cũ không dùng lại).

## 4. Kiểm thử
Unit cho quyền và idempotent vote; integration trên Postgres thật (`./scripts/run-tests.ps1 -Scope ai-service`, scope mới thêm ở V2-08).
