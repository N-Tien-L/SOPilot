---
id: V2-36
title: "core-api: quyền ghi tài liệu theo publisher phòng ban và publisher workspace"
type: feat
status: todo
created: 2026-11-10
updated: 2026-11-10
author: "Owner"
scope: knowledge
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-23, V2-24]
blocks: [V2-16, V2-31, V2-33]
branch: "feat/knowledge-core-api-department-publishers"
assignee: pair
---

# TICKET V2-36: Publisher theo phòng ban và publisher toàn workspace

> **Phạm vi:** `knowledge` | **Độ phức tạp:** `L` | **Ưu tiên:** `P0`
> **Kế hoạch cha:** `PLAN-V2-SOPILOT-MVP` | **Nhánh làm việc:** `feat/knowledge-core-api-department-publishers`

## 1. Bối cảnh & Mục tiêu

Triển khai [ADR-009](../../02-architecture/adr/ADR-009-department-publishers.md) theo [TECH-V2-core-api §15](../../02-architecture/designs/TECH-V2-core-api.md): quyền ghi tài liệu chuyển từ OWNER/ADMIN sang publisher của phòng chủ quản (tài liệu `DEPARTMENTS`) hoặc publisher toàn workspace (tài liệu `WORKSPACE`). Quyền đọc, token và ai-service không đổi.

**Điều kiện bắt đầu:** đã đủ. ADR-009 `approved` 2026-11-10 (Q0–Q7 chốt ở ADR-009 §6); PRD-V2 FR-06, FR-25, FR-26, §8 mục 9 đã sửa theo (Q7).

## 2. Tiêu chí Hoàn thành

**Schema (migration `core/V008`, skill `flyway-migration`)**
- [ ] `core.department_publishers`, `core.workspace_publishers`, `core.documents.owner_department_id` đúng TECH §15.2: FK hai cột tới `departments` và `memberships`, `fk_documents_owner_in_scope` hoãn tới commit, CHECK `WORKSPACE ⇔ owner_department_id IS NULL`; RLS `FORCE` và grant như bảng tenant khác.
- [ ] Backfill theo quyết định Q6 và ADR-009 §4.4; `core.create_personal_workspace` và `POST /workspaces` gán người tạo làm publisher workspace. `./scripts/check-migrations.ps1` xanh; không sửa migration đã commit.

**Quyền ghi (core-api)**
- [ ] `DocumentWritePolicy` là điểm kiểm tra duy nhất cho 7 endpoint ghi tài liệu (TECH §15.1); `DocumentService` không còn `requireManager()` ngoài `deleteAll`.
- [ ] Publisher đúng: publisher phòng D tải lên, tải bản thay thế, thử lại, sửa metadata, áp dụng gợi ý, đổi danh sách phòng (giữ D) và xóa tài liệu chủ quản D; publisher workspace làm như vậy với tài liệu `WORKSPACE`.
- [ ] Publisher sai: publisher phòng D2 ghi tài liệu chủ quản D mà D2 đọc được (có trong `document_departments`) → `403 NOT_PUBLISHER`; tài liệu D2 không đọc được → `404`, không lộ tên. Publisher phòng ghi tài liệu `WORKSPACE` → `403`.
- [ ] ADMIN bị từ chối: ADMIN không phải publisher nhận `403` ở cả 7 endpoint ghi; vẫn tạo/sửa/xóa phòng ban, category, thành viên như trước; vẫn đọc mọi tài liệu.
- [ ] OWNER không phải publisher nhận `403` ở tải lên, tải bản thay thế, thử lại, sửa metadata, áp dụng gợi ý, `PUT /visibility` (ADR-009 quyết định 8, Q4).
- [ ] OWNER thu hồi: OWNER `ACTIVE` xóa được mọi tài liệu kể cả của phòng chưa có publisher; audit `actingAs = OWNER`. OWNER vừa bị hạ xuống ADMIN (token cũ còn hạn) → `403` (vai trò đọc từ DB).
- [ ] OWNER gán lại: chỉ OWNER gọi được API §15.4 (ADMIN, MEMBER → `403`); sau khi OWNER đổi publisher phòng D từ A sang B, request ghi kế tiếp của A → `403`, của B → thành công, không cần refresh token. Gán người khác phòng → `409 PUBLISHER_NOT_IN_DEPARTMENT`; người `SUSPENDED` → `409 MEMBER_NOT_ACTIVE`; phòng `ARCHIVED` → `409 DEPARTMENT_ARCHIVED`.
- [ ] Rời phòng: đổi `departmentId` của publisher xóa dòng publisher trong cùng transaction và ghi audit; phòng D không còn publisher thì mọi tạo mới với chủ quản D → `403`. Xóa thành viên hoặc rời workspace cascade dòng publisher.
- [ ] Phiên bản `READY` không bị ảnh hưởng khi đổi hoặc gỡ publisher (Q3): `current_version_id`, trạng thái, `rag.document_access` không đổi; tài liệu vẫn hỏi đáp được.
- [ ] Chuyển trách nhiệm (Q5): `PUT /documents/{id}/ownership` chỉ OWNER (ADMIN, publisher → `403`). Ba ca `DEPARTMENTS → WORKSPACE`, `WORKSPACE → DEPARTMENTS`, đổi phòng chủ quản: người ghi đổi ở request kế tiếp; `current_version_id`, phiên bản, chunk giữ nguyên; `rag.document_access` cập nhật qua `ACCESS_UPDATED`; audit `DOCUMENT_OWNERSHIP_CHANGED`. Phòng đích `ARCHIVED` → `409`; phòng chủ quản ngoài `departmentIds` → `400`.
- [ ] Publisher gọi `PUT /visibility` đổi loại hoặc bỏ phòng chủ quản → `409 OWNERSHIP_CHANGE_REQUIRES_OWNER`; DB chặn bỏ phòng chủ quản lúc commit (`fk_documents_owner_in_scope`).
- [ ] Đổi publisher song song với upload không cho người cũ ghi sau khi lệnh đổi đã commit (khóa `FOR SHARE`/`FOR UPDATE` trên dòng publisher); có integration test.
- [ ] `GET /api/v1/publishers` cho mọi thành viên `ACTIVE`, không trả email; `GET /members/me` có `publisherOf`. `GET /documents/{id}/versions` trả `uploadedBy`, `uploadedAt` (từ `uploaded_by`, `created_at`).
- [ ] Audit `PUBLISHER_ASSIGNED`, `PUBLISHER_UNASSIGNED`; `DOCUMENT_*` có `ownerDepartmentId`, `actingAs`; `DOCUMENT_OWNERSHIP_CHANGED` (TECH §15.5).

**Cách ly đọc (FR-29, FR-19), hồi quy**
- [ ] Ma trận đọc ADR-007 §4.4 giữ nguyên với dữ liệu có publisher: MEMBER ngoài phòng vẫn `404` ở danh sách, chi tiết, URL tải; publisher không đọc thêm tài liệu ngoài phòng của mình; OWNER/ADMIN vẫn đọc mọi tài liệu.
- [ ] Payload `INGEST_REQUESTED`, `ACCESS_UPDATED` không đổi (không có `owner_department_id`); ai-service không phải sửa.
- [ ] `tests/tenant-isolation` xanh với hai bảng mới (RLS FORCE, negative control đỏ khi tắt RLS); `TenantIsolation*IT` xanh.

**Tài liệu**
- [ ] Cập nhật `.agent/context/authorization/v2-core-identity.md`, `.agent/context/database/tables/core.md`, `services/core-api/README.md` cùng thay đổi; sơ đồ ERD chuyển phần đề xuất sang thật.
- [ ] Chỗ code lệch TECH §15 ghi thành bảng ghi chú triển khai trong TECH-V2-core-api.

## 3. Hướng dẫn

- Thứ tự: migration → `DocumentWritePolicy` + thay 7 chỗ `requireManager()` → API publisher và `PUT /ownership` → `MemberService` (xóa dòng khi đổi phòng) → audit → test → docs.
- Đọc publisher và membership từ DB trong `TenantTx` của thao tác ghi, lọc `workspace_id` tường minh (constraint 4 của `CLAUDE.md`); không đưa publisher vào token.
- `DocumentView` dùng chung truy vấn publisher (không khóa) để quyết định trả trường quản trị.
- Không đổi `services/ai-service`, `rag.*`, contract §8.

## 4. Kiểm thử

| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Bảng quyền ghi (vai trò × publisher × endpoint, gồm `PUT /ownership`), thứ tự `404`/`403`, `requireCanCreate`, `requireCanDelete`, `requireCanTransfer` | `./scripts/run-tests.ps1 -Scope core-api -Type unit` |
| Integration | Các tiêu chí "Quyền ghi" và hồi quy đọc FR-29, khóa song song, FK hoãn | `./scripts/run-tests.ps1 -Scope core-api -Type all` (Docker) |
| Cách ly | Bảng mới trong bộ tenant isolation | `cd tests/tenant-isolation; uv run pytest -v` (Docker) |
| Migration | Đặt tên, không sửa file cũ, không DDL phá hủy | `./scripts/check-migrations.ps1` |

## 5. Tóm tắt các File thay đổi (dự kiến)

| Đường dẫn | Hành động |
|---|:---:|
| `infrastructure/db/migrations/core/V008__department_publishers.sql` | CREATE |
| `services/core-api/src/main/java/com/sopilot/core/document/DocumentWritePolicy.java` | CREATE |
| `services/core-api/src/main/java/com/sopilot/core/document/DocumentService.java`, `DocumentView.java`, `DocumentController.java` | MODIFY |
| `services/core-api/src/main/java/com/sopilot/core/department/` (API gán publisher), `member/MemberService.java` | MODIFY |
| `services/core-api/src/test/java/...` (unit, IT) | CREATE/MODIFY |
| `.agent/context/authorization/v2-core-identity.md`, `.agent/context/database/tables/core.md`, `services/core-api/README.md` | MODIFY |

## 6. Lệnh Kiểm tra Nhanh

```powershell
./scripts/validate-build.ps1 -Scope core
./scripts/check-migrations.ps1
./scripts/pre-commit-check.ps1
```
