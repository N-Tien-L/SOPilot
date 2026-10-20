---
name: analyze-quality
description: Analyzing test failures, evaluating code coverage, diagnosing performance bottlenecks, auditing safety/security, and generating audit reports.
version: 1.0.0
author: SOPilot Team
---

# Analyze Quality Skill

This skill guides the AI Agent in performing systematic quality auditing, test failure triage, coverage gap identification, performance diagnosis, and authoring formal **Audit Reports**.

---

## When to use this skill
- When test suites fail and root cause needs to be diagnosed.
- After completing a milestone or feature to evaluate overall quality and test coverage.
- When performing pre-release sanity checks or security audits.
- When generating formal audit reports in `docs/04-reports/`.

---

## 1. Test Failure Triage & Root Cause Diagnosis

Khi gặp lỗi chạy test từ `run-test`:
1. **Phân loại bản chất lỗi:**
   - **Assertion Error (`expected X but got Y`)**: Logic code bị sai hoặc test expectation bị lỗi thời.
   - **NullPointerException / AttributeError**: Thiếu null check hoặc mock chưa stub đủ data.
   - **Database / Constraint Violation**: Vi phạm foreign key, unique constraint, hoặc transaction chưa rollback.
   - **Timeout / Hang**: Blocking I/O trong async event loop hoặc deadlock.
   - **Context Load Failure**: Thiếu bean, sai profile, sai env variable.
2. **Đối chiếu Stack Trace:**
   - Xác định chính xác class, file và dòng code gây crash.
   - Kiểm tra xem code mới có làm gãy hồi quy (regression) các module cũ hay không.
3. **Đề xuất giải pháp khắc phục (Fix Action):**
   - Sửa logic nghiệp vụ nếu hành vi hệ thống vi phạm PRD.
   - Cập nhật test nếu requirement nghiệp vụ đã thay đổi có chủ đích.

---

## 2. Phân tích Độ phủ Kiểm thử (Coverage & Gaps Analysis)

Rà soát mã nguồn đối chiếu với ma trận test cases:
- [ ] **Mã lỗi HTTP**: Mỗi endpoint đã có test cho 200, 400, 401, 403, 404, 409 chưa?
- [ ] **Data Boundary**: Đã test string rỗng, chuỗi quá dài, số âm, email sai định dạng chưa?
- [ ] **Transaction Rollback**: Khi service văng lỗi ở giữa chừng, database có được rollback nguyên vẹn không?
- [ ] **Event Delivery**: Các message RabbitMQ có được publish đúng routing key và định dạng JSON không?

---

## 3. Rà soát Vệ sinh Code & An toàn Bảo mật (Hygiene & Safety Audit)

Chạy kiểm tra tự động và rà soát thủ công:
1. **Debug Pollution Check:**
   - Quét không cho phép tồn tại `console.log`, `print()`, `System.out.println` trong code production.
   - Bắt buộc dùng structured logger (`LoggerFactory` trong Java, `structlog` trong Python, `Winston` trong NestJS).
2. **Secrets & Environment Leak:**
   - Đảm bảo không hardcode token, API key, mật khẩu.
   - Kiểm tra `.gitignore` không bị lộ `.env`.
3. **Kiến trúc Schema Isolation:**
   - Đảm bảo tuyệt đối không có truy vấn SQL chéo schema (`core` không query trực tiếp `knowledge`, v.v.).

---

## 4. Phân tích Hiệu năng & Rủi ro VPS (Performance Profiling)

- **JPA N+1 Problem:** Kiểm tra các quan hệ `@OneToMany`, `@ManyToMany` có bị fetch lặp vô tận không (khuyến nghị dùng `JOIN FETCH` hoặc `@EntityGraph`).
- **Async Blocking:** Kiểm tra trong FastAPI có hàm đồng bộ blocking nào (như `requests.get` thay vì `httpx.AsyncClient`) làm nghẽn Event Loop không.
- **Resource Limits:** Đảm bảo JVM parameters tuân thủ `-XX:+UseSerialGC -Xms96m -Xmx192m` để chạy tốt trên VPS 2GB-4GB RAM.

---

## 5. Xuất Báo cáo Kiểm định (Audit Report Generation)

Sau khi hoàn tất phân tích cho một milestone hoặc đợt kiểm thử lớn:
1. Sử dụng template tại `docs/04-reports/templates/audit-report-template.md`.
2. Tạo file tại:
   `docs/04-reports/AUDIT-<milestone/ticket-id>-<short-name>.md`
3. Điền đầy đủ ma trận test execution, tỷ lệ pass, coverage gaps, và kết luận nghiệm thu (Sign-off).
