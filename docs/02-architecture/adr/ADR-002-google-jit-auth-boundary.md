---
adr_id: ADR-002
title: "auth-service trực tiếp xác thực Google ID Token; Gateway làm Reverse Proxy"
status: accepted
date: 2026-09-25
deciders: ["Principal Architect", "Tech Lead"]
consulted_docs: ["docs/01-requirements/PRD-M1-jit-onboarding.md"]
---

# ADR-002: auth-service trực tiếp xác thực Google ID Token; Gateway làm Reverse Proxy

> **Trạng thái:** Accepted | **Ngày quyết định:** 2026-09-25 | **Người quyết định:** Principal Architect, Tech Lead

---

## 1. Bối cảnh & Vấn đề (Context & Problem Statement)
Khi nhân viên bấm "Sign in with Google", frontend nhận được Google ID Token. Câu hỏi đặt ra là: Tầng nào sẽ chịu trách nhiệm gọi Google JWKS để xác thực chữ ký số: API Gateway (NestJS) hay `auth-service` (Spring Boot)?

---

## 2. Tiêu chí Đánh giá (Decision Drivers)
- **Tập trung hóa logic Authentication:** Giữ toàn bộ quy trình phát hành token, refresh token và ghi nhận `core.login_history` tại một nơi duy nhất.
- **Tính độc lập của API Gateway:** Gateway cần giữ vai trò lightweight reverse proxy, không nên ôm logic nghiệp vụ token provider bên thứ ba.

---

## 3. Các phương án xem xét (Considered Options)

### Phương án A: Gateway xác thực Google Token rồi chuyển tiếp
- **Nhược điểm:** Gateway phải chứa Google Auth library, cấu hình client ID, và vẫn phải gọi sang `auth-service` để sinh JWT session nội bộ của SOPilot. Gây phân mảnh logic xác thực.

### Phương án B: auth-service trực tiếp xác thực Google ID Token (ĐƯỢC CHỌN)
- **Ưu điểm:**
  - Gateway chỉ đóng vai trò forward request `POST /api/v1/auth/google/verify` với decorator `@Public()`.
  - `auth-service` kiểm tra chữ ký JWKS, đối soát whitelist, tạo session và cấp JWT nội bộ trong cùng một transaction.

---

## 4. Quyết định & Biện luận (Decision Outcome & Rationale)
- **Quyết định:** Chọn **Phương án B**. `auth-service` là điểm duy nhất chịu trách nhiệm xác thực danh tính người dùng và phát hành JWT token nội bộ cho SOPilot.
