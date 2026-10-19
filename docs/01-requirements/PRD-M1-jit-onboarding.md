---
id: PRD-M1-JIT-ONBOARDING
title: "JIT Onboarding & Quản lý Danh bạ Định danh Nhân sự"
status: superseded
created: 2026-09-25
updated: 2026-10-20
author: "Principal Software Architect & Tech Lead"
milestone: "Milestone 1: JIT Onboarding v1.0"
priority: P0
---

# YÊU CẦU NGHIỆP VỤ & ĐẶC TẢ TÍNH NĂNG (PRD)

> **Mã tài liệu:** `PRD-M1-JIT-ONBOARDING` | **Milestone:** Milestone 1: JIT Onboarding v1.0 | **Trạng thái:** Superseded bởi PRD-V2-SOPILOT-MVP (2026-10-20)

---

## 1. Problem Statement & Motivation

### Vấn đề hiện tại:
Quy trình cấp quyền và khởi tạo tài khoản nhân viên mới vào hệ thống quản lý tri thức & quy chế nội bộ SOPilot đang dựa vào đăng ký thủ công hoặc gửi thư mời phức tạp, gây ra các điểm nghẽn:
1. **Quản trị viên (HR/IT Helpdesk) tốn nhiều thời gian**: Phải tạo thủ công từng tài khoản, cấp mật khẩu tạm thời hoặc gửi email kích hoạt dễ bị lạc vào hòm thư rác.
2. **Nhân viên gặp rào cản tiếp cận (Friction)**: Phải tạo mật khẩu mới, xác minh nhiều bước, dễ quên thông tin đăng nhập.
3. **Rủi ro an ninh & Kiểm soát quyền hạn (Security & Compliance)**: Nhân sự ngoài tổ chức có thể tự do đăng ký nếu không có tường lửa danh bạ; nhân viên mới vào có thể bị gán sai phòng ban/vai trò dẫn tới xem được các tài liệu mật không được phép.

### Mục tiêu giải quyết:
Thay thế hoàn toàn luồng truyền thống bằng cơ chế **"Pre-provisioned Directory + Google 1-Click JIT Sign-in"**:
1. HR/Admin upload danh sách nhân viên công ty (file Excel/CSV chuẩn gồm: Họ tên, Email, Mã NV, Mã Phòng ban, Role).
2. Nhân viên chỉ cần truy cập trang web, bấm **"Sign in with Google"** bằng email công ty.
3. Hệ thống đối soát email đã được Google xác thực với danh bạ định danh trước:
   - **Nếu khớp**: Tự động khởi tạo hồ sơ nhân viên (JIT Provisioning), gắn đúng Phòng ban (Department) và Quyền hạn (Role: USER/MANAGER), đánh dấu trạng thái đã kích hoạt (`status = CLAIMED`), cấp phát JWT token đưa vào trang hỏi đáp.
   - **Nếu không khớp**: Chặn ngay lập tức với lỗi `403 Forbidden` kèm giao diện thông báo thân thiện: *"Tài khoản của bạn chưa nằm trong danh bạ nhân sự của tổ chức. Vui lòng liên hệ HR."*

---

## 2. User Personas & Use Cases

| Persona | Mô tả vai trò | Mục tiêu chính khi dùng tính năng |
|---|---|---|
| **Admin / HR Manager** | Quản lý nhân sự & hệ thống | Tải lên danh sách nhân viên công ty (Excel/CSV), quản lý danh bạ chờ kích hoạt, xem lịch sử import. |
| **New Employee** | Nhân viên mới gia nhập | Đăng nhập tức thì chỉ với 1 click bằng tài khoản Google Workspace công ty mà không cần tạo mật khẩu. |

### Use Case Scenarios:
1. **UC-01: Admin Import Danh bạ Nhân sự (Pre-provisioning)**
   - **Actor:** Admin / HR
   - **Tiền điều kiện:** Đã đăng nhập vào trang `/admin/users` với quyền `ADMIN`.
   - **Luồng chính:** Admin chọn tải lên file `.xlsx`/`.csv` ➔ Hệ thống kiểm tra format và validate mã phòng ban ➔ Lưu danh sách vào trạng thái `PENDING_ACTIVATION`.
2. **UC-02: Nhân viên Đăng nhập 1-Click JIT Thành công**
   - **Actor:** Employee có trong danh bạ
   - **Luồng chính:** Nhân viên bấm "Sign in with Google" ➔ Xác thực với Google JWKS ➔ Khớp email trong roster ➔ Tự động tạo `UserProfile`, chuyển roster sang `CLAIMED` ➔ Cấp phát JWT token đưa vào giao diện Q&A.
3. **UC-03: Người ngoài tổ chức bị từ chối truy cập**
   - **Actor:** Người dùng có tài khoản Google nhưng không nằm trong danh bạ
   - **Luồng chính:** Đăng nhập Google ➔ Hệ thống đối soát không thấy email trong roster ➔ Trả về `403 Forbidden` kèm thông báo liên hệ HR.

---

## 3. Functional Requirements (FR)

- [ ] **FR-01 (Excel/CSV Parser & Validation):** Hỗ trợ import file danh bạ dạng Excel/CSV; validate cú pháp email, trùng lặp mã nhân viên, và tồn tại của mã phòng ban.
- [ ] **FR-02 (Roster Whitelist Management):** Quản lý bảng danh bạ tiền định danh với các trạng thái `PENDING`, `CLAIMED`, `REVOKED`.
- [ ] **FR-03 (Google Token JWKS Verification):** Xác thực chữ ký số của Google ID Token trực tiếp thông qua JWKS endpoint chính thức của Google.
- [ ] **FR-04 (1-Click JIT Claiming):** Khởi tạo `core.users` và `core.user_profiles` tự động ngay trong lần đăng nhập đầu tiên khi email khớp danh bạ.
- [ ] **FR-05 (Audit Logging):** Ghi nhận log sự kiện đăng ký mới và gán phòng ban vào `analytics.audit_logs`.

---

## 4. Non-Functional Requirements (NFR)

- **Security:** Token Google được kiểm tra chữ ký số JWKS, `aud` phải khớp Google Client ID của SOPilot; không cho phép bypass đăng ký.
- **Performance:** Thời gian xử lý JIT Onboarding < 800ms từ lúc nhận Google ID token đến khi phát JWT token.
- **Data Integrity:** Ràng buộc `UNIQUE(LOWER(email))` và `UNIQUE(employee_code)` trong database; giao dịch JIT phải mang tính nguyên tử (atomic transaction).

---

## 5. Scope & Boundary

| Trong phạm vi (In-Scope) | Nằm ngoài phạm vi (Out-of-Scope) |
|---|---|
| Upload file Excel/CSV danh bạ nhân sự | Đồng bộ trực tiếp Google Workspace Admin Directory API |
| Google OAuth 1-Click JIT Sign-in | Đăng nhập SSO qua SAML 2.0 / Okta / Azure AD (để dành Mốc sau) |
| Màn hình từ chối 403 Forbidden | Tự động gửi email thông báo HR khi có nhân viên bị từ chối |
