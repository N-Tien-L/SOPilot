---
id: V2-04
title: "Đóng backlog M1/NEXT và dọn tài liệu trùng lặp"
type: docs
status: todo
created: 2026-10-17
updated: 2026-10-17
scope: docs
priority: P1
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-01]
blocks: []
branch: "docs/docs-close-legacy"
assignee: pair
---

# TICKET V2-04: Đóng backlog cũ

## 1. Bối cảnh & Mục tiêu
Tránh nhầm tiến độ giữa hai hướng. Chỉ làm sau khi V2-01 được duyệt.

## 2. Tiêu chí Hoàn thành
- [ ] NEXT-01, 03, 04, 05, 06 chuyển trạng thái đóng. Frontmatter ticket chỉ cho phép `todo|in-progress|review|done`, nên cần thêm giá trị hợp lệ (ví dụ `superseded`) vào `docs/README.md` trước, hoặc ghi chú thay thế trong thân ticket. Chọn một cách, nêu rõ.
- [ ] NEXT-02, M1-03, M1-04, M1-05: giữ nguyên trạng thái `review`/`in-progress`, thêm ghi chú "port sang V2-11".
- [ ] PLAN-M1 và PLAN-NEXT có ghi chú bị PLAN-V2 thay thế.
- [ ] Xóa `docs/plans/` (đã deprecated) chỉ khi NEXT-02 đã commit; kiểm `git status` trước, không xóa file ngoài đúng đường dẫn.
- [ ] Commit nốt nhánh `fix/auth-google-roster-admission` và PR qua `develop` (việc này cần owner yêu cầu rõ ràng).

## 3. Hướng dẫn
- **File:** `docs/03-plans/PLAN-M1-jit-onboarding.md`, `PLAN-NEXT-implementation-readiness.md`, các ticket nêu trên, `docs/README.md`.
- **Action:** MODIFY. Giữ bộ đếm PLAN khớp frontmatter ticket.

## 4. Kiểm thử
Đối chiếu bộ đếm PLAN với frontmatter bằng `Grep "status:"` trên `docs/03-plans/tickets/`.
