---
id: ADR-005
title: "V2: workspace là tenant; đăng nhập Google JIT, lời mời và gia nhập theo domain thay cho roster"
status: approved
created: 2026-10-16
updated: 2026-10-20
refs: [docs/01-requirements/PRD-V2-sopilot-mvp.md, docs/02-architecture/adr/ADR-004-two-service-architecture.md]
deciders: ["Owner"]
amends: []
supersedes: [ADR-001, ADR-003]
superseded_by: ""
---

# ADR-005: Workspace là tenant; Google JIT, lời mời và domain thay cho roster

> **Trạng thái:** `approved` (2026-10-20) | **Ngày đề xuất:** `2026-10-16` | **Người quyết định:** `Owner`
>
> Khi được duyệt, ADR này thay thế ADR-001 (roster thuộc user-service) và ADR-003 (admission bằng roster mỗi lần đăng nhập Google). Quy tắc binding danh tính theo `(issuer, sub)` của ADR-003 được giữ nguyên.

---

## 1. Bối cảnh & vấn đề cần quyết định
- Kiểm tra code ngày 2026-10-16: không có khái niệm tổ chức trong schema, JWT hay spec. `core.employee_roster` có email unique toàn cục; phòng ban và access rule là toàn cục; `ai-qa-service` (`chunk_repo.py`) lọc chunk theo role/phòng ban/user, không theo tổ chức.
- Mọi đăng nhập Google đều cần có tên trong roster, nên người dùng đơn lẻ và nhóm không có HR bị chặn.
- PRD-V2 cần một mô hình phục vụ được cả cá nhân, startup và doanh nghiệp, với cách ly dữ liệu tuyệt đối.

## 2. Tiêu chí đánh giá
1. Không rò rỉ dữ liệu giữa tenant, kể cả khi có lỗi lập trình ở một truy vấn.
2. Onboarding không cần quản trị viên cho người dùng đơn lẻ.
3. Doanh nghiệp vẫn kiểm soát được ai vào workspace.
4. ai-service không phải gọi core-api ở mỗi request để kiểm tra quyền.

## 3. Các phương án xem xét

### Mô hình tenant
- **A. Giữ roster, thêm `organization_id` vào mọi bảng.** (−) Vẫn cần HR cho mọi người dùng; không có lối vào cho solo user.
- **B. Workspace + membership (chọn).** User là toàn cục; workspace là tenant; membership mang role. Một người thuộc nhiều workspace. Solo user là trường hợp riêng: workspace một thành viên.
- **C. Database/schema riêng cho mỗi tenant.** (−) Quá nặng cho gói miễn phí và cho eval.

### Cách ly dữ liệu
- **Chỉ lọc ở tầng ứng dụng.** (−) Một truy vấn quên `WHERE workspace_id` là rò rỉ.
- **Lọc ở ứng dụng + Postgres RLS (chọn).** Bảng có `workspace_id` bật RLS với policy `workspace_id = current_setting('app.workspace_id')::uuid`. Mỗi transaction đặt `SET LOCAL app.workspace_id` từ token. Role database của ứng dụng không phải owner bảng và không có `BYPASSRLS`.

### Phạm vi token
- **Token theo user, kiểm tra membership mỗi request.** (−) ai-service phải gọi core-api hoặc đọc schema `core`.
- **Token theo workspace (chọn).** Access token chứa `sub` (user id), `wid` (workspace đang hoạt động), `wrole`. Chuyển workspace là gọi `POST /api/v1/auth/switch-workspace` để nhận token mới.

## 4. Quyết định & biện luận
- **Được chọn:** workspace + membership; lọc ở ứng dụng + RLS; access token theo workspace.

### 4.1 Đăng nhập Google (JIT)
1. Xác minh ID token như hiện tại (`GoogleTokenVerifierService`): RS256/JWKS, `iss`, `aud`, `exp`, `email_verified`. Bổ sung kiểm tra `nonce`. Không trả chi tiết lỗi nội bộ ra client.
2. Tìm user theo `(issuer, sub)` trong `core.external_identities`. Không có thì tạo user + identity trong một transaction (JIT). Không bao giờ liên kết theo email.
3. User mới được tạo workspace cá nhân với role `OWNER` (idempotent).
4. Áp dụng lời mời đang chờ hoặc gia nhập theo domain (4.2), rồi phát token cho workspace hoạt động gần nhất.
5. Tài khoản Google không có mật khẩu; cột password hash bị bỏ.

### 4.2 Gia nhập workspace
- **Lời mời:** `core.invitations(workspace_id, email, role, token_hash, expires_at, accepted_at, revoked_at)`. Chỉ lưu hash của token. Chỉ chấp nhận khi email đã xác minh của Google khớp email được mời (so sánh không phân biệt hoa thường). Mỗi lời mời dùng được một lần.
- **Domain (P1):** `core.workspace_domains(workspace_id, domain)`. Chỉ owner có claim `hd` bằng đúng domain đó mới đăng ký được, nên không cần xác minh DNS. Người đăng nhập có `hd` trùng domain thấy workspace và tự gia nhập với role `MEMBER`. Email Gmail cá nhân không bao giờ khớp domain.

### 4.3 Role và quy tắc
| Hành động | OWNER | ADMIN | MEMBER |
|---|---|---|---|
| Hỏi đáp, xem/tải tài liệu, phản hồi | ✓ | ✓ | ✓ |
| Tải lên/xóa tài liệu, xem khoảng trống tri thức | ✓ | ✓ | |
| Mời, xóa member, đổi role (không đụng tới OWNER) | ✓ | ✓ | |
| Thăng/giáng OWNER, bật domain, xóa workspace, xem audit | ✓ | | |

Workspace luôn còn ít nhất một `OWNER`. Workspace cá nhân không xóa được khi đó là workspace duy nhất của user.

### 4.4 Thu hồi quyền
- Access token sống ≤ 15 phút. Khi refresh, core-api kiểm tra lại membership của `wid`; mất membership thì không phát token cho workspace đó nữa.
- Vì vậy, xóa thành viên có hiệu lực chậm nhất sau một vòng đời access token. Độ trễ này được chấp nhận cho MVP và ghi trong tài liệu bảo mật.

### 4.5 Cách ly trong ai-service
- `rag.chunks`, `rag.conversations`, `rag.messages`, `rag.ingestion_jobs` đều có `workspace_id` và bật RLS.
- Mọi truy vấn truy xuất có `workspace_id = :wid` lấy từ token đã xác minh, không bao giờ lấy từ body request.
- Bộ test FR-19 chứng minh cách ly ở cả HTTP lẫn SQL.

## 5. Tác động & hệ quả
- **Tích cực:** phục vụ được solo user, startup và doanh nghiệp bằng một mô hình duy nhất; cách ly có hai lớp; ai-service không phụ thuộc core-api khi phục vụ request.
- **Đánh đổi:**
  - ~~Mất phòng ban và phân quyền theo phòng ban trong V2.~~ Đề xuất 2026-10-19: [ADR-007](ADR-007-departments-member-profiles-document-access.md) giữ phòng ban phẳng trong workspace và quyền đọc tài liệu theo phòng ban.
  - Độ trễ thu hồi quyền ≤ thời hạn access token.
  - RLS đòi hỏi kỷ luật quản lý connection (`SET LOCAL` trong mỗi transaction); cần test để không rò `app.workspace_id` qua connection pool.
- **Hành động tiếp theo:**
  - DDL `core` (users, external_identities, workspaces, memberships, invitations, workspace_domains, refresh_tokens, documents, feedback, audit_logs) và `rag` trong TECH.
  - Khi duyệt: chuyển ADR-001, ADR-003 sang `superseded`; viết lại `.agent/context/authorization/` theo mô hình workspace.
