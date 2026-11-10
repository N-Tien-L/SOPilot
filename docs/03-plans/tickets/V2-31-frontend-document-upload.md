---
id: V2-31
title: "Frontend: nạp nhiều tài liệu và theo dõi xử lý"
type: feat
status: todo
created: 2026-10-24
updated: 2026-11-10
author: "Owner"
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-12, V2-15, V2-36]
blocks: [V2-17]
branch: "feat/web-v2-31"
assignee: pair
---

# TICKET V2-31: Frontend: nạp nhiều tài liệu và theo dõi xử lý

## 1. Bối cảnh & Mục tiêu
Tách phạm vi từ V2-15 XL ngày 2026-10-24; giữ nguyên yêu cầu PRD/TECH đã duyệt. Dùng skill frontend-delivery và `.claude/rules/frontend.md` khi triển khai.

## 2. Tiêu chí Hoàn thành
- [ ] Chọn tối đa 10 file mỗi lượt (chọn file thứ 11 bị chặn kèm thông báo), gửi từng request upload, tối đa 3 đồng thời; mỗi file hiện trạng thái "Đang tải lên", "Đang xử lý", "Sẵn sàng" hoặc lỗi với lý do riêng (PRD-V2 FR-30). Upload xong chỉ hiện "Đang xử lý", không có liên kết nội dung cho tới `READY`.
- [ ] Kết quả độc lập: một lượt 10 file có 2 file lỗi (ví dụ PDF scan và `.txt`) vẫn để 8 file đi tiếp; file lỗi có hành động riêng: "Thử lại" cho lỗi tạm thời, "Thay file"/"Xóa" cho lỗi nội dung (bảng mã TECH-V2-core-api §5.5), "Gửi lại" khi lỗi mạng; thử lại không gửi lại file đã thành công.
- [ ] Hiển thị đúng thông điệp cho `409 DUPLICATE_DOCUMENT` (kèm liên kết tài liệu đã có), `409 DOCUMENT_UNCHANGED` ("Nội dung file không thay đổi"), `409 VERSION_IN_PROGRESS`, `409 QUOTA_EXCEEDED` (kèm hạn mức và số đã dùng), `413`, `415`.
- [ ] Không bắt người dùng chờ: đóng hộp thoại được khi không còn file đang tải lên (cảnh báo rời trang chỉ trong lúc đang truyền bytes); danh sách tài liệu tự làm mới trạng thái khi còn tài liệu đang xử lý và dừng khi không còn.
- [ ] Upload chỉ cho PDF có lớp chữ và MD; TXT bỏ khỏi MVP, DOCX hoãn (FR-06). Hiển thị lỗi `415` từ API với hướng dẫn (TXT → `.md`, DOCX → PDF có lớp chữ); không có luồng chuyển đổi trên server.

## 3. Hướng dẫn
1. Khai báo types trong `frontend/web/types`, API client ở `frontend/web/lib/api.ts` theo TECH-V2-core-api/ai-service.
2. Triển khai trong `frontend/web/app/` và `frontend/web/components/`, dùng khung V2-15.
3. Ghi bằng chứng trình duyệt theo từng acceptance criterion, cập nhật README frontend.
- Cập nhật contract liên quan trong `.agent/context/` cùng thay đổi; V2-17 chỉ tổng hợp và bỏ mô tả V1.

## 4. Kiểm thử
- Trình duyệt: 10/11 file, giới hạn 3 upload, partial failure, retry riêng, 409/413/415, đóng hộp thoại và polling dừng đúng lúc.
- `./scripts/validate-build.ps1 -Scope web`; pre-commit. Build/lint không thay bằng chứng UC-04/UC-12.
