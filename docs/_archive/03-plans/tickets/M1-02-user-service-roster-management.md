---
id: M1-02
title: "User-Service: Roster Management & Internal Claim Engine"
type: feat
status: done
created: 2026-09-25
updated: 2026-09-25
author: "Owner"
scope: user
priority: P0
size: L
parent_plan: PLAN-M1-JIT-ONBOARDING
depends_on: [M1-01]
blocks: [M1-03, M1-04]
branch: "feat/m1-02-user-roster-service"
assignee: pair
---

## Context
`user-service` là System of Record cho danh bạ nhân sự. Ticket này xây dựng entity, parser Excel Apache POI streaming, các API quản lý danh bạ (import, export template, search, update) và internal endpoint `POST /internal/v1/roster/claim` phục vụ JIT onboarding.

## Acceptance Criteria
- [x] JPA Entity `EmployeeRoster` và Repository `EmployeeRosterRepository` mapping chính xác với `core.employee_roster`.
- [x] Tích hợp Apache POI `poi-ooxml` xử lý file Excel streaming an toàn bộ nhớ.
- [x] API `GET /api/v1/users/roster/template` xuất file `.xlsx` 2 sheet (Form nhập & Danh mục phòng ban).
- [x] API `POST /api/v1/users/roster/import` xử lý multipart file, validate mã NV, email, dept code, role; trả về chi tiết dòng thành công/lỗi.
- [x] API `GET /api/v1/users/roster` hỗ trợ phân trang, tìm kiếm keyword, filter theo `departmentId` và `status`.
- [x] Internal API `POST /internal/v1/roster/claim` tạo User + UserProfile, gán Department, cập nhật roster `is_claimed=true` trong 1 Transaction, bắn sự kiện RabbitMQ `UserRegisteredEvent` và `UserAssignedToDepartmentEvent`.

## Implementation Guide
1. **Thêm dependency Apache POI vào pom.xml**
   - **File:** `services/user-service/pom.xml`
   - **Action:** MODIFY
   - **Details:** Thêm `org.apache.poi:poi-ooxml:5.2.5`.

2. **Tạo Entity & DTOs**
   - **Files:**
     - `services/user-service/src/main/java/com/poliwise/user/entity/EmployeeRoster.java`
     - `services/user-service/src/main/java/com/poliwise/user/enums/RosterStatus.java`
     - `services/user-service/src/main/java/com/poliwise/user/dto/roster/RosterImportResponse.java`
     - `services/user-service/src/main/java/com/poliwise/user/dto/roster/RosterRowError.java`
     - `services/user-service/src/main/java/com/poliwise/user/dto/roster/ClaimRosterRequest.java`
     - `services/user-service/src/main/java/com/poliwise/user/dto/roster/ClaimRosterResponse.java`
   - **Action:** CREATE

3. **Xây dựng Repository & Service**
   - **Files:**
     - `services/user-service/src/main/java/com/poliwise/user/repository/EmployeeRosterRepository.java`
     - `services/user-service/src/main/java/com/poliwise/user/service/RosterExcelService.java`
     - `services/user-service/src/main/java/com/poliwise/user/service/EmployeeRosterService.java`
   - **Action:** CREATE
   - **Details:** Xử lý logic import streaming, xuất template 2 sheet, claim logic và event emission.

4. **Tạo Controllers**
   - **Files:**
     - `services/user-service/src/main/java/com/poliwise/user/controller/EmployeeRosterController.java` (Admin APIs)
     - `services/user-service/src/main/java/com/poliwise/user/controller/InternalRosterController.java` (Internal API)
   - **Action:** CREATE

## Test Requirements
| Type | What to Test | Framework |
|---|---|---|
| Unit | RosterExcelService parse file mẫu thành công và bắt đúng lỗi dòng sai dept code | JUnit 5 + Mockito |
| Unit | Internal claim: email không tồn tại trả về 403 `ROSTER_NOT_FOUND` | JUnit 5 |
| Integration | Flow import Excel -> Gọi API claim tạo User -> Check User & UserProfile trong DB | SpringBootTest |

## Files Changed Summary
| File | Action | Est. Lines |
|---|---|---|
| `services/user-service/pom.xml` | MODIFY | +10 |
| `services/user-service/.../EmployeeRoster.java` | CREATE | +80 |
| `services/user-service/.../RosterExcelService.java` | CREATE | +150 |
| `services/user-service/.../EmployeeRosterService.java` | CREATE | +180 |
| `services/user-service/.../EmployeeRosterController.java` | CREATE | +100 |
| `services/user-service/.../InternalRosterController.java` | CREATE | +60 |
