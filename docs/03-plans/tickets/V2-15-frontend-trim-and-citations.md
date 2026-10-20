---
id: V2-15
title: "Frontend: thu gọn, chọn workspace, trình xem trích dẫn"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-21
scope: web
priority: P0
size: XL
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-11, V2-12, V2-23, V2-24, V2-25]
blocks: [V2-17]
branch: "feat/web-v2-workspace-citations"
assignee: pair
---

# TICKET V2-15: Frontend V2

## 1. Bối cảnh & Mục tiêu
Giữ các component chat; bỏ trang admin hệ thống, analytics, roster, phòng ban, OnlyOffice, so sánh version, UI chọn model. Điều phối theo skill `frontend-delivery` (CLAUDE.md toàn cục). Sửa 2026-10-21 theo [AUDIT-markdown-normalization](../../04-reports/AUDIT-markdown-normalization-and-preview-2026-10-21.md) §4: luồng nạp ≤ 10 file và màn "Nội dung hệ thống nhận diện" (PRD-V2 FR-30, FR-31, UC-12). Nếu ticket vượt khung XL khi bắt đầu, tách phần nạp tài liệu/màn xem thành ticket con và cập nhật PLAN.

## 2. Tiêu chí Hoàn thành
- [ ] Chọn tối đa 10 file mỗi lượt (chọn file thứ 11 bị chặn kèm thông báo), gửi từng request upload, tối đa 3 đồng thời; mỗi file hiện trạng thái "Đang tải lên", "Đang xử lý", "Sẵn sàng" hoặc lỗi với lý do riêng (PRD-V2 FR-30). Upload xong chỉ hiện "Đang xử lý", không có liên kết nội dung cho tới `READY`.
- [ ] Kết quả độc lập: một lượt 10 file có 2 file lỗi (ví dụ PDF scan và `.txt`) vẫn để 8 file đi tiếp; file lỗi có hành động riêng: "Thử lại" cho lỗi tạm thời, "Thay file"/"Xóa" cho lỗi nội dung (bảng mã TECH-V2-core-api §5.5), "Gửi lại" khi lỗi mạng; thử lại không gửi lại file đã thành công.
- [ ] Hiển thị đúng thông điệp cho `409 DUPLICATE_DOCUMENT` (kèm liên kết tài liệu đã có), `409 DOCUMENT_UNCHANGED` ("Nội dung file không thay đổi"), `409 VERSION_IN_PROGRESS`, `409 QUOTA_EXCEEDED` (kèm hạn mức và số đã dùng), `413`, `415`.
- [ ] Không bắt người dùng chờ: đóng hộp thoại được khi không còn file đang tải lên (cảnh báo rời trang chỉ trong lúc đang truyền bytes); danh sách tài liệu tự làm mới trạng thái khi còn tài liệu đang xử lý và dừng khi không còn.
- [ ] Upload chỉ cho PDF có lớp chữ và MD; TXT bỏ khỏi MVP, DOCX hoãn (FR-06). Hiển thị lỗi `415` từ API với hướng dẫn (TXT → `.md`, DOCX → PDF có lớp chữ); không có luồng chuyển đổi trên server.
- [ ] Màn "Nội dung hệ thống nhận diện" (FR-31): chỉ mở khi `currentVersion` tồn tại (`READY`); PDF hiện file gốc (URL ký sẵn) cạnh Markdown chuẩn, mốc "Trang N" bấm vào thì PDF nhảy trang; màn hẹp dùng hai tab; MD hiện Markdown chuẩn + nút tải gốc. Nhãn phiên bản: khi `latestVersion` khác `currentVersion`, hiện "Phiên bản N đang dùng để hỏi đáp; phiên bản N+1 đang xử lý / xử lý lỗi". Cảnh báo chỉ hiện khi API có `warnings`; khối khung đã loại liệt kê thu gọn. Câu cố định: `READY` là đã xử lý xong, không có nghĩa nội dung đã được kiểm tra. Không có editor hay nút "đã kiểm tra".
- [ ] Render Markdown an toàn: không dùng `rehype-raw` (khác `DocumentViewerModal` cũ); fixture MD chứa `<script>`, `<img onerror>` và ảnh ngoài hiển thị dạng văn bản/liên kết, không chạy script, không tự tải ảnh ngoài.
- [ ] Ngoài quyền đọc (FR-25) hoặc tài liệu chưa `READY`: màn xem không lộ nội dung (API `404`).
- [ ] Đăng nhập Google; chọn/chuyển workspace; token giữ theo workspace (T8).
- [ ] Trang: chat, tài liệu, thành viên + lời mời, khoảng trống tri thức, cài đặt workspace.
- [ ] Thành viên: hồ sơ (họ tên, mã nhân viên, chức danh, phòng ban), tạm khóa/mở khóa; phòng ban và category phẳng: tạo, đổi tên, ngừng sử dụng, xóa khi hợp lệ. Ẩn phòng ban ở workspace một thành viên.
- [ ] Tài liệu: sửa metadata, chọn phạm vi `WORKSPACE`/`DEPARTMENTS`, xem và chấp nhận/sửa gợi ý metadata; trạng thái gợi ý không chặn thao tác khác.
- [ ] Trình xem trích dẫn: bấm `[n]` mở đúng trang PDF / đúng đoạn, tô sáng nguồn bằng offset UTF-16 trên Markdown chuẩn (FR-14); dùng chung thành phần hiển thị với màn FR-31.
- [ ] Hiển thị từ chối "không tìm thấy" và trạng thái xử lý tài liệu.
- [ ] Xóa enum model OpenAI không dùng và mọi gọi tới gateway cũ.
- [ ] Sửa 61 lỗi lint hiện có hoặc loại bỏ cùng code bị cắt; `pnpm build` và `pnpm lint` xanh.
- [ ] **Kiểm tra bằng trình duyệt thật** các UC-01, 02, 04, 05, 07 đến 12 (gồm nhảy trang PDF trên Chrome và Firefox, bố cục màn hẹp); báo rõ nếu chưa kiểm tra (build/lint không thay thế được).

## 3. Hướng dẫn
- **File:** `frontend/web/` theo `.agent/rules/frontend.md`; API client `frontend/web/lib/api.ts`; types `frontend/web/types`.
- **Giữ bản demo chạy được trong lúc chuyển (ADR-004 §4.5):** frontend sửa tại chỗ, nên khi bỏ gọi gateway cũ thì nó không còn chạy với stack cũ.
  - Chỉ bắt đầu nối API khi các ticket trong `depends_on` đã có endpoint chạy được trên `docker-compose.v2.yml`; trước đó chỉ làm phần UI không phụ thuộc backend (thu gọn trang, component trình xem) trên nhánh của ticket.
  - Đích của `rewrites` (TECH-V2-core-api §1.1) đọc từ env server-side (`CORE_API_URL`, mặc định `http://core-api:8080`; `AI_SERVICE_URL`, mặc định `http://ai-service:8000`) để chạy được cả trong compose lẫn `pnpm dev` trên host. Ghi vào `frontend/web/.env.example`.
  - Trước khi merge nhánh này vào `develop`, tạo tag `v1-final` trên `develop` (commit cuối frontend còn chạy với stack cũ). Bản demo dự phòng: `git checkout v1-final` + `docker-compose.yml` cũ. V2-17 dùng lại tag này.

## 4. Kiểm thử
```powershell
./scripts/validate-build.ps1 -Scope web
```
Cộng ghi chú các luồng đã thử tay trên trình duyệt.
