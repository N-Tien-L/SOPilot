---
ticket_id: "[PLAN_ID]-[XX]"
title: "[Mô tả ngắn gọn đầu việc cần làm]"
type: feat # feat | fix | chore | refactor | docs | test
scope: user # auth | user | knowledge | metadata | feedback | ai-qa | ingestion | gateway | web | infra
priority: P0 # P0 | P1 | P2 | P3
size: M # S (<2h) | M (2-4h) | L (4-8h) | XL (>8h)
status: todo # todo | in-progress | review | done
parent_plan: PLAN-XXX
depends_on: [] # Danh sách ticket_id bắt buộc hoàn thành trước
blocks: [] # Danh sách ticket_id bị chặn bởi ticket này
branch: "{type}/{scope}-{short-name}"
assignee: pair
---

# TICKET [TICKET_ID]: [TIÊU ĐỀ]

> **Phạm vi (Scope):** `[scope]` | **Độ phức tạp:** `[size]` | **Ưu tiên:** `[priority]`
> **Kế hoạch cha:** `[parent_plan]` | **Nhánh làm việc:** `[branch]`

---

## 1. Bối cảnh & Mục tiêu (Context & Goal)
Mô tả cụ thể nhiệm vụ của ticket này trong bức tranh tổng thể của milestone. Nêu rõ mục tiêu kỹ thuật cần đạt được.

---

## 2. Tiêu chí Hoàn thành (Acceptance Criteria)
Checklist nhị phân (Binary Pass/Fail) bắt buộc phải thỏa mãn:
- [ ] Tiêu chí chức năng 1...
- [ ] Tiêu chí chức năng 2...
- [ ] Không làm gãy API contract hiện tại.
- [ ] Unit/Integration tests cho phần code mới đạt PASS.

---

## 3. Hướng dẫn Triển khai Từng bước (Implementation Guide)

### Bước 1: [Tên bước 1]
- **File:** `path/to/target/file`
- **Action:** `CREATE` | `MODIFY` | `DELETE`
- **Chi tiết thực hiện:**
  - Mô tả cụ thể logic cần viết, method/class cần tạo.

### Bước 2: [Tên bước 2]
- **File:** `path/to/target/file`
- **Action:** `CREATE` | `MODIFY` | `DELETE`
- **Chi tiết thực hiện:**
  - ...

---

## 4. Yêu cầu Kiểm thử (Test Requirements)

| Loại Test | Nội dung cần kiểm thử | Framework / Công cụ | Lệnh thực thi |
|---|---|---|---|
| **Unit Test** | Test logic nghiệp vụ, validation | JUnit 5 / Pytest / Jest | `./scripts/run-tests.ps1 -Scope [scope] -Type unit` |
| **Integration Test** | Test tương tác DB / Mockito / Supertest | Spring / Test Client | `./scripts/run-tests.ps1 -Scope [scope] -Type integration` |

---

## 5. Tóm tắt các File thay đổi (Files Changed Summary)

| Đường dẫn File | Hành động | Ước lượng Lines |
|---|:---:|:---:|
| `services/.../FooService.java` | MODIFY | +40 / -5 |
| `services/.../FooServiceTest.java` | CREATE | +80 |

---

## 6. Lệnh Kiểm tra Nhanh (Pre-check Command)
```powershell
./scripts/validate-build.ps1 -Scope [scope]
./scripts/check-conventions.ps1 -Scope [scope]
```
