---
id: ADR-009
title: "V2: quyền ghi tài liệu theo publisher của phòng ban và của workspace"
status: approved
created: 2026-11-10
updated: 2026-11-11
author: "Owner"
refs:
  - docs/02-architecture/adr/ADR-007-departments-member-profiles-document-access.md
  - docs/02-architecture/adr/ADR-005-workspace-tenancy-and-google-jit.md
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/02-architecture/designs/TECH-V2-core-api.md
deciders: ["Owner"]
amends: [ADR-007]
supersedes: []
superseded_by: ""
---

# ADR-009: Publisher theo phòng ban và publisher toàn workspace

> **Trạng thái:** `approved` (2026-11-10) | **Ngày đề xuất:** `2026-11-10` | **Người quyết định:** `Owner`
>
> ADR này điều chỉnh **quyền ghi tài liệu** của ADR-007 §4.4: quyền tải lên, sửa metadata, đổi phạm vi và xóa tài liệu chuyển từ OWNER/ADMIN sang **publisher**. Quyền đọc (ADR-007 §4.4 ba dòng đầu, §4.5), claim token, mô hình phòng ban phẳng và một phòng ban mỗi thành viên giữ nguyên. Chi tiết DDL, API và điểm kiểm tra ở [TECH-V2-core-api §15](../designs/TECH-V2-core-api.md).

---

## 1. Bối cảnh & vấn đề cần quyết định

- ADR-007 §4.4 cho OWNER và ADMIN toàn quyền ghi mọi tài liệu của workspace, và ghi "quyền quản lý tài liệu cho trưởng phòng ban là P1". PRD-V2 FR-06, FR-25 và §8 mục 9 nói cùng điều đó.
- Owner quyết định (2026-11-10) tách hai việc: ADMIN tiếp tục quản trị con người và danh mục (thành viên, phòng ban, category), còn **nội dung** tài liệu do người chịu trách nhiệm của từng phòng ban đăng. Lý do: trong doanh nghiệp, SOP của phòng ban nào do phòng đó ban hành; người quản trị hệ thống không nên sửa được nội dung phòng khác.
- Code hiện tại (kiểm tra 2026-11-10, nhánh `feat/knowledge-core-api-metadata-visibility`):
  - Quyền ghi tài liệu kiểm tra bằng `AuthPrincipal.requireManager()` (`wrole ∈ {OWNER, ADMIN}`) ở 7 chỗ trong `DocumentService`; `DocumentView` dùng `isManager()` để quyết định trả các trường quản trị. Không có khái niệm người chịu trách nhiệm tài liệu. (`CategoryService`, `DepartmentService`, `MemberService` cũng dùng `requireManager()` nhưng không đổi.)
  - `core.document_versions.uploaded_by uuid NOT NULL REFERENCES core.users(id)` và `created_at` **đã có** từ `core/V005`; `core.documents.created_by` cũng đã có. Yêu cầu "mỗi phiên bản ghi người đăng và thời điểm" (quyết định 5 bên dưới) đã được đáp ứng ở mức schema.
  - `core.memberships` có PK `(workspace_id, user_id)` và đúng một `department_id` nullable (ADR-007). `core.departments` có `UNIQUE (workspace_id, id)` cho FK hai cột.
  - `rag.document_access` (ai-service) chỉ chứa phạm vi đọc; không có dữ liệu ghi nào cần sang ai-service.

## 2. Tiêu chí đánh giá

1. Mỗi tài liệu có đúng một người được ghi tại một thời điểm, xác định được từ DB mà không đọc audit.
2. Không mở rộng quyền đọc (fail closed, ADR-007 tiêu chí 3); thay đổi chỉ chạm đường ghi của core-api.
3. Không tạo vai trò mới, không đổi claim `wrole`/`wdept`, không cần ai-service biết thêm gì (ADR-005 tiêu chí 4).
4. Ràng buộc chính nằm trong DB (FK, unique), phần còn lại kiểm tra trong cùng transaction ghi.
5. Không có quy trình duyệt, yêu cầu thay đổi hay thông báo trong hệ thống.

## 3. Các phương án xem xét

### Phương án A: ADMIN giữ quyền ghi (như ADR-007)
- **Mô tả:** giữ nguyên ma trận; trưởng phòng muốn đăng phải nhờ ADMIN.
- **(+)** Không đổi code, schema hay test.
- **(−)** ADMIN sửa được SOP của mọi phòng; không phân biệt người quản trị hệ thống với người chịu trách nhiệm nội dung. Trái quyết định của owner.

### Phương án B: một publisher cho cả workspace
- **Mô tả:** một người duy nhất được ghi mọi tài liệu.
- **(+)** Một bảng một dòng; kiểm tra quyền đơn giản nhất.
- **(−)** Nghẽn ở một người với workspace nhiều phòng ban; người đó vẫn sửa được tài liệu của mọi phòng, chỉ thay "ADMIN" bằng "một người".

### Phương án C: publisher theo phòng ban + publisher toàn workspace (chọn)
- **Mô tả:** mỗi phòng ban có đúng một publisher là thành viên `ACTIVE` của phòng đó; mỗi workspace có đúng một publisher cho tài liệu `WORKSPACE`. Mỗi tài liệu có một phòng chủ quản (`owner_department_id`) hoặc `NULL` khi là tài liệu `WORKSPACE`.
- **(+)** Người ghi của mỗi tài liệu được suy ra trực tiếp từ hai bảng nhỏ; ADMIN không còn sửa được nội dung; tài liệu `DEPARTMENTS` dùng chung nhiều phòng vẫn có một người chịu trách nhiệm.
- **(−)** Thêm hai bảng, một cột và một điểm kiểm tra quyền cho mọi endpoint ghi tài liệu. Có khoảng trống khi publisher rời phòng (phòng đó không đăng được tới khi OWNER gán lại).

### Biến thể đã loại trong phương án C
- **Thêm vai trò `PUBLISHER` vào `wrole`.** (−) Một người vừa là ADMIN vừa là publisher; token phải mang thêm phòng được ghi; đổi publisher phải chờ hết access token (≤ 15 phút). Owner đã loại (quyết định 7).
- **Đưa publisher vào claim token.** (−) Như trên; quyền ghi đọc từ DB trong transaction ghi thì có hiệu lực ngay và không cần đổi JWKS hay ai-service.
- **FK ba cột `(workspace_id, user_id, department_id) → memberships`** để DB tự đảm bảo publisher thuộc phòng. (−) PostgreSQL không có `ON UPDATE SET NULL (cột)`; dùng `RESTRICT` thì ADMIN không chuyển phòng ban được cho publisher cho tới khi OWNER gỡ trước, trái quyết định 4 ("rời phòng thì OWNER gán lại"). Thay bằng: core-api xóa dòng publisher trong cùng transaction đổi phòng ban, và kiểm tra lại lúc ghi (TECH §15.3).

## 4. Quyết định & biện luận

**Phương án được chọn: C.** Các mục dưới là quyết định của owner (2026-11-10), gồm cả các câu hỏi đã chốt ở §6; owner duyệt toàn bộ ADR cùng ngày.

### 4.1 Mô hình
1. **Publisher phòng ban.** Mỗi `core.departments` có tối đa một publisher (`core.department_publishers`, PK `department_id`). Publisher phải là thành viên `ACTIVE` có `memberships.department_id` bằng phòng đó. Phòng chưa có publisher thì không ai đăng hay sửa được tài liệu của phòng đó.
2. **Publisher toàn workspace** *(owner xác nhận 2026-11-10, §6 Q0, Q1)*. Mỗi workspace có tối đa một publisher (`core.workspace_publishers`, PK `workspace_id`), **chỉ** cho tài liệu `visibility = WORKSPACE`; người này không đăng hay sửa được tài liệu `DEPARTMENTS` (trừ khi đồng thời là publisher của phòng chủ quản). Người này phải là thành viên `ACTIVE`; không yêu cầu thuộc phòng ban nào.
3. **Phòng chủ quản.** `core.documents.owner_department_id uuid NULL`:
   - `NULL` ⇔ `visibility = WORKSPACE` (CHECK). Tài liệu `DEPARTMENTS` luôn có đúng một phòng chủ quản, và phòng đó phải nằm trong `core.document_departments` của tài liệu.
   - Tài liệu `DEPARTMENTS` dùng chung nhiều phòng: chỉ publisher của phòng chủ quản được ghi; các phòng còn lại trong `document_departments` chỉ đọc.
4. **Gán và đổi publisher.** Chỉ OWNER gán, đổi, gỡ publisher (cả phòng ban và workspace). Khi publisher bị gỡ, rời phòng, rời hoặc bị xóa khỏi workspace, dòng publisher bị xóa trong cùng transaction; OWNER gán lại thủ công. Trong lúc chưa gán, phạm vi đó không đăng được tài liệu mới và tài liệu đang có không sửa được. Không có cơ chế tự gán.
5. **Ai đã đăng.** Mỗi phiên bản ghi `uploaded_by` (user id) và thời điểm đăng. Hai cột này đã có (`document_versions.uploaded_by`, `created_at`, `core/V005`); TECH §15 gọi `created_at` là thời điểm đăng, **không thêm cột** `uploaded_at` trùng nghĩa. Audit ghi thêm phòng chủ quản và vai trò publisher lúc ghi (TECH §15.5).
6. **Ngoài hệ thống.** Không có luồng yêu cầu thay đổi, duyệt, thông báo hay hàng đợi phê duyệt. Người muốn sửa tài liệu liên hệ publisher ngoài hệ thống; hệ thống chỉ cho biết publisher là ai.
7. **Không vai trò mới.** `wrole` vẫn là `OWNER | ADMIN | MEMBER`; `wdept` không đổi. Publisher là một thuộc tính gán thêm cho membership, đọc từ DB khi ghi. Một OWNER, ADMIN hay MEMBER đều có thể là publisher; quyền thực tế là hợp của quyền theo vai trò và quyền publisher.
8. **OWNER phân trách nhiệm, không viết nội dung** *(owner chốt 2026-11-10, §6 Q4, Q5)*. Tách người ban hành nội dung (publisher) khỏi người phân công và thu hồi (OWNER), như cách quản lý tài liệu theo ISO 9001:
   - OWNER **thu hồi** (xóa) được mọi tài liệu của workspace mà không cần là publisher, để xử lý tài liệu sai khi phạm vi đó chưa có publisher hoặc publisher vắng mặt.
   - OWNER **chuyển trách nhiệm** một tài liệu: đổi `WORKSPACE ⇄ DEPARTMENTS` hoặc đổi phòng chủ quản, cùng danh sách phòng được đọc, trong một thao tác. Nội dung, phiên bản và lịch sử giữ nguyên; chỉ người được ghi và phạm vi đọc đổi.
   - OWNER **không** tải lên, tải bản thay thế, thử lại, sửa metadata hay áp dụng gợi ý nếu không phải publisher của phạm vi đó; muốn làm thì tự gán mình làm publisher.
   - Người tạo workspace mặc định là publisher workspace (§4.4) và có thể giao lại cho người khác (ví dụ Hành chính). Workspace có nhiều OWNER thì mọi OWNER đều có hai quyền trên; publisher workspace vẫn chỉ một người.
   - Mỗi lần thu hồi hay chuyển trách nhiệm đều ghi audit với tư cách OWNER.

Vai trò trong doanh nghiệp tương ứng (để hình dung, không phải ràng buộc):

| Vai trò hệ thống | Thường là | Chịu trách nhiệm |
|---|---|---|
| OWNER | Giám đốc, chủ doanh nghiệp | Ai được đăng gì; thu hồi và chuyển trách nhiệm tài liệu |
| ADMIN | Quản trị hệ thống, Nhân sự | Con người và danh mục; không đụng nội dung |
| Publisher workspace | Hành chính, thư ký ISO, hoặc giám đốc ở công ty nhỏ | Tài liệu chung toàn công ty |
| Publisher phòng D | Trưởng phòng hoặc người được ủy quyền | SOP của phòng D |
| MEMBER | Nhân viên | Đọc, hỏi đáp, liên hệ publisher khi cần sửa |

### 4.2 Ma trận quyền (thay dòng tương ứng của ADR-007 §4.4)

Cột "Pub. WS" = publisher toàn workspace; "Pub. D" = publisher của phòng D. Một người có thể nằm ở nhiều cột (ví dụ ADMIN đồng thời là Pub. D); khi đó lấy hợp các quyền.

| Hành động | OWNER | ADMIN | Pub. WS | Pub. D | MEMBER khác | Thay đổi so với ADR-007 §4.4 |
|---|:---:|:---:|:---:|:---:|:---:|---|
| Đọc tài liệu `WORKSPACE` | ✓ | ✓ | ✓ | ✓ | ✓ | Không đổi |
| Đọc tài liệu `DEPARTMENTS` chứa phòng của mình | ✓ | ✓ | ✓ | ✓ | ✓ | Không đổi |
| Đọc tài liệu `DEPARTMENTS` không chứa phòng của mình | ✓ | ✓ | | | | Không đổi (publisher không có quyền đọc thêm) |
| Tải lên, tải bản thay thế, thử lại, sửa metadata, áp dụng gợi ý tài liệu `WORKSPACE` | | | ✓ | | | **Đổi:** bỏ OWNER, ADMIN (quyết định 8) |
| Như trên cho tài liệu `DEPARTMENTS` có phòng chủ quản D | | | | ✓ | | **Đổi:** bỏ OWNER, ADMIN; chỉ publisher của phòng chủ quản |
| Xóa (thu hồi) tài liệu | ✓ (mọi tài liệu) | | ✓ (tài liệu `WORKSPACE`) | ✓ (tài liệu chủ quản D) | | **Đổi:** bỏ ADMIN; OWNER thu hồi được mọi tài liệu (§6 Q4) |
| Đổi danh sách phòng ban được đọc của tài liệu có phòng chủ quản D (giữ D trong danh sách) | ✓ (qua chuyển trách nhiệm) | | | ✓ | | **Đổi:** tách từ dòng "đổi phạm vi" của ADR-007 |
| Chuyển trách nhiệm: đổi `WORKSPACE ⇄ DEPARTMENTS` hoặc đổi phòng chủ quản | ✓ | | | | | **Mới:** chỉ OWNER (§6 Q5) |
| Xem lịch sử phiên bản, lý do `FAILED`, nguồn trường metadata, gợi ý | ✓ | ✓ | ✓ (tài liệu `WORKSPACE`) | ✓ (tài liệu chủ quản D) | | **Mới:** thêm publisher chịu trách nhiệm; OWNER/ADMIN vẫn xem (đọc) |
| Gán, đổi, gỡ publisher phòng ban và publisher workspace | ✓ | | | | | **Mới** |
| Xem ai là publisher của từng phòng và của workspace | ✓ | ✓ | ✓ | ✓ | ✓ | **Mới** (để liên hệ ngoài hệ thống) |
| Quản lý phòng ban, category, mời, sửa hồ sơ, tạm khóa thành viên (trừ OWNER) | ✓ | ✓ | | | | Không đổi |
| Tạm khóa/xóa OWNER, xem audit | ✓ | | | | | Không đổi |

Ghi chú:
- Dòng "Tải lên, sửa metadata, đổi phạm vi, xóa tài liệu" của ADR-007 §4.4 được thay bằng bốn dòng "Đổi" ở trên. Câu "Quyền quản lý tài liệu cho trưởng phòng ban là P1" của ADR-007 §4.4 được thay bằng ADR này: publisher phòng ban vào MVP.
- Publisher của phòng `ARCHIVED`: vẫn sửa và xóa tài liệu đang có của phòng; không tạo tài liệu mới với phòng đó làm chủ quản (đồng nhất với "không gán mới vào phòng `ARCHIVED`" của ADR-007 §4.3). Không gán publisher mới cho phòng `ARCHIVED`.
- Từ chối ghi khi người gọi đọc được tài liệu → `403 NOT_PUBLISHER`; khi không đọc được → `404` như ADR-007 (không lộ tên). Tạo mới khi không phải publisher của phạm vi đích → `403 NOT_PUBLISHER`.
- Thành viên `SUSPENDED` không có quyền nào (ADR-007); dòng publisher của họ được giữ nhưng kiểm tra lúc ghi yêu cầu `ACTIVE`.

### 4.3 Thực thi
- Một điểm kiểm tra duy nhất trong core-api (`DocumentWritePolicy`, TECH §15.3) cho mọi endpoint ghi tài liệu, đọc publisher từ DB trong cùng transaction và khóa dòng publisher (`FOR SHARE`) để không chạy song song với việc OWNER đổi publisher.
- Quyền đọc không đổi: bộ lọc đọc của core-api (TECH §5.6) và `rag.document_access` (ADR-007 §4.5) không dùng `owner_department_id` hay bảng publisher. ai-service không đổi.
- Phiên bản đang `READY` không bị ảnh hưởng khi đổi publisher *(owner chốt 2026-11-10, §6 Q3)*: đổi publisher chỉ đổi ai được ghi tiếp, không đổi trạng thái, phạm vi đọc hay chunk.

### 4.4 Chuyển dữ liệu hiện có
- `workspace_publishers`: mỗi workspace chưa xóa nhận `created_by` nếu người đó còn là thành viên `ACTIVE`, nếu không thì OWNER `ACTIVE` gia nhập sớm nhất. Workspace `PERSONAL` và workspace `TEAM` mới tạo tự gán người tạo (trong `core.create_personal_workspace` và `POST /workspaces`), để workspace cá nhân, eval và demo vẫn tải lên được.
- `department_publishers`: không backfill; mọi phòng bắt đầu không có publisher tới khi OWNER gán (đúng quyết định 4).
- `documents.owner_department_id` của tài liệu `DEPARTMENTS` đã có: xem §6 Q6.

## 5. Tác động & hệ quả

- **Tích cực:**
  - Người ghi của mỗi tài liệu xác định được từ DB; ADMIN không còn sửa được nội dung SOP.
  - Không đổi token, JWKS, ai-service hay `rag.document_access`; bộ test đọc FR-29 giữ nguyên ý nghĩa.
  - Đổi publisher có hiệu lực ngay ở request ghi kế tiếp (không chờ token hết hạn).
- **Đánh đổi:**
  - Khoảng trống khi publisher rời phòng: phòng đó không đăng hay sửa được tới khi OWNER gán lại. Chấp nhận theo quyết định 4.
  - Mỗi request ghi tài liệu thêm một truy vấn khóa dòng publisher.
  - OWNER chỉ thu hồi hoặc chuyển trách nhiệm được, không sửa nhanh nội dung sai nếu không phải publisher; ADMIN không có quyền nào trên tài liệu (§6 Q4).
  - Thêm một endpoint chỉ OWNER gọi được để chuyển trách nhiệm (TECH §15.4), kèm kiểm thử.
  - Danh sách khoảng trống tri thức (FR-17, V2-13) vẫn chỉ cho OWNER và ADMIN xem, publisher không xem được. ADMIN thấy chỗ thiếu tài liệu nhưng không ghi được, nên phải báo publisher của phòng liên quan ngoài hệ thống (làm tay). Chấp nhận trong MVP vì: (1) câu `NO_EVIDENCE` và `GENERATOR_NOT_FOUND` không gắn được với tài liệu hay phòng nào (ai-service fail closed, TECH-V2-ai-service §3.4); (2) `rag.document_access` không có `owner_department_id`; (3) cho publisher xem cần đưa publisher vào token hoặc cho ai-service gọi core-api, trái "không đổi token, ai-service" ở trên; (4) publisher phòng A sẽ đọc câu hỏi (đã che PII) của nhân viên phòng B. Việc để publisher xem và xử lý danh sách này nằm ngoài ADR này; làm sau MVP thì cần ADR riêng.
  - PRD-V2 FR-06, FR-25 và §8 mục 9 phải sửa theo khi ADR này được duyệt.
  - Workspace một thành viên: người đó là OWNER và publisher toàn workspace; tài liệu `DEPARTMENTS` chỉ đăng được khi đã tạo phòng ban, tự xếp mình vào phòng và tự gán mình làm publisher.
- **Hành động tiếp theo (khi duyệt):**
  - TECH-V2-core-api §15 chuyển từ đề xuất sang đặc tả; migration `core/V009` qua skill `flyway-migration`.
  - Ticket [V2-36](../../03-plans/tickets/V2-36-core-api-department-publishers.md) triển khai core-api và test phân quyền ghi; V2-31, V2-33 hiển thị nút ghi và màn gán publisher; V2-16 tạo publisher cho dữ liệu demo.
  - Sửa PRD-V2 FR-06, FR-25, §8 mục 9.
  - Cập nhật `.agent/context/authorization/v2-core-identity.md` và `.agent/context/database/tables/core.md` cùng lúc với triển khai (như ADR-007), không trước.
  - Cập nhật sơ đồ `docs/02-architecture/diagrams/sopilot-database-erd.excalidraw` từ "đề xuất" sang thật khi migration được gộp.

## 6. Câu hỏi mở (owner quyết, ADR không tự chốt)

> **Owner chốt 2026-11-10:** Q0 giữ publisher toàn workspace; Q1 không (publisher workspace chỉ ghi tài liệu `WORKSPACE`); Q3 phiên bản `READY` không bị ảnh hưởng; Q7 sửa PRD-V2 sau khi ADR này được giải quyết hết câu hỏi mở và duyệt. Q2 không (theo đề xuất); Q6 theo quy tắc phòng của người đăng (theo đề xuất); Q4, Q5 theo quyết định 8 (OWNER thu hồi và chuyển trách nhiệm, không viết nội dung). Không còn câu hỏi mở; owner duyệt ADR (`approved`) cùng ngày.

| # | Câu hỏi | Ràng buộc đã biết | Đề xuất |
|---|---|---|---|
| Q0 | Có giữ **publisher toàn workspace** (quyết định 2) không? | Nếu bỏ, tài liệu `WORKSPACE` không còn ai ghi được, trừ khi tài liệu `WORKSPACE` cũng có phòng chủ quản (khi đó quy tắc "`NULL` ⇔ `WORKSPACE`" phải bỏ). | **Chốt: giữ.** Một dòng mỗi workspace, cần cho workspace cá nhân và eval. |
| Q1 | Publisher toàn workspace có được đăng tài liệu `DEPARTMENTS` không, hay chỉ `WORKSPACE`? | Nếu được, tài liệu `DEPARTMENTS` do người này đăng không có phòng chủ quản, nên quy tắc "`owner_department_id IS NULL` ⇔ `WORKSPACE`" không còn đúng; cần cột hoặc giá trị riêng để biết ai ghi (ví dụ `owner_scope WORKSPACE|DEPARTMENT`). | **Chốt: không.** Chỉ `WORKSPACE`; giữ quy tắc "`NULL` ⇔ `WORKSPACE`", DDL TECH §15.2 không đổi. |
| Q2 | Một người có thể là publisher của nhiều phòng không? | Với ADR-007 (một phòng ban mỗi thành viên) và quyết định 1 (publisher phải thuộc phòng đó), một người **chỉ có thể** là publisher của phòng mình. Trả lời "có" cần nới quyết định 1 hoặc cho thành viên nhiều phòng (P1 của ADR-007). Một người vẫn có thể vừa là publisher phòng vừa là publisher toàn workspace. | **Chốt: không** trong MVP (hệ quả tự nhiên của schema). Tài liệu nhiều phòng dùng chung đã được giải quyết bằng một phòng chủ quản (quyết định 3). |
| Q3 | Khi OWNER đổi publisher, phiên bản đang `READY` có bị ảnh hưởng không? | Đổi publisher không chạm `document_versions`, `rag.document_access` hay chunk. | **Chốt: không ảnh hưởng.** Phiên bản cũ tiếp tục phục vụ Q&A; publisher mới tải bản thay thế khi cần. |
| Q4 | OWNER có quyền ghi ngầm định (không cần là publisher) không, ví dụ để gỡ tài liệu sai khi phòng chưa có publisher? | Quyết định "quyền ghi chuyển sang publisher" chỉ nói rõ về ADMIN. OWNER gán được chính mình làm publisher workspace bất kỳ lúc nào; làm publisher phòng D thì phải thuộc phòng D. | **Chốt:** OWNER không có quyền viết nội dung ngầm định (tự gán mình làm publisher khi cần), nhưng **thu hồi (xóa) được mọi tài liệu** (quyết định 8). |
| Q5 | Ai được đổi `WORKSPACE ⇄ DEPARTMENTS` hoặc chuyển phòng chủ quản (chuyển trách nhiệm tài liệu)? | Mỗi thao tác này đổi người được ghi. Nếu publisher phòng D tự đổi sang `WORKSPACE` thì mất quyền ghi tài liệu vừa đổi. | **Chốt: chỉ OWNER**, qua thao tác chuyển trách nhiệm riêng, giữ nội dung và lịch sử (quyết định 8, TECH §15.4). Publisher gọi `PUT /visibility` để đổi loại hoặc bỏ phòng chủ quản → `409 OWNERSHIP_CHANGE_REQUIRES_OWNER`. |
| Q6 | Tài liệu `DEPARTMENTS` đã có (trước migration) lấy phòng chủ quản nào? | Migration không đoán được ý định khi tài liệu có nhiều phòng. Corpus nghiên cứu trong DB local chủ yếu là `WORKSPACE` (chưa đo). | **Chốt:** một phòng → phòng đó; nhiều phòng → phòng hiện tại của người đăng phiên bản đầu tiên (`document_versions.uploaded_by` → `memberships.department_id`) nếu phòng đó có trong `document_departments`; nếu không → phòng có `lower(name)` nhỏ nhất. Liệt kê các tài liệu nhiều phòng trong ghi chú migration để OWNER kiểm. |
| Q7 | PRD-V2 FR-06, FR-25, §8 mục 9 sửa trong cùng lần duyệt ADR hay trong V2-36? | Ba chỗ đang ghi "chỉ OWNER/ADMIN tải lên, sửa, xóa". | **Chốt: sửa sau khi ADR này hết câu hỏi mở và được duyệt**, trước khi bắt đầu V2-36. |
