---
id: V2-26
title: "Test phân quyền tài liệu theo phòng ban (FR-29) trong CI"
type: test
status: todo
created: 2026-10-19
updated: 2026-10-19
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-23, V2-24]
blocks: [V2-17]
branch: "test/tests-department-authorization"
assignee: pair
---

# TICKET V2-26: Test phân quyền phòng ban

## 1. Bối cảnh & Mục tiêu
PRD-V2 FR-29, ADR-007 §4.4–4.5. Lớp kiểm thử thứ hai, độc lập với cách ly workspace (V2-14/FR-19): trong **cùng một workspace**, tài liệu giới hạn phòng ban không lộ cho người ngoài phòng ban.

## 2. Tiêu chí Hoàn thành
- [ ] Dữ liệu test: một workspace, phòng ban A và B, thành viên ở A, ở B, chưa có phòng ban, `SUSPENDED`, cùng OWNER và ADMIN; tài liệu `WORKSPACE`, `DEPARTMENTS[A]`, `DEPARTMENTS[A,B]`, mỗi tài liệu có chuỗi bí mật riêng.
- [ ] Mọi ô của ma trận ADR-007 §4.4 được kiểm qua: danh sách, tìm kiếm, chi tiết, xem trước, URL tải, dense, BM25, rerank, context gửi LLM (LLM mock ghi lại prompt), trích dẫn, lịch sử hội thoại, cache.
- [ ] Ca thay đổi: chuyển A → B (sau refresh), tạm khóa, archive phòng ban A, thử xóa phòng ban A còn tài liệu (bị chặn), thu hẹp tài liệu từ `WORKSPACE` sang `DEPARTMENTS[A]`, ai-service chưa nhận cập nhật (fail closed).
- [ ] Không câu trả lời nào trả về tên hay nội dung tài liệu ngoài quyền; số chunk vào context không giảm vì lọc sau top-k (lọc trước `LIMIT`).
- [ ] Chạy trong GitHub Actions cùng FR-19 trên mỗi PR.

## 3. Hướng dẫn
- Dùng chung khung test của V2-14; giữ hai bộ test tách biệt để lỗi chỉ ra đúng lớp bị hỏng.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Integration | Bộ FR-29 trên Postgres thật, core-api + ai-service, LLM mock | theo V2-14 |
