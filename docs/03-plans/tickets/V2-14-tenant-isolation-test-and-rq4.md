---
id: V2-14
title: "Test cách ly tenant FR-19 trong CI và đo RQ4"
type: test
status: review
created: 2026-10-17
updated: 2026-11-06
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
- [ ] Test tạo ≥ 3 workspace, mỗi workspace có tài liệu chứa "chuỗi bí mật" riêng; chứng minh không câu hỏi, API tài liệu, hội thoại, feedback hay audit nào trả dữ liệu workspace khác. **Còn mở một phần:** API tài liệu, thành viên, phòng ban, audit và bảng hội thoại/feedback (mức DB) đã phủ; hỏi đáp, hội thoại, feedback qua API chờ V2-10/V2-13.
- [x] Test thiếu/giả `workspace_id` trong token và truy vấn trực tiếp DB bằng role ứng dụng bị RLS chặn.
- [ ] Workflow GitHub Actions chạy test này trên mỗi PR. **Còn mở:** file workflow đã viết, chưa có run xanh trên GitHub. Phân quyền phòng ban trong cùng workspace là bộ riêng ở V2-26.
- [x] RQ4: đo độ trễ truy xuất với lọc ứng dụng so với ứng dụng + RLS trên cùng dữ liệu, ghi p50/p95 vào báo cáo.

## 3. Hướng dẫn
- **File:** `tests/tenant-isolation/` (CREATE), `.github/workflows/tenant-isolation.yml`, mở rộng `eval/` cho RQ4.

## 4. Kiểm thử
Chính ticket này là test. Bằng chứng: log CI xanh và một lần chạy cố ý bỏ lọc để xác nhận test **fail** khi có rò rỉ (kiểm chứng test không vô nghĩa).

## 5. Bằng chứng triển khai (2026-11-06, chờ owner nghiệm thu)

Chi tiết và số đo: [AUDIT-v2-14](../../04-reports/AUDIT-v2-14-tenant-isolation-rq4-2026-11-06.md).

- **Code:** `tests/tenant-isolation/` (`isolation.py`, `conftest.py`, `test_db_isolation.py`, README), `services/core-api/src/test/java/com/sopilot/core/tenancy/TenantIsolationApiIT.java`, `.github/workflows/tenant-isolation.yml` (4 job: database, negative-control, core-api, ai-service), `eval/rq4_rls_latency.py`.
- **Lệnh và kết quả:** `cd tests/tenant-isolation && uv run pytest` -> 31 xanh; `ISOLATION_MUTATION=disable-rls uv run pytest` -> 23 fail (đúng yêu cầu "cố ý bỏ lọc thì test phải fail"); `./mvnw verify -Dit.test=TenantIsolationApiIT` -> 8 xanh; đột biến thủ công bỏ lọc `workspace_id` + tắt RLS -> test fail rồi đã khôi phục mã; `uv run pytest tests/integration/test_retrieval.py` (ai-service) -> 12 xanh (một lần fail đầu, ba lần sau xanh).
- **RQ4:** RLS thêm +0,5% đến +2% ở p50, p95 không phân biệt được với nhiễu, ở 10.000 và 30.000 chunk tổng hợp; top-10 giống hệt ở 600/600 truy vấn.
- **Chưa kiểm:** run xanh trên GitHub Actions; hỏi đáp/hội thoại/feedback qua API; RQ4 trên dữ liệu thật và quy mô lớn hơn 30.000 chunk.
