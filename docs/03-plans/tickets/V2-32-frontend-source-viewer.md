---
id: V2-32
title: "Frontend: nội dung nhận diện và trình xem trích dẫn"
type: feat
status: todo
created: 2026-10-24
updated: 2026-10-24
scope: web
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-12, V2-15]
blocks: [V2-17]
branch: "feat/web-v2-32"
assignee: pair
---

# TICKET V2-32: Frontend: nội dung nhận diện và trình xem trích dẫn

## 1. Bối cảnh & Mục tiêu
Tách phạm vi từ V2-15 XL ngày 2026-10-24; giữ nguyên yêu cầu PRD/TECH đã duyệt. Dùng skill frontend-delivery và `.agent/rules/frontend.md` khi triển khai. FR-14/FR-31, TECH-V2-ai-service §7.3/§7.5.

## 2. Tiêu chí Hoàn thành
- [ ] Màn "Nội dung hệ thống nhận diện" (FR-31): chỉ mở khi `currentVersion` tồn tại (`READY`); PDF hiện file gốc (URL ký sẵn) cạnh Markdown chuẩn, mốc "Trang N" bấm vào thì PDF nhảy trang; màn hẹp dùng hai tab; MD hiện Markdown chuẩn + nút tải gốc. Nhãn phiên bản: khi `latestVersion` khác `currentVersion`, hiện "Phiên bản N đang dùng để hỏi đáp; phiên bản N+1 đang xử lý / xử lý lỗi". Cảnh báo chỉ hiện khi API có `warnings`; khối khung đã loại liệt kê thu gọn. Câu cố định: `READY` là đã xử lý xong, không có nghĩa nội dung đã được kiểm tra. Không có editor hay nút "đã kiểm tra".
- [ ] Render Markdown an toàn: không dùng `rehype-raw` (khác `DocumentViewerModal` cũ); fixture MD chứa `<script>`, `<img onerror>` và ảnh ngoài hiển thị dạng văn bản/liên kết, không chạy script, không tự tải ảnh ngoài.
- [ ] Ngoài quyền đọc (FR-25) hoặc tài liệu chưa `READY`: màn xem không lộ nội dung (API `404`).
- [ ] Trình xem trích dẫn: bấm `[n]` mở đúng trang PDF / đúng đoạn, tô sáng nguồn bằng offset UTF-16 trên Markdown chuẩn (FR-14); dùng chung thành phần hiển thị với màn FR-31.
- [ ] Trích dẫn phiên bản cũ chỉ hiện snapshot/nhãn; không gọi viewer hiện hành khi `isCurrentVersion=false`.
- [ ] Kiểm trên Chrome/Firefox: nhảy trang PDF, offset UTF-16 có emoji, màn hẹp, quyền bị thu hồi trả 404.

## 3. Hướng dẫn
1. Khai báo types trong `frontend/web/types`, API client ở `frontend/web/lib/api.ts` theo TECH-V2-core-api/ai-service.
2. Triển khai trong `frontend/web/app/` và `frontend/web/components/`, dùng khung V2-15.
3. Ghi bằng chứng trình duyệt theo từng acceptance criterion, cập nhật README frontend.
- Cập nhật contract liên quan trong `.agent/context/` cùng thay đổi; V2-17 chỉ tổng hợp và bỏ mô tả V1.

## 4. Kiểm thử
- Trình duyệt: PDF/MD, trang/bảng nhiều trang, emoji, XSS/ảnh ngoài, current/latest version, chưa READY và quyền bị thu hồi.
- `./scripts/validate-build.ps1 -Scope web`; pre-commit. Ghi rõ browser nào chưa kiểm.
