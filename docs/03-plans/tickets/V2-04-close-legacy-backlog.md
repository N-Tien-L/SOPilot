---
id: V2-04
title: "Đóng backlog M1/NEXT và dọn tài liệu trùng lặp"
type: docs
status: done
created: 2026-10-17
updated: 2026-10-24
author: "Owner"
scope: docs
priority: P1
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-01]
blocks: [V2-18]
branch: "docs/docs-close-legacy"
assignee: pair
---

# TICKET V2-04: Đóng backlog cũ

## 1. Bối cảnh & Mục tiêu
Tránh nhầm tiến độ giữa hai hướng. Chỉ làm sau khi V2-01 được duyệt.

## 2. Tiêu chí Hoàn thành
- [x] NEXT-01, 03, 04, 05, 06 chuyển trạng thái đóng. Frontmatter đã bổ sung `superseded` theo `docs/README.md`; ghi rõ tài liệu thay thế trong thân ticket. Chọn một cách, nêu rõ.
  - **Chọn:** thêm `superseded` vào bảng trạng thái ticket ở `docs/README.md` (không tính vào bộ đếm PLAN), mỗi ticket ghi ticket/tài liệu thay thế ở đầu thân. M1-06 (E2E của M1, ngoài danh sách gốc) cũng `superseded`, ánh xạ sang V2-14/V2-26/V2-17.
- [x] NEXT-02, M1-03, M1-04, M1-05: giữ nguyên trạng thái `review`/`in-progress`, thêm ghi chú "port sang V2-11".
- [x] PLAN-M1 và PLAN-NEXT (`status: superseded`) có ghi chú bị PLAN-V2 thay thế.
- [x] Xóa `docs/plans/` (đã deprecated) chỉ khi NEXT-02 đã commit (commit `9638f0a`); 14 file đều đã tracked, không có thay đổi chưa commit; bỏ nhắc `docs/plans/` trong `AGENTS.md`, `CLAUDE.md`, `docs/README.md`, skill `execute-ticket`; kiểm `git status` trước, không xóa file ngoài đúng đường dẫn.
- [x] Commit nốt nhánh `fix/auth-google-roster-admission` và PR qua `develop`: đã xong trước ticket này (PR #2 merge vào `origin/develop`, commit `2954aca`).

## 3. Hướng dẫn
- **File:** `docs/archive/03-plans/PLAN-M1-jit-onboarding.md`, `PLAN-NEXT-implementation-readiness.md`, các ticket nêu trên, `docs/README.md`.
- **Action:** MODIFY. Giữ bộ đếm PLAN khớp frontmatter ticket.

## 4. Kiểm thử
Đối chiếu bộ đếm PLAN với frontmatter bằng `Grep "status:"` trên `docs/03-plans/tickets/`.

Kết quả 2026-10-20: `Grep "status:"` trên `docs/03-plans/tickets/` khớp bộ đếm: PLAN-M1 2 done, 2 review (implemented 4); PLAN-NEXT 0 done, 1 review (implemented 1). `superseded` không được đếm. Review tài liệu hoàn tất bởi Codex ngày 2026-10-24; xem bằng chứng bên dưới.

### Review 2026-10-24
Đối chiếu trạng thái/tài liệu thay thế của 12 ticket M1/NEXT, bộ đếm hai PLAN, xác nhận `docs/plans/` không tồn tại và các commit `9638f0a`, `2954aca` thuộc lịch sử HEAD. Sửa chỉ dẫn bắt đầu và cây thư mục còn lỗi thời trong `docs/README.md`. Không thay trạng thái lịch sử của M1/NEXT, không xóa thêm file. Bằng chứng: [AUDIT readiness](../../04-reports/AUDIT-v2-readiness-preparation-2026-10-24.md).
