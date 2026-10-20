---
id: ADR-XXX
title: "[Tên quyết định kiến trúc]"
status: draft # draft | approved | superseded
created: YYYY-MM-DD
updated: YYYY-MM-DD
refs: [docs/01-requirements/PRD-XXX.md]
deciders: ["Principal Architect", "Tech Lead"]
amends: [] # ADR bị điều chỉnh một phần, vẫn giữ approved
supersedes: [] # ADR bị thay thế hoàn toàn (ADR đó chuyển superseded)
superseded_by: "" # ADR-ZZZ nếu có
---

# ADR-XXX: [Tiêu đề quyết định kiến trúc]

> **Trạng thái:** `[status]` | **Ngày quyết định:** `YYYY-MM-DD` | **Tác giả:** `[deciders]`

---

## 1. Bối cảnh & Vấn đề cần quyết định (Context & Problem Statement)
Mô tả vấn đề kỹ thuật hoặc bài toán kiến trúc phát sinh cần đưa ra quyết định dứt khoát.
- Tại sao phải đưa ra quyết định này?
- Các ràng buộc về hệ thống (ví dụ: tài nguyên VPS thấp 2-4GB RAM, mô hình Microservice, phân vùng Schema PostgreSQL).

---

## 2. Tiêu chí đánh giá (Decision Drivers)
1. **Tuân thủ DDD & Schema Ownership:** Không phá vỡ ranh giới dữ liệu giữa các microservices.
2. **Hiệu năng & Tài nguyên:** Không làm phình to service không cần thiết.
3. **Bảo mật & Kiểm soát truy cập:** Đảm bảo xác thực chặt chẽ, không tin tưởng client mù quáng.
4. **Khả năng kiểm thử & Độc lập:** Dễ dàng viết Unit test và Mocking.

---

## 3. Các phương án xem xét (Considered Options)

### Phương án 1: [Tên phương án 1]
- **Mô tả:** ...
- **Ưu điểm (+):** ...
- **Nhược điểm (-):** ...

### Phương án 2: [Tên phương án 2]
- **Mô tả:** ...
- **Ưu điểm (+):** ...
- **Nhược điểm (-):** ...

---

## 4. Quyết định & Biện luận (Decision Outcome & Rationale)
- **Phương án được chọn:** **[Phương án X]**
- **Lý do lựa chọn (Biện luận kỹ thuật):**
  - Giải thích cụ thể lý do tại sao phương án này vượt trội hơn các phương án còn lại trong bối cảnh hệ thống SOPilot.

---

## 5. Tác động & Hệ quả (Consequences)
- **Tác động tích cực (Pros):**
  - ...
- **Hạn chế / Rủi ro chấp nhận đánh đổi (Cons / Trade-offs):**
  - ...
- **Hành động tiếp theo (Follow-up Actions):**
  - Cập nhật tài liệu thiết kế `TECH-XXX`.
  - Phân rã ticket thực thi trong `PLAN-XXX`.
