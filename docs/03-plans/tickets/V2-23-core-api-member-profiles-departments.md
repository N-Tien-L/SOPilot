---
id: V2-23
title: "core-api: hồ sơ thành viên, vòng đời tạm khóa và phòng ban phẳng"
type: feat
status: todo
created: 2026-10-19
updated: 2026-10-19
scope: user
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-11]
blocks: [V2-24, V2-15, V2-26]
branch: "feat/user-core-api-members-departments"
assignee: pair
---

# TICKET V2-23: Hồ sơ thành viên và phòng ban

## 1. Bối cảnh & Mục tiêu
PRD-V2 FR-04 (phần hồ sơ trong lời mời), FR-22, FR-23, FR-24 (P1), FR-20 (phần nhân sự); ADR-007 §4.1–4.3. Hồ sơ nằm trên membership, lời mời là trạng thái chờ; không có roster tạo trước.

## 2. Tiêu chí Hoàn thành
- [ ] Membership có `display_name`, `employee_code` (tùy chọn, unique trong workspace), `job_title` (tùy chọn), `department_id` (nullable), `status` `ACTIVE | SUSPENDED`; lời mời mang các trường này và áp dụng khi chấp nhận.
- [ ] Tạm khóa/mở khóa thành viên: refresh không cấp token cho workspace bị khóa; ADMIN không khóa được OWNER; luôn còn ≥ 1 OWNER `ACTIVE`.
- [ ] Rời/xóa khỏi workspace không xóa tài khoản toàn cục; workspace cá nhân không đòi hồ sơ hay phòng ban.
- [ ] Phòng ban phẳng theo workspace: tạo, đổi tên, `ARCHIVED`; tên unique trong workspace; không gán mới vào phòng ban `ARCHIVED`.
- [ ] Xóa phòng ban bị từ chối (409) khi còn thành viên, lời mời chờ hoặc tài liệu tham chiếu (FK `RESTRICT`).
- [ ] Access token có claim `wdept`; refresh đọc lại `status` và `department_id` (ADR-007 §4.5).
- [ ] Audit: đổi phòng ban, tạm khóa/mở khóa, sửa hồ sơ.
- [ ] (P1, có thể hoãn) Import CSV tạo lời mời hàng loạt, báo lỗi theo dòng (FR-24).

## 3. Hướng dẫn
- **File:** module members/departments trong `services/core-api/`; migration trong `infrastructure/db/migrations/`.
- Tham khảo, không port nguyên: `services/user-service` (`DepartmentService`, `EmployeeRoster*`), `frontend/web/app/admin/departments/`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Vòng đời membership; quy tắc OWNER; phòng ban archived; xóa bị chặn | `./mvnw test` |
| Integration | Mời kèm hồ sơ → chấp nhận → token có `wdept`; tạm khóa → refresh bị từ chối; chuyển phòng ban → token mới đổi `wdept` | `./mvnw verify` |
