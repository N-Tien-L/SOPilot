---
id: V2-23
title: "core-api: hồ sơ thành viên, vòng đời tạm khóa và phòng ban phẳng"
type: feat
status: done
created: 2026-10-19
updated: 2026-11-09
author: "Owner"
scope: user
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-11]
blocks: [V2-24, V2-26, V2-33, V2-36]
branch: "feat/user-core-api-members-departments"
assignee: pair
---

# TICKET V2-23: Hồ sơ thành viên và phòng ban

## 1. Bối cảnh & Mục tiêu
PRD-V2 FR-04 (phần hồ sơ trong lời mời), FR-22, FR-23, FR-24 (P1), FR-20 (phần nhân sự); ADR-007 §4.1–4.3. Hồ sơ nằm trên membership, lời mời là trạng thái chờ; không có roster tạo trước.

## 2. Tiêu chí Hoàn thành
- [x] Membership có `display_name`, `employee_code` (tùy chọn, unique trong workspace), `job_title` (tùy chọn), `department_id` (nullable), `status` `ACTIVE | SUSPENDED`; lời mời mang các trường này và áp dụng khi chấp nhận. (cột hồ sơ có và được kiểm thử; bảng `invitations` mang các trường hồ sơ; endpoint mời/chấp nhận và việc áp hồ sơ khi chấp nhận chuyển sang V2-30)
- [x] Tạm khóa/mở khóa thành viên: refresh không cấp token cho workspace bị khóa; ADMIN không khóa được OWNER; luôn còn ≥ 1 OWNER `ACTIVE`. (quy tắc OWNER, tạm khóa, mở khóa xong; `SessionTokenService.reissue` trả `403 MEMBERSHIP_SUSPENDED`; endpoint refresh và thu hồi refresh token khi tạm khóa/xóa/rời đã làm ở V2-29, `MemberService` gọi `RefreshTokenService.revokeForMembership`)
- [x] Rời/xóa khỏi workspace không xóa tài khoản toàn cục; workspace cá nhân không đòi hồ sơ hay phòng ban.
- [x] Phòng ban phẳng theo workspace: tạo, đổi tên, `ARCHIVED`; tên unique trong workspace; không gán mới vào phòng ban `ARCHIVED`.
- [x] Xóa phòng ban bị từ chối (409) khi còn thành viên, lời mời chờ hoặc tài liệu tham chiếu (FK `RESTRICT`). (lời mời chờ chặn bằng kiểm tra ở service; FK của `invitations` là `SET NULL` thay vì `RESTRICT` để lời mời đã dùng/thu hồi không ghim phòng ban)
- [x] Access token có claim `wdept`; refresh đọc lại `status` và `department_id` (ADR-007 §4.5). (token cấp lại đọc `status`/`department_id` từ DB; chưa có endpoint refresh, V2-29)
- [x] Audit: đổi phòng ban, tạm khóa/mở khóa, sửa hồ sơ.
- [x] (P1, có thể hoãn) Import CSV tạo lời mời hàng loạt, báo lỗi theo dòng (FR-24). (owner hoãn 2026-11-09, chuyển sang V2-30 dưới dạng tiêu chí P1)

## 3. Hướng dẫn
- **File:** module members/departments trong `services/core-api/`; migration trong `infrastructure/db/migrations/`.
- Tham khảo, không port nguyên: `services/user-service` (`DepartmentService`, `EmployeeRoster*`), `frontend/web/app/admin/departments/`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Vòng đời membership; quy tắc OWNER; phòng ban archived; xóa bị chặn | `./mvnw test` |
| Integration | Mời kèm hồ sơ → chấp nhận → token có `wdept`; tạm khóa → refresh bị từ chối; chuyển phòng ban → token mới đổi `wdept` | `./mvnw verify` |

## 5. Bằng chứng triển khai (2026-11-06, nghiệm thu 2026-11-09)

Owner nghiệm thu 2026-11-09, chuyển `done`. Code ở commit `4113f63`, merge vào `develop` qua PR #5. Phần phụ thuộc endpoint chưa có do V2-29 làm (refresh, thu hồi token khi tạm khóa) hoặc đã thành tiêu chí của V2-30 (lời mời kèm hồ sơ, import CSV P1). Chỗ lệch TECH (FK `invitations.department_id` `SET NULL`, `PATCH /members` chưa nhận `role`) được duyệt ở TECH-V2-core-api §13. Kiểm lại khi nghiệm thu: `DepartmentMemberIT` 12 xanh trong `./mvnw -B verify` (73 unit + 78 integration, 0 lỗi); đọc lại `MemberService`, `MemberRepository`, `DepartmentService`, `DepartmentRepository`: mọi câu lệnh lọc `workspace_id`, kiểm OWNER cuối khóa dòng OWNER trước khi đổi.

- **Code:** `services/core-api/src/main/java/com/sopilot/core/{department,member}/`, `identity/SessionTokenService.java`; migration `V004__departments_and_member_profiles.sql` (`departments`, `memberships.employee_code/job_title` + FK hai cột, `invitations`).
- **Lệnh:** `./mvnw verify` -> 0 lỗi; riêng V2-23: `DepartmentMemberIT` 12 test trên Postgres thật với role `sopilot_core_app`: tên phòng ban unique theo workspace (không phân biệt hoa thường, trùng tên ở workspace khác được); lưu trữ phòng ban; xóa bị `409 DEPARTMENT_IN_USE` khi còn thành viên, lời mời chờ hoặc tài liệu (FK `RESTRICT` kiểm riêng), lời mời đã thu hồi thì không ghim; không gán vào phòng ban đã lưu trữ; `employee_code` unique; đổi phòng ban -> token cấp lại mang `wdept` mới, token đang cầm giữ giá trị cũ; tạm khóa -> `403 MEMBERSHIP_SUSPENDED`, mở khóa -> cấp lại được; xóa khỏi workspace -> `401 MEMBERSHIP_LOST`, tài khoản toàn cục còn; ADMIN không khóa/xóa OWNER; OWNER cuối cùng không tự khóa/xóa/rời (`LAST_OWNER`); workspace cá nhân không rời được, không đòi hồ sơ; MEMBER chỉ thấy hồ sơ của mình; audit `MEMBER_DEPARTMENT_CHANGED`, `MEMBER_PROFILE_UPDATED`, `MEMBER_SUSPENDED`.
- **Lệch/ghi chú:** `PATCH /members/{userId}` chưa nhận `role` (đổi role và quy tắc OWNER đầy đủ là V2-30); body `PATCH` kiểu map nên `null` tường minh xóa trường tùy chọn.
- **Chưa làm:** import CSV (P1); nhận lời mời kèm hồ sơ; thu hồi refresh token khi tạm khóa; frontend (V2-33).
- **Docs:** như V2-12.
