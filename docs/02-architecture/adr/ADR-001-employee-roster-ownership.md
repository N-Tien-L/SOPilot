---
adr_id: ADR-001
title: "Quyền sở hữu bảng core.employee_roster thuộc user-service"
status: accepted
date: 2026-09-25
deciders: ["Principal Architect", "Tech Lead"]
consulted_docs: ["docs/01-requirements/PRD-M1-jit-onboarding.md"]
---

# ADR-001: Quyền sở hữu bảng core.employee_roster thuộc user-service

> **Trạng thái:** Accepted | **Ngày quyết định:** 2026-09-25 | **Người quyết định:** Principal Architect, Tech Lead

---

## 1. Bối cảnh & Vấn đề (Context & Problem Statement)
Hệ thống triển khai cơ chế "Pre-provisioned Directory + Google 1-Click JIT Sign-in" cần một bảng lưu trữ danh bạ nhân sự (`core.employee_roster`) do Admin/HR tải lên. Câu hỏi kiến trúc đặt ra là: Service nào sẽ là chủ sở hữu (System of Record) của bảng này: `user-service` hay `auth-service`?

---

## 2. Tiêu chí Đánh giá (Decision Drivers)
- **Domain-Driven Design (DDD):** Đặt thực thể đúng bounded context nghiệp vụ.
- **Single Responsibility Principle (SRP):** Giữ cho `auth-service` tinh gọn, tập trung vào xác thực và phát hành token.
- **Tài nguyên & Dependencies:** Tránh tích hợp thư viện đọc file bảng tính (Apache POI) vào service xác thực bảo mật.

---

## 3. Các phương án xem xét (Considered Options)

### Phương án A: Giao cho `auth-service` quản lý
- **Ưu điểm:** `auth-service` có thể trực tiếp query kiểm tra whitelist email khi nhận Google token mà không cần gọi API nội bộ sang service khác.
- **Nhược điểm:** `auth-service` bị phình to (bloated), phải ôm logic parse Excel, cây phòng ban, phân trang danh bạ và validate chức vụ, vi phạm nghiêm trọng SRP.

### Phương án B: Giao toàn quyền cho `user-service` quản lý (ĐƯỢC CHỌN)
- **Ưu điểm:**
  - Danh bạ nhân sự gắn liền với aggregate `Department` và `UserProfile`.
  - Toàn bộ logic import Excel, filter phòng ban, validate mã nhân viên thuộc về miền quản trị nhân sự của `user-service`.
  - `auth-service` chỉ cần gọi một endpoint internal `/internal/v1/roster/claim` sang `user-service`.
- **Nhược điểm:** Thêm một lời gọi mạng nội bộ (Internal HTTP) từ `auth-service` sang `user-service` trong lần đăng nhập đầu tiên.

---

## 4. Quyết định & Biện luận (Decision Outcome & Rationale)
- **Quyết định:** Chọn **Phương án B** - `user-service` là **Owner (System of Record)** của `core.employee_roster`.
- **Biện luận:** Lời gọi nội bộ chỉ diễn ra duy nhất 1 lần khi nhân viên claim tài khoản JIT. Sau đó tài khoản đã được kích hoạt và nằm trong `core.users`, không ảnh hưởng tới hiệu năng các lần đăng nhập tiếp theo.

---

## 5. Hệ quả (Consequences)
- **Tích cực:** Tách biệt rõ ràng ranh giới nghiệp vụ; `auth-service` không bị phụ thuộc vào Apache POI.
- **Tiêu cực:** `auth-service` cần OpenFeign client gọi sang `user-service` kèm `INTERNAL_SERVICE_TOKEN` để bảo vệ API nội bộ.
