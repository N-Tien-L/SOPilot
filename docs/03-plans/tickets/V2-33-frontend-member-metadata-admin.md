---
id: V2-33
title: "Frontend: thành viên, phòng ban và metadata tài liệu"
type: feat
status: todo
created: 2026-10-24
updated: 2026-11-10
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-15, V2-23, V2-24, V2-25, V2-30, V2-36]
blocks: [V2-17]
branch: "feat/web-v2-33"
assignee: pair
---

# TICKET V2-33: Frontend: thành viên, phòng ban và metadata tài liệu

## 1. Bối cảnh & Mục tiêu
Tách phạm vi từ V2-15 XL ngày 2026-10-24; giữ nguyên yêu cầu PRD/TECH đã duyệt. Dùng skill frontend-delivery và `.claude/rules/frontend.md` khi triển khai. FR-04/FR-22 đến FR-29.

## 2. Tiêu chí Hoàn thành
- [ ] Thành viên: hồ sơ (họ tên, mã nhân viên, chức danh, phòng ban), tạm khóa/mở khóa; phòng ban và category phẳng: tạo, đổi tên, ngừng sử dụng, xóa khi hợp lệ. Ẩn phòng ban ở workspace một thành viên.
- [ ] Tài liệu: sửa metadata, chọn phạm vi `WORKSPACE`/`DEPARTMENTS`, xem và chấp nhận/sửa gợi ý metadata; trạng thái gợi ý không chặn thao tác khác.
  - Form gợi ý theo quyết định owner 2026-11-12 trong V2-25 §2a: một form sửa được, `doc_code`/revision/ngày hiệu lực chỉ đọc, nút tạo category gợi ý chỉ cho OWNER/ADMIN.
- [ ] UI tạo/thu hồi/nhận link lời mời; thao tác OWNER/ADMIN theo quyền và hiển thị lỗi API đúng ngữ cảnh.
- [ ] Kiểm bằng trình duyệt quyền admin/member, trạng thái tạm khóa, gợi ý đang chạy/lỗi và quyền đọc thay đổi.

## 3. Hướng dẫn
1. Khai báo types trong `frontend/web/types`, API client ở `frontend/web/lib/api.ts` theo TECH-V2-core-api/ai-service.
2. Triển khai trong `frontend/web/app/` và `frontend/web/components/`, dùng khung V2-15.
3. Ghi bằng chứng trình duyệt theo từng acceptance criterion, cập nhật README frontend.
- Cập nhật contract liên quan trong `.agent/context/` cùng thay đổi; V2-17 chỉ tổng hợp và bỏ mô tả V1.

## 4. Kiểm thử
- Trình duyệt: hồ sơ/phòng ban/category phẳng, lời mời, OWNER cuối, sửa quyền tài liệu, gợi ý metadata không chặn upload/chat.
- `./scripts/validate-build.ps1 -Scope web`; pre-commit.
