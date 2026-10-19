---
id: PRD-XXX
title: "[Tên tính năng / Nghiệp vụ]"
status: draft # draft | approved | superseded
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: "[Tên tác giả / Agent Role]"
milestone: "[Milestone X]"
priority: P0 # P0 (Blocker) | P1 (High) | P2 (Medium) | P3 (Low)
---

# YÊU CẦU NGHIỆP VỤ & ĐẶC TẢ TÍNH NĂNG (PRD)

> **Mã tài liệu:** `PRD-XXX` | **Milestone:** `[Milestone X]` | **Trạng thái:** `[status]`

---

## 1. Problem Statement & Motivation
- **Bối cảnh & Điểm nghẽn hiện tại:**
  - Mô tả vấn đề mà người dùng hoặc hệ thống đang gặp phải.
  - Tác động tiêu cực nếu không giải quyết.
- **Mục tiêu mong đợi:**
  - Kết quả cụ thể cần đạt được sau khi tính năng hoàn thành.

---

## 2. User Personas & Use Cases
| Persona | Mô tả vai trò | Mục tiêu chính khi dùng tính năng |
|---|---|---|
| **Employee** | Nhân viên nội bộ | ... |
| **Manager** | Trưởng phòng ban | ... |
| **Admin / HR** | Quản trị viên hệ thống / Nhân sự | ... |

### Use Case Scenarios:
1. **UC-01: [Tên kịch bản 1]**
   - **Actor:** Employee
   - **Tiền điều kiện:** ...
   - **Luồng chính:** 1 -> 2 -> 3
   - **Hậu điều kiện:** ...
2. **UC-02: [Tên kịch bản 2]**
   - ...

---

## 3. Functional Requirements (FR)
- [ ] **FR-01: [Tên yêu cầu 1]**
  - Mô tả chi tiết hành vi hệ thống.
  - Quy tắc nghiệp vụ (Business Rules).
- [ ] **FR-02: [Tên yêu cầu 2]**
  - ...

---

## 4. Non-Functional Requirements (NFR)
- **Security & Authorization:** Phân quyền theo RBAC (`USER`, `MANAGER`, `ADMIN`), kiểm tra dữ liệu nhạy cảm.
- **Performance / SLA:** Thời gian phản hồi API (vd: < 500ms), streaming latency (vd: < 1.5s).
- **Data Integrity:** Tính toàn vẹn dữ liệu, idempotency, unique constraints.
- **Audit & Logging:** Các sự kiện cần ghi log tuân thủ vào `analytics.audit_logs`.

---

## 5. Scope & Boundary (In-Scope vs Out-of-Scope)
| Hạng mục | Trong phạm vi (In-Scope) | Nằm ngoài phạm vi (Out-of-Scope) |
|---|---|---|
| Nghiệp vụ | Những gì bắt buộc phải hoàn thành | Những gì để dành cho phase sau |
| Giao diện | Màn hình, modal nào cần dựng | Màn hình nâng cao chưa cần |
| Tích hợp | Tích hợp bên thứ 3 nào | Tích hợp chưa làm |

---

## 6. Acceptance Criteria tổng quan (DoD - Definition of Done)
- [ ] Tất cả Use Cases chính chạy thành công trên giao diện và API.
- [ ] Tích hợp kiểm tra quyền RBAC không bị hở quyền (Access Control Check passed).
- [ ] Tài liệu kỹ thuật tương ứng (`TECH-XXX`) đã được phê duyệt.
