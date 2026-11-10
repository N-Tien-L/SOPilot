---
id: ADR-007
title: "V2: hồ sơ thành viên theo workspace, phòng ban phẳng và quyền đọc tài liệu theo phòng ban"
status: approved
created: 2026-10-19
updated: 2026-11-09
author: "Owner"
refs:
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/02-architecture/adr/ADR-005-workspace-tenancy-and-google-jit.md
  - docs/02-architecture/adr/ADR-004-two-service-architecture.md
deciders: ["Owner"]
amends: [ADR-005]
supersedes: []
superseded_by: ""
---

# ADR-007: Hồ sơ thành viên, phòng ban phẳng và quyền tài liệu theo phòng ban

> **Trạng thái:** `approved` (2026-10-20) | **Ngày đề xuất:** `2026-10-19` | **Người quyết định:** `Owner`
>
> ADR này điều chỉnh ADR-005: thay đánh đổi "mất phòng ban và phân quyền theo phòng ban trong V2" bằng mô hình phòng ban phẳng trong workspace. Workspace, membership, RLS và token theo workspace của ADR-005 giữ nguyên.
>
> **Được điều chỉnh bởi:** [ADR-009](ADR-009-department-publishers.md) (`approved`, 2026-11-10) chuyển quyền ghi tài liệu của §4.4 từ OWNER/ADMIN sang publisher theo phòng ban và publisher toàn workspace; quyền đọc không đổi.

---

## 1. Bối cảnh & vấn đề cần quyết định
- Owner yêu cầu (2026-10-19) giữ quản lý nhân sự, phòng ban và phân quyền tài liệu theo phòng ban cho doanh nghiệp nhỏ, nhưng không bê nguyên roster HR cũ và không làm phiền người dùng cá nhân.
- Code hiện tại (kiểm tra 2026-10-19):
  - `core.departments` là toàn cục, có `parent_id` (cây); `DepartmentService.deleteDepartment` chỉ deactivate nhưng `DepartmentController` không có endpoint xóa.
  - `core.employee_roster` tạo hồ sơ trước khi đăng nhập, email unique toàn cục, mỗi người đúng một `department_id`.
  - `metadata.document_access_rules` là ACL tổng quát (`ROLE | DEPARTMENT | USER`), `target_department_id ... ON DELETE CASCADE`: xóa cứng phòng ban sẽ xóa luật, có thể làm tài liệu giới hạn mất giới hạn.
  - `knowledge.chunks` sao chép `allowed_roles/allowed_departments/allowed_users/access_level` lúc ingest; không có đường nào cập nhật lại khi luật đổi. Mặc định cột `access_level` là `'PUBLIC'`.
  - `ai-qa-service` `chunk_repo.py` lọc theo `access_level = 'PUBLIC' OR allowed_* && ...` và chèn `department_id` vào SQL bằng f-string (để cộng điểm).
- Phần tái sử dụng được: ý tưởng một phòng ban mỗi người, UI quản lý phòng ban/category/tag của `frontend/web/app/admin/`, kiểm tra `access-check` của metadata-service làm tham chiếu. Không port nguyên schema.

## 2. Tiêu chí đánh giá
1. Người dùng cá nhân không thấy và không phải điền gì liên quan tới nhân sự hay phòng ban.
2. Quyền đọc đúng ở mọi đường dữ liệu, kể cả trước khi vào context LLM.
3. Thay đổi phòng ban hay phạm vi tài liệu không bao giờ vô tình mở rộng quyền (fail closed).
4. ai-service không phải gọi core-api ở mỗi request (giữ tiêu chí 4 của ADR-005).
5. Ít bảng và ít khái niệm nhất có thể.

## 3. Các phương án xem xét

### Hồ sơ nhân sự
- **A. Roster tạo trước khi đăng nhập (như cũ).** (−) Hai bảng song song với lời mời; email unique toàn cục xung đột với đa workspace.
- **B. Hồ sơ nằm trên membership, lời mời mang hồ sơ ban đầu (chọn).** Lời mời chính là trạng thái "chờ tham gia". Khi chấp nhận, hồ sơ được chép sang membership.

### Số phòng ban mỗi thành viên
- **Một (chọn).** Khớp mô hình cũ và token nhỏ; tài liệu vẫn giới hạn được cho nhiều phòng ban.
- **Nhiều.** (+) Linh hoạt cho người kiêm nhiệm. (−) Thêm bảng nối, token dài hơn, UI phức tạp. Để P1.

### Mô hình quyền tài liệu
- **ACL tổng quát ROLE/DEPARTMENT/USER (như cũ).** (−) Khó test đầy đủ, dễ sai.
- **Hai phạm vi `WORKSPACE | DEPARTMENTS` + role (chọn).**

### Nơi đánh giá quyền khi truy xuất
- **Sao chép quyền vào từng chunk.** (−) Đổi quyền phải ghi lại toàn bộ chunk; dễ lệch như code cũ.
- **Bảng quyền theo tài liệu trong ai-service, join khi truy xuất (chọn).** Một dòng mỗi tài liệu; đổi quyền là cập nhật một dòng.

## 4. Quyết định & biện luận

### 4.1 Mô hình dữ liệu (chi tiết DDL trong TECH-V2)
- `core.users`: tài khoản toàn cục (ADR-005), không có phòng ban.
- `core.memberships`: thêm `display_name`, `employee_code` (tùy chọn, unique theo `(workspace_id, employee_code)` khi có), `job_title` (tùy chọn), `department_id` (nullable), `status` (`ACTIVE | SUSPENDED`), `suspended_at`.
- `core.invitations`: thêm `display_name`, `department_id`, `employee_code`, `job_title`.
- `core.departments(workspace_id, name, status ACTIVE|ARCHIVED)`, tên unique trong workspace, không có `parent_id`. FK từ membership và từ phạm vi tài liệu dùng `ON DELETE RESTRICT`.
- `core.document_departments(document_id, department_id)` cho tài liệu `DEPARTMENTS`; `core.documents.visibility` là `WORKSPACE | DEPARTMENTS`, mặc định `WORKSPACE`. Ràng buộc: `DEPARTMENTS` phải có ít nhất một dòng.
- `core.categories(workspace_id, name, status)` phẳng; `documents.category_id` nullable; `core.tags`, `core.document_tags` theo workspace.
- Mọi bảng trên có `workspace_id` và RLS như ADR-005.

### 4.2 Vòng đời thành viên
`lời mời (chờ) → ACTIVE ⇄ SUSPENDED → rời/bị xóa`. `SUSPENDED` chặn cấp token cho workspace đó nhưng giữ hồ sơ, hội thoại và audit. Rời/bị xóa xóa membership; hội thoại của người đó trong workspace được giữ cho audit tới khi workspace bị xóa. Khóa ở workspace không ảnh hưởng tài khoản toàn cục; xóa tài khoản toàn cục ngoài phạm vi V2.

### 4.3 Phòng ban
- Chuyển phòng ban: cập nhật membership; có hiệu lực ở lần cấp token kế tiếp (≤ 15 phút, cùng cơ chế thu hồi của ADR-005 §4.4).
- Ngừng sử dụng (`ARCHIVED`): không gán mới được; thành viên đang thuộc phòng ban vẫn giữ tới khi được chuyển; tài liệu giới hạn cho phòng ban đó vẫn giới hạn. Nếu không còn ai trong phòng ban, chỉ OWNER/ADMIN đọc được các tài liệu đó.
- Xóa hẳn: chỉ khi không còn membership, lời mời đang chờ hay tài liệu tham chiếu (FK `RESTRICT`).
- Workspace cá nhân: không tạo phòng ban mặc định; UI ẩn phần phòng ban khi workspace chỉ có một thành viên.

### 4.4 Ma trận quyền
| Hành động | OWNER | ADMIN | MEMBER có phòng ban D | MEMBER chưa có phòng ban |
|---|:---:|:---:|:---:|:---:|
| Đọc tài liệu `WORKSPACE` | ✓ | ✓ | ✓ | ✓ |
| Đọc tài liệu `DEPARTMENTS` chứa D | ✓ | ✓ | ✓ | |
| Đọc tài liệu `DEPARTMENTS` không chứa D | ✓ | ✓ | | |
| Tải lên, sửa metadata, đổi phạm vi, xóa tài liệu | ✓ | ✓ | | |
| Quản lý phòng ban, category, mời, sửa hồ sơ, tạm khóa thành viên (trừ OWNER) | ✓ | ✓ | | |
| Tạm khóa/xóa OWNER, xem audit | ✓ | | | |

"Đọc" gồm danh sách, tìm kiếm, chi tiết, xem trước, tải xuống, xuất hiện trong kết quả truy xuất, context LLM và trích dẫn. Thành viên `SUSPENDED` không có quyền nào; access token cấp trước khi tạm khóa còn hiệu lực tới khi hết hạn (§5). Quyền quản lý tài liệu cho trưởng phòng ban là P1.

### 4.5 Thực thi quyền
- Access token thêm claim `wdept` (phòng ban của membership hoặc rỗng) cạnh `wid`, `wrole`. Refresh kiểm tra lại membership, `status` và `department_id`.
- ai-service giữ `rag.document_access(workspace_id, document_id, visibility, department_ids uuid[])`. Truy vấn dense và BM25 join bảng này với điều kiện `wrole IN (OWNER, ADMIN) OR visibility = 'WORKSPACE' OR :wdept = ANY(department_ids)`, **trước** `LIMIT k`. Rerank và LLM chỉ nhận ứng viên đã lọc. Tham số hóa toàn bộ, không f-string.
- Đổi phạm vi tài liệu: core-api ghi DB, gọi ai-service đồng bộ để cập nhật `rag.document_access`, outbox thử lại nếu lỗi. Tài liệu mới chỉ vào truy xuất sau khi dòng quyền đã có (`READY` đòi hỏi dòng quyền tồn tại); thiếu dòng quyền nghĩa là không đọc được (fail closed).
- Tải xuống/xem trước: core-api kiểm tra quyền rồi phát URL ký sẵn hạn ≤ 5 phút.
- Cache: cache câu trả lời/kết quả truy xuất (nếu có) dùng khóa gồm `workspace_id`, `wrole`, `wdept`; cache embedding chỉ chứa vector theo nội dung chunk, không trả văn bản.
- Lịch sử hội thoại: khi mở lại, mọi tài liệu câu trả lời được sinh ra từ đó (source trong context LLM và trích dẫn) được kiểm tra với quyền hiện tại; câu trả lời có tài liệu không còn quyền bị ẩn kèm lý do. (Sửa 2026-11-09 cho khớp §4.4: bản trước chỉ kiểm trích dẫn; chi tiết ở [TECH-V2-ai-service §7.5](../designs/TECH-V2-ai-service.md).)

## 5. Tác động & hệ quả
- **Tích cực:** đủ dùng cho nhóm và doanh nghiệp nhỏ; người dùng cá nhân không bị ảnh hưởng; một điểm lọc duy nhất trong SQL truy xuất; đổi quyền không cần embed lại.
- **Đánh đổi:**
  - Thu hồi theo phòng ban hay tạm khóa trễ tối đa một vòng đời access token; thu hẹp phạm vi tài liệu có hiệu lực khi ai-service nhận cập nhật.
  - Một phòng ban mỗi người không phục vụ người kiêm nhiệm (P1).
  - Thêm bảng `rag.document_access` là dữ liệu sao chép giữa hai service; cần test đồng bộ.
- **Hành động tiếp theo:**
  - TECH-V2 (V2-03) chốt DDL, claim token, API phòng ban/hồ sơ/metadata và contract cập nhật quyền sang ai-service.
  - FR-29: bộ test phân quyền phòng ban riêng với FR-19.
  - Khi duyệt: viết lại `.agent/context/authorization/` theo mô hình này cùng lúc với triển khai, không trước.
