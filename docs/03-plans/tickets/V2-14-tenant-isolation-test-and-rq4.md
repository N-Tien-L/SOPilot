---
id: V2-14
title: "Test cách ly tenant FR-19 trong CI và đo RQ4"
type: test
status: todo
created: 2026-10-17
updated: 2026-10-19
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-12]
blocks: [V2-17, V2-18]
branch: "test/tests-tenant-isolation"
assignee: pair
---

# TICKET V2-14: Cách ly tenant và RQ4

## 1. Bối cảnh & Mục tiêu
Rủi ro lớn nhất của hệ thống cũ (A1, A2). Cần bằng chứng 0 rò rỉ chạy tự động.

## 2. Tiêu chí Hoàn thành
- [ ] Test tạo ≥ 3 workspace, mỗi workspace có tài liệu chứa "chuỗi bí mật" riêng; chứng minh không câu hỏi, API tài liệu, hội thoại, feedback hay audit nào trả dữ liệu workspace khác.
- [ ] Test thiếu/giả `workspace_id` trong token và truy vấn trực tiếp DB bằng role ứng dụng bị RLS chặn.
- [ ] Workflow GitHub Actions chạy test này trên mỗi PR. Phân quyền phòng ban trong cùng workspace là bộ riêng ở V2-26.
- [ ] RQ4: đo độ trễ truy xuất với lọc ứng dụng so với ứng dụng + RLS trên cùng dữ liệu, ghi p50/p95 vào báo cáo.

## 3. Hướng dẫn
- **File:** `tests/tenant-isolation/` (CREATE), `.github/workflows/tenant-isolation.yml`, mở rộng `eval/` cho RQ4.

## 4. Kiểm thử
Chính ticket này là test. Bằng chứng: log CI xanh và một lần chạy cố ý bỏ lọc để xác nhận test **fail** khi có rò rỉ (kiểm chứng test không vô nghĩa).
