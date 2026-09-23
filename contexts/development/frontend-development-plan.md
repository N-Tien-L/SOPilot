# Frontend Development Plan - Poliwise

> **Nguồn phân tích**: So sánh exhaustively giữa backend API contracts (7 microservices) và frontend codebase hiện tại (Next.js 16 App Router).
> **Nguyên tắc**: Không suy đoán. Mỗi mục đều có evidence từ backend API và được so sánh với trạng thái frontend hiện tại.

---

## I. Tổng quan Coverage

### 1.1 Backend API Summary

| Domain | Backend Status | Endpoints Count | Frontend Status |
|--------|--------------|-----------------|-----------------|
| Authentication | ✅ Hoàn chỉnh | 6 (login, register, refresh, logout, logout-all, sessions) | ⚠️ Thiếu: register, logout-all, sessions |
| User Management | ✅ Hoàn chỉnh | 7 (CRUD profile, search, status, department) | ⚠️ Thiếu: search filters, department change, delete |
| Documents | ✅ Hoàn chỉnh | 7 (list, get, upload, delete, download, confirm, cancel) | ⚠️ Thiếu: detail view, versions, process trigger, compare |
| Metadata | ✅ Hoàn chỉnh | 10+ (categories, tags, access rules, lifecycle) | ❌ Gần như không có (chỉ getCategories) |
| AI Q&A | ❌ Không có service | 10 endpoints định nghĩa trong Gateway | ⚠️ UI có nhưng API sẽ fail |
| Feedback | ✅ Hoàn chỉnh | 5 (submit, list, by-conversation, by-user, delete) | ⚠️ Thiếu: list by conversation, by user |
| Analytics | ✅ Hoàn chỉnh | 10+ (dashboard, overview, trends, top questions/docs, dept stats) | ⚠️ Thiếu: hầu hết |
| Reporting | ✅ Hoàn chỉnh | 4 (create, status, download, list my reports) | ❌ Không có |
| Audit Logs | ✅ Hoàn chỉnh | 2 (search, get by ID) | ❌ Không có |
| Sessions | ✅ Hoàn chỉnh | 1 (get active sessions) | ❌ Không có |
| Unanswered Questions | ✅ Hoàn chỉnh | 2 (list, resolve) | ❌ Không có |
| Password Management | ❌ Không có service | 0 | ❌ Không có |

### 1.2 Critical Frontend-Backend Issues

#### Issue 1: Duplicate AI API definitions (CONFUSION)
- `lib/api.ts` định nghĩa: `POST /api/v1/ai/ask` → `api.ai.ask()`
- `services/ai.service.ts` định nghĩa: `POST /api/v1/ai/chat` → `aiService.sendMessage()`
- `app/page.tsx` gọi `api.ai.ask()` từ `lib/api.ts`
- Backend API Gateway định nghĩa proxy route: cả hai đều proxy đến `ai-qa-service:8086`

**Action**: Chỉ giữ một nơi. Consolidate vào `lib/api.ts`.

#### Issue 2: Direct service bypass for uploads (WORKAROUND)
- Frontend upload gọi **trực tiếp** `knowledge-service:8083` thay vì qua Gateway
- Lý do: Gateway không xử lý được `multipart/form-data` streaming
- Backend có note trong code: `"Multipart uploads go directly to knowledge-service to avoid gateway parsing issues with multipart/form-data"`

**Action**: Giữ nguyên bypass này vì là workaround đúng. Nhưng cần document rõ.

#### Issue 3: Conversation history endpoint mismatch
- `lib/api.ts`: `GET /api/v1/ai/history` → `api.ai.getHistory()`
- `services/ai.service.ts`: `GET /api/v1/ai/conversations` → `aiService.getConversations()`
- `app/page.tsx` sử dụng `api.ai.getHistory()` từ `lib/api.ts`

**Action**: Backend Gateway strip prefix `/api/v1/ai` nên cả hai đều đến đúng service. Cần verify endpoint path chính xác.

#### Issue 4: Feedback API mismatch
- `lib/api.ts`: `POST /api/v1/feedback` với body `{ conversationId, type, comment }`
- Backend `FeedbackController`: nhận `FeedbackRequest` với fields `{ conversationId, messageId, type, comment }`

**Action**: Frontend thiếu `messageId` trong feedback request. Cần fix.

---

## II. Kiến trúc frontend hiện tại & cần cải thiện

### 2.1 Current Architecture

```
frontend/web/
├── app/                    # App Router pages
│   ├── page.tsx            # Chat (AI Q&A)
│   ├── login/page.tsx      # Login
│   ├── profile/page.tsx    # Profile
│   ├── documents/page.tsx  # Document list
│   ├── analytics/page.tsx  # Analytics dashboard
│   └── admin/users/        # Admin: user management
│
├── components/            # Shared components
│   ├── layout/            # Header, Sidebar, MainLayout
│   ├── ui/                # Toast, LoadingScreen
│   └── documents/         # UploadModal, TagInput
│
├── lib/api.ts             # Main API client (class ApiClient)
├── services/              # Domain services (alternative to lib/api.ts)
│   ├── api-client.ts       # Axios client (Zustand-based)
│   ├── auth.service.ts
│   ├── user.service.ts
│   ├── knowledge.service.ts
│   ├── ai.service.ts       # DUPLICATE with lib/api.ts
│   ├── feedback.service.ts
│   └── analytics.service.ts
│
├── store/                 # Zustand state
│   ├── auth-store.ts       # Auth + user state
│   └── ui-store.ts         # UI state
│
├── types/                 # Shared types (flat)
│   ├── auth.ts
│   ├── document.ts
│   ├── ai.ts
│   └── analytics.ts
│
└── interfaces/models/     # Detailed models (backend-aligned)
    ├── core/
    ├── knowledge/
    ├── metadata/
    ├── conversation/
    └── analytics/
```

### 2.2 Proposed Cleanup Architecture

```
frontend/web/
├── app/
│   ├── (auth)/            # Auth group (no layout)
│   │   ├── login/page.tsx
│   │   └── forgot-password/page.tsx
│   │
│   ├── (main)/           # Main group (with MainLayout)
│   │   ├── page.tsx              # Chat AI
│   │   ├── profile/page.tsx      # My profile
│   │   ├── documents/
│   │   │   ├── page.tsx         # Document list
│   │   │   ├── [id]/page.tsx    # Document detail
│   │   │   └── [id]/versions/page.tsx
│   │   │
│   │   └── analytics/
│   │       ├── page.tsx         # Analytics dashboard
│   │       └── reports/page.tsx  # Report export
│   │
│   └── (admin)/          # Admin group (with MainLayout + admin check)
│       ├── users/page.tsx
│       ├── metadata/
│       │   ├── categories/page.tsx
│       │   └── tags/page.tsx
│       ├── access-rules/page.tsx
│       ├── audit-logs/page.tsx
│       ├── sessions/page.tsx
│       └── settings/page.tsx
│
├── components/
│   ├── layout/           # Header, Sidebar, MainLayout
│   ├── ui/              # Button, Input, Select, Table, Modal, Badge, Card, Pagination
│   ├── documents/       # UploadModal, DocumentCard, VersionHistory, TagInput
│   ├── analytics/        # StatCard, Chart components
│   └── shared/          # ConfirmDialog, EmptyState, PageHeader
│
├── lib/
│   ├── api.ts           # Single unified API client (consolidate from lib/api.ts)
│   └── utils.ts         # Date formatting, number formatting, etc.
│
├── store/
│   ├── auth-store.ts    # Keep existing
│   └── ui-store.ts      # Keep existing
│
└── types/
    └── index.ts         # Consolidated types
```

---

## III. Design System

### 3.1 Giữ nguyên & Tái sử dụng

Giữ nguyên:
- **Color scheme**: CSS variables với Tailwind (primary `#4f46e5`, destructive `#ef4444`, v.v.)
- **Layout**: Header 64px, Sidebar 280px
- **Toast system**: ToastContext + ToastContainer đã hoàn chỉnh
- **Zustand stores**: auth-store và ui-store
- **Axios client**: Core interceptors từ `lib/api.ts`

### 3.2 Cần xây dựng mới (Design System Components)

Tất cả components dùng **chung thư viện icon `lucide-react`** (đã có trong package.json).

#### UI Components cần xây dựng

| Component | Mô tả | Props chính |
|-----------|--------|-------------|
| `ui/Button` | Button với variants: `primary`, `secondary`, `ghost`, `destructive` | `variant`, `size`, `loading`, `disabled`, `icon`, `children` |
| `ui/Input` | Input field | `label`, `error`, `helperText`, `leftIcon`, `rightIcon` |
| `ui/Select` | Select dropdown | `label`, `options`, `value`, `onChange`, `error`, `placeholder` |
| `ui/Textarea` | Multi-line input | `label`, `error`, `rows`, `maxLength` |
| `ui/Checkbox` | Checkbox | `label`, `checked`, `onChange`, `disabled` |
| `ui/Switch` | Toggle switch | `label`, `checked`, `onChange` |
| `ui/Badge` | Status badge | `variant` (success/warning/error/info/neutral), `children` |
| `ui/Card` | Card container | `title`, `actions`, `children` |
| `ui/Modal` | Modal dialog | `open`, `onClose`, `title`, `size`, `children`, `footer` |
| `ui/Table` | Data table | `columns`, `data`, `loading`, `empty`, `pagination`, `onSort` |
| `ui/Pagination` | Pagination control | `page`, `totalPages`, `onPageChange`, `siblingCount` |
| `ui/Tabs` | Tab navigation | `tabs`, `activeTab`, `onTabChange` |
| `ui/Avatar` | User avatar | `src`, `name`, `size` |
| `ui/Spinner` | Loading spinner | `size`, `color` |
| `ui/Skeleton` | Loading placeholder | `width`, `height`, `variant` |
| `ui/EmptyState` | Empty data placeholder | `icon`, `title`, `description`, `action` |
| `ui/ConfirmDialog` | Confirmation dialog | `title`, `message`, `confirmLabel`, `variant`, `onConfirm`, `onCancel` |
| `ui/PageHeader` | Page header với title + actions | `title`, `description`, `actions` |
| `ui/StatCard` | Statistics card | `label`, `value`, `change`, `icon`, `trend` |
| `ui/Breadcrumb` | Breadcrumb navigation | `items` |

### 3.3 CSS Variables (giữ nguyên)

```css
:root {
  /* Colors */
  --background: #ffffff;
  --foreground: #0f172a;
  --primary: #4f46e5;
  --primary-foreground: #ffffff;
  --secondary: #f1f5f9;
  --muted: #f1f5f9;
  --muted-foreground: #64748b;
  --destructive: #ef4444;
  --destructive-foreground: #ffffff;
  --success: #22c55e;
  --warning: #f59e0b;
  --border: #e2e8f0;
  --input: #e2e8f0;
  --ring: #4f46e5;

  /* Layout */
  --sidebar-width: 280px;
  --header-height: 64px;

  /* Radius */
  --radius: 0.5rem;
}
```

---

## IV. Nhiệm vụ chi tiết

### TASK 1: Design System — Xây dựng shared UI components

**Priority**: P0 (nền tảng)
**Effort**: Medium

#### 1.1 Xây dựng base UI components
Tạo thư mục `components/ui/` với:

```
components/ui/
├── button/
│   ├── Button.tsx
│   └── button.module.css
├── input/
│   ├── Input.tsx
│   └── input.module.css
├── select/
│   ├── Select.tsx
│   └── select.module.css
├── badge/
│   ├── Badge.tsx
│   └── badge.module.css
├── card/
│   ├── Card.tsx
│   └── card.module.css
├── modal/
│   ├── Modal.tsx
│   └── modal.module.css
├── table/
│   ├── Table.tsx
│   ├── TableHeader.tsx
│   ├── TableBody.tsx
│   ├── TableRow.tsx
│   ├── TableCell.tsx
│   └── table.module.css
├── pagination/
│   ├── Pagination.tsx
│   └── pagination.module.css
├── tabs/
│   ├── Tabs.tsx
│   └── tabs.module.css
├── avatar/
│   ├── Avatar.tsx
│   └── avatar.module.css
├── spinner/
│   ├── Spinner.tsx
│   └── spinner.module.css
├── skeleton/
│   ├── Skeleton.tsx
│   └── skeleton.module.css
├── empty-state/
│   ├── EmptyState.tsx
│   └── empty-state.module.css
├── confirm-dialog/
│   ├── ConfirmDialog.tsx
│   └── confirm-dialog.module.css
├── page-header/
│   ├── PageHeader.tsx
│   └── page-header.module.css
├── stat-card/
│   ├── StatCard.tsx
│   └── stat-card.module.css
├── breadcrumb/
│   ├── Breadcrumb.tsx
│   └── breadcrumb.module.css
├── index.ts  # Barrel export
```

**Quy tắc**:
- Mỗi component là một directory với TSX + CSS module
- Dùng `lucide-react` cho tất cả icons (không svg inline)
- Export tất cả qua `components/ui/index.ts`
- Tất cả components nhận `className` prop để override
- TypeScript strict mode

#### 1.2 Consolidate API client
**Action cụ thể**:

1. **Xóa bỏ** `services/ai.service.ts` — duplicate với `lib/api.ts`
2. **Sửa** `lib/api.ts` — thêm các endpoint còn thiếu
3. **Merge** `services/api-client.ts` → `lib/api.ts` (giữ logic interceptors từ `api-client.ts`)

**Endpoints cần thêm vào `lib/api.ts`**:

```typescript
// Auth - thêm
auth: {
  // Đã có: login, register, refresh, logout, logoutAll, getSessions
  // Cần thêm:
  // forgotPassword(email: string): Promise<void>
  // resetPassword(token: string, newPassword: string): Promise<void>
  // changePassword(currentPassword: string, newPassword: string): Promise<void>
}

// AI - sửa để align với ai.service.ts
ai: {
  ask(data: { question: string; conversationId?: string }): Promise<QuestionResponse>
  // Đổi tên: getHistory -> getConversations (align với ai.service.ts)
  getConversations(params?): Promise<ConversationHistory>
  getConversationById(id: string): Promise<Conversation>
  getMessages(conversationId: string): Promise<Message[]>
  deleteConversation(id: string): Promise<void>
  clearHistory(id: string): Promise<void>
  markAsUnanswered(conversationId: string, messageId: string): Promise<UnansweredQuestion>
}

// Feedback - sửa (thiếu messageId)
feedback: {
  submit(conversationId: string, messageId: string, type: FeedbackType, comment?: string): Promise<void>
  // Đã có trong api.ts: ai.giveFeedback - CẦN SỬA body thiếu messageId
}

// Documents - thêm
documents: {
  // Đã có: getAll, getById, upload, delete, download, confirmMetadata, cancel
  // Cần thêm:
  getVersions(documentId: string): Promise<DocumentVersion[]>
  getProcessingJob(documentId: string): Promise<ProcessingJob>
  triggerProcess(documentId: string): Promise<void>
  comparePolicies(doc1Id: string, doc2Id: string): Promise<PolicyComparisonResponse>
}

// Metadata - thêm
metadata: {
  // Đã có: getCategories, getTags
  // Cần thêm:
  getCategoryById(id: string): Promise<Category>
  createCategory(data: CreateCategoryRequest): Promise<Category>
  updateCategory(id: string, data: UpdateCategoryRequest): Promise<Category>
  deleteCategory(id: string): Promise<void>

  createTag(data: CreateTagRequest): Promise<Tag>
  updateTag(id: string, data: UpdateTagRequest): Promise<Tag>
  deleteTag(id: string): Promise<void>
  resolveTags(tagNames: string[]): Promise<Tag[]>

  createDocumentMetadata(data: CreateDocumentMetadataRequest): Promise<DocumentMetadata>
  updateDocumentMetadata(id: string, data: UpdateDocumentMetadataRequest): Promise<DocumentMetadata>
  publishDocument(id: string): Promise<DocumentMetadata>
  archiveDocument(id: string): Promise<DocumentMetadata>
  deleteDocumentMetadata(id: string): Promise<void>

  createAccessRule(metadataId: string, data: CreateAccessRuleRequest): Promise<AccessRule>
  getAccessRules(metadataId: string): Promise<AccessRule[]>
  deleteAccessRule(ruleId: string): Promise<void>
}

// Analytics - thêm
analytics: {
  // Đã có: getDashboard, getOverview, getUnansweredQuestions
  // Cần thêm:
  getTrends(days: number): Promise<TrendResponse[]>
  getTopQuestions(limit: number, from?: string, to?: string): Promise<PopularQuestion[]>
  getTopDocuments(limit: number): Promise<DocumentPopularity[]>
  getDepartmentStats(deptId: string, date: string): Promise<DepartmentStatsResponse>
  getFeedbackAnalysis(from?: string, to?: string): Promise<FeedbackAnalysisResponse>
}

// Reports - thêm mới hoàn toàn
reports: {
  createReport(data: ReportExportRequest): Promise<ReportExportResponse>
  getReportStatus(id: string): Promise<ReportExportResponse>
  downloadReport(id: string): Promise<Blob>
  getMyReports(params?): Promise<{ data: ReportExport[], pagination }>
}

// Audit - thêm mới hoàn toàn
audit: {
  search(params: AuditLogSearchRequest): Promise<{ data: AuditLog[], pagination }>
  getById(id: string): Promise<AuditLog>
}

// Sessions - thêm mới hoàn toàn
sessions: {
  getActiveSessions(): Promise<Session[]>
  revokeSession(sessionId: string): Promise<void>  // Backend có revoke refresh token
}
```

#### 1.3 Update Types
Sửa `types/ai.ts` — thêm `messageId` vào feedback-related types:

```typescript
// Sửa: feedback gửi kèm messageId
interface FeedbackSubmitRequest {
  conversationId: string;
  messageId: string;  // THÊM VÀO
  type: 'LIKE' | 'DISLIKE';
  comment?: string;
}
```

Thêm types mới cho các phần thiếu:
- `types/sessions.ts` — SessionInfo, RevokeSessionRequest
- `types/metadata.ts` — Category, Tag, AccessRule, CreateCategoryRequest, v.v.
- `types/reports.ts` — ReportExportRequest, ReportExportResponse
- `types/audit.ts` — AuditLog, AuditLogSearchRequest

---

### TASK 2: Auth Flows — Hoàn thiện authentication

**Priority**: P0
**Effort**: Small

#### 2.1 Login Page — Cần cải tiến UX
**File**: `app/login/page.tsx`

**Cải tiến**:
- Thêm "Remember me" checkbox
- Thêm link "Quên mật khẩu?" (trỏ đến `/forgot-password`)
- Thêm hiệu ứng focus ring theo design system
- Thêm error message chi tiết (không chỉ "Đăng nhập thất bại" mà phân biệt: "Tài khoản bị khóa", "Sai mật khẩu", "Tài khoản không tồn tại")
- Thêm "Đăng ký" link cho admin tạo tài khoản mới (chỉ admin mới có quyền register, nhưng cần UI)

#### 2.2 Register Page — Cần tạo mới
**File**: `app/register/page.tsx` (route mới)

```
app/register/page.tsx
```

**Chỉ ADMIN mới được truy cập trang này** (kiểm tra role từ auth store, redirect nếu không phải admin).

**Fields**:
- Username (required, unique check)
- Email (required, email format, unique check)
- Password (required, min 8 chars, complexity)
- Confirm Password (required, must match)
- Role (select: USER, MANAGER, ADMIN) — chỉ hiển thị cho ADMIN
- Department (select từ danh sách departments)

**API Call**: `api.auth.register({ username, email, password, role, departmentId })`

**Flow**: Register thành công → redirect `/admin/users` với toast "Tài khoản đã được tạo".

#### 2.3 Forgot Password Page — Cần tạo mới
**File**: `app/forgot-password/page.tsx` (route mới, public)

**Flow**:
1. User nhập email
2. POST `/api/v1/auth/forgot-password` → backend gửi email (chưa có backend)
3. Hiển thị: "Đã gửi email đặt lại mật khẩu đến xxx@xxx.com"
4. User click link trong email → `/reset-password?token=xxx`

**Lưu ý**: Backend hiện tại chưa có endpoint này. Cần implement sau khi backend có.

**UI**: Đơn giản — một input email + button, không cần nhiều complexity.

#### 2.4 Reset Password Page — Cần tạo mới
**File**: `app/reset-password/page.tsx` (route mới, public, requires token from URL)

**Flow**:
1. Validate token từ URL params
2. User nhập password mới + confirm
3. POST `/api/v1/auth/reset-password` với `{ token, newPassword }`
4. Redirect `/login` với toast "Đặt lại mật khẩu thành công"

#### 2.5 Session Management — Cần tạo mới
**File**: `app/sessions/page.tsx` (route: `/sessions`, auth required)

**UI**: Danh sách các phiên đăng nhập đang hoạt động.

**Layout**:
```
┌─ Thiết bị đang sử dụng ─────────────────────────┐
│ 🖥️ Chrome trên Windows — 192.168.1.1          │
│ ⏱️ Đăng nhập lúc 10:30, 21/04/2026            │
│ ✅ Hiện tại                                     │
└─────────────────────────────────────────────────┘

┌─ Các phiên khác ───────────────────────────────┐
│ 📱 Safari trên iPhone — 192.168.1.2           │
│ ⏱️ Đăng nhập lúc 09:15, 21/04/2026            │
│ [Thu hồi]                                     │
└─────────────────────────────────────────────────┘

[Thu hồi tất cả các phiên khác]
```

**API**: `GET /api/v1/auth/sessions` → `Session[]`

**Actions**:
- Revoke một phiên: `POST /api/v1/auth/logout` với `refreshToken` của phiên đó
- Revoke tất cả: `POST /api/v1/auth/logout-all`

**Note**: Backend `AuthController.logout()` nhận `LogoutRequest { refreshToken, rawAccessToken }` — cần truyền đúng.

---

### TASK 3: User Management Pages

**Priority**: P1
**Effort**: Medium

#### 3.1 Profile Page — Cần mở rộng
**File**: `app/profile/page.tsx`

**Hiện trạng**: Có form với fullName, email, department. Không có avatar, phone, position, bio.

**Cải tiến**:

1. **Avatar upload** — Thêm component upload avatar (preview, crop nếu cần)
2. **Thêm fields**: phone, position, bio, employeeCode (nếu backend trả về)
3. **Change Password section** — Thêm form đổi mật khẩu riêng (không dùng chung với profile)
4. **Department change** — Sử dụng `api.users.updateDepartment()` — hiện tại chưa có trong UI
5. **Account status display** — Hiển thị badge trạng thái tài khoản (ACTIVE/DEACTIVATED/REVOKED)

**Layout cải tiến**:
```
┌─ Thông tin cá nhân ─────────────────────────────┐
│ [Avatar]                                        │
│ [Upload Avatar Button]                          │
│                                                 │
│ Họ và tên: [________________]                   │
│ Email:     [________________]  (readonly)       │
│ Số điện thoại: [________________]               │
│ Chức vụ:   [________________]                   │
│ Giới thiệu: [________________]                   │
│                                                 │
│ Phòng ban: [Dropdown________________▼]           │
│                                                 │
│                    [Lưu thay đổi]              │
└─────────────────────────────────────────────────┘

┌─ Bảo mật ───────────────────────────────────────┐
│ Mật khẩu: •••••••• [Đổi mật khẩu]             │
│ Phiên đăng nhập: [Quản lý phiên →]             │
└─────────────────────────────────────────────────┘

┌─ Tài khoản ─────────────────────────────────────┐
│ Trạng thái: [🟢 ACTIVE]                        │
│ Vai trò:   [Quản trị viên]                     │
│ Ngày tham gia: 15/01/2026                      │
└─────────────────────────────────────────────────┘
```

#### 3.2 Users Admin Page — Cần mở rộng
**File**: `app/admin/users/page.tsx`

**Hiện trạng**: Có bảng users với search, pagination, status change. Thiếu nhiều features.

**Cải tiến**:

1. **Filter bar đầy đủ**:
   - Search (username/email)
   - Role filter (Tất cả / USER / MANAGER / ADMIN)
   - Status filter (Tất cả / ACTIVE / DEACTIVATED / REVOKED)
   - Department filter (dropdown từ API hoặc hardcoded list)
   - Date range (created from/to)

2. **User actions menu** (dropdown trên mỗi row):
   - Xem chi tiết → Modal hoặc redirect `/admin/users/[id]`
   - Đổi vai trò (ADMIN)
   - Đổi trạng thái: ACTIVE ↔ DEACTIVATED ↔ REVOKED
   - Xóa user (ADMIN)

3. **Create User button** → `/register` (ADMIN only)

4. **Bulk actions**: Select multiple users → Bulk deactivate/delete (ADMIN only)

5. **User detail modal/page**: Xem chi tiết user (login history count, created date, last active, department)

**API Calls**:
```typescript
// Search users với tất cả filters
api.users.search({ page, limit, search, role, status, departmentId })

// Update status
api.users.updateStatus(userId, status)

// Update role (backend có?)
api.users.updateRole(userId, role)  // Cần check backend

// Delete user
api.users.delete(userId)
```

**Layout cải tiến**:
```
┌─ Quản lý người dùng ───────────────────────────┐
│ [+ Tạo tài khoản]                                │
├──────────────────────────────────────────────────┤
│ 🔍 [Tìm kiếm...] [Vai trò ▼] [Trạng thái ▼]    │
│     [Phòng ban ▼]  [Ngày tạo ▼]  [Xóa lọc]     │
├──────────────────────────────────────────────────┤
│ ☐ | Họ tên | Username | Email | Vai trò | ...  │
│ ☑   Nguyễn Văn A  | nguyenvana | a@email | ADMIN | ...
│ ☐   Trần Thị B    | tranthib   | b@email | USER  | ...
│ ...                                                │
├──────────────────────────────────────────────────┤
│ Hiển thị 1-20 trong 150 người dùng              │
│ [<] [1] [2] [3] ... [8] [>]                      │
└──────────────────────────────────────────────────┘
```

#### 3.3 Departments Page — Cần tạo mới
**File**: `app/admin/departments/page.tsx` (route mới)

**Mục đích**: Admin quản lý departments (xem, không cần CRUD vì seed data)

**UI**: Simple table với departments từ seed data (Engineer, Marketing, Sales, HR, Finance, Operations, Legal).

**Note**: Backend `user-service` có `DataInitializer.java` seed 7 departments mặc định. Không có endpoint CRUD departments trong API Gateway. Chỉ cần display.

---

### TASK 4: Document Management Pages

**Priority**: P1
**Effort**: Large

#### 4.1 Documents List Page — Cần mở rộng
**File**: `app/documents/page.tsx`

**Hiện trạng**: Có bảng với search, status filter, view mode (grid/list). Có UploadModal.

**Cải tiến**:

1. **Filter bar đầy đủ**:
   - Search (title, filename)
   - Status filter: Tất cả / DRAFT / PUBLISHED / ARCHIVED / EXPIRED
   - Category filter (dropdown)
   - File type filter: Tất cả / PDF / DOCX / XLSX / TXT
   - Date range (upload date)
   - Sort: Mới nhất / Cũ nhất / Tên / Kích thước

2. **List view columns**: Checkbox, Title, Category, Tags, Status, Size, Uploaded by, Date, Actions

3. **Grid view**: Card với icon file type, title, category badge, status badge, size, date

4. **Actions** (row actions):
   - Xem chi tiết → `/documents/[id]`
   - Tải về → `api.documents.download()`
   - So sánh (select 2 docs → compare) → `/documents/compare?ids=xxx,yyy`
   - Xóa (ADMIN only) → ConfirmDialog → `api.documents.delete()`

5. **Bulk actions**: Select multiple → Bulk delete (ADMIN only)

6. **Upload button** (ADMIN only): Mở `UploadModal`

**API**: `api.documents.getAll(params)` với params `{ page, limit, search, status, category, fileType, startDate, endDate, sortBy, sortOrder }`

#### 4.2 Document Detail Page — Cần tạo mới
**File**: `app/documents/[id]/page.tsx` (route mới)

**Layout**:
```
┌─ Chi tiết tài liệu ──────────────────────────────┐
│ [← Quay lại danh sách]              [Tải về] [Sửa] [Xóa] │
├──────────────────────────────────────────────────┤
│ 📄 Hướng dẫn quy trình nhân sự.pdf              │
│                                                  │
│ Trạng thái: [🟢 Đã xuất bản]  Version: 3       │
├──────────────────────────────────────────────────┤
│ Thông tin | Phiên bản | So sánh                 │
├──────────────────────────────────────────────────┤
│ Tên file: hieu_nhan_nhan_su_v3.pdf              │
│ Loại: PDF  |  Kích thước: 2.4 MB               │
│ Trang: 45 trang                                  │
│ Ngôn ngữ: Tiếng Việt                            │
│ Ngày tải lên: 15/03/2026                        │
│ Người tải: Nguyễn Văn A                         │
│ Phòng ban: Nhân sự                              │
│ Mô tả: Hướng dẫn quy trình tuyển dụng...       │
│                                                  │
│ Tags: [Nhân sự] [Tuyển dụng] [Quy trình]       │
│                                                  │
│ Quyền truy cập: [🌐 Công khai]                  │
│                                                  │
│ [Tải về]  [Xem trước]  [Chỉnh sửa]            │
└──────────────────────────────────────────────────┘
```

**Tabs**:
- **Thông tin**: Metadata chi tiết
- **Phiên bản**: Version history (xem `/documents/[id]/versions`)
- **So sánh**: Compare với phiên bản khác

**API**: `api.documents.getById(id)`

#### 4.3 Document Versions Page — Cần tạo mới
**File**: `app/documents/[id]/versions/page.tsx` (route mới)

**Layout**:
```
┌─ Lịch sử phiên bản ─────────────────────────────┐
│ Tài liệu: Hướng dẫn quy trình nhân sự.pdf       │
├──────────────────────────────────────────────────┤
│ Ver | Ngày tạo | Người tạo | Thay đổi           │
│ v3  | 15/03/2026 | Nguyễn Văn A | Cập nhật ...  │
│ v2  | 10/02/2026 | Trần Thị B   | Thêm mục 3.2  │
│ v1  | 05/01/2026 | Admin        | Phiên bản đầu  │
├──────────────────────────────────────────────────┤
│ [Xem chi tiết] [Tải về] [So sánh với phiên bản hiện tại] │
└──────────────────────────────────────────────────┘
```

**API**: `api.documents.getVersions(documentId)`

#### 4.4 Policy Comparison Page — Cần tạo mới
**File**: `app/documents/compare/page.tsx` (route: `/documents/compare?ids=xxx,yyy`)

**Flow**:
1. Select 2 documents từ list → truyền IDs qua URL params
2. Hoặc vào trực tiếp page, chọn 2 documents từ dropdown

**Layout**:
```
┌─ So sánh tài liệu ─────────────────────────────┐
│ [Tài liệu 1 ▼] [Tài liệu 2 ▼]                  │
├──────────────────────────────────────────────────┤
│ THÊM                           XÓA              │
│ + Mục 3.1: Quy trình...    - Mục 2.5: Bảo mật  │
│ + Mục 3.2: Yêu cầu...      - Mục 2.6: Bảo vệ   │
│                                                   │
│ THAY ĐỔI                                          │
│ ~ Mục 1.1: "3 ngày" → "5 ngày"                  │
│ ~ Mục 2.1: "100%" → "90%"                        │
└──────────────────────────────────────────────────┘
```

**API**: `api.documents.comparePolicies(doc1Id, doc2Id)`

#### 4.5 UploadModal — Cần cải thiện UX
**File**: `components/documents/UploadModal.tsx`

**Cải tiến UX**:

1. **Step 1 (Select)**: Drag & drop zone cần rõ ràng hơn, hiển thị file info sau khi chọn
2. **Step 2 (Review)**: Hiện AI suggestion với confidence indicator
3. **Progress bar**: Hiển thị upload progress (sử dụng Axios onUploadProgress)
4. **Error handling**: Retry button cho AI suggestion failure
5. **Cancel flow**: Nếu user đóng modal khi đang upload → confirm dialog "Bạn có muốn hủy không?"

**Fix bug**: Sau khi confirm metadata thành công, cần gọi `onSuccess` callback để refresh document list.

#### 4.6 Process Document Trigger — Cần tạo mới
**File**: `app/admin/documents/[id]/process/page.tsx` hoặc integrate vào detail page

**Mục đích**: Admin trigger processing pipeline cho document đang ở trạng thái UPLOADED.

**UI**:
```
┌─ Xử lý tài liệu ────────────────────────────────┐
│ Tài liệu: Hướng dẫn quy trình nhân sự.pdf       │
│ Trạng thái: Đã tải lên (chờ xử lý)              │
├──────────────────────────────────────────────────┤
│ Pipeline:                                        │
│ ☑ Tải lên (Hoàn thành)                         │
│ ☑ Xác nhận metadata (Hoàn thành)                 │
│ ☐ Phân tích nội dung (Đang xử lý...)  [40%]      │
│ ☐ Tách chunks                                    │
│ ☐ Tạo embeddings                                 │
│ ☐ Lập chỉ mục                                   │
├──────────────────────────────────────────────────┤
│ Job ID: abc-123-xyz                              │
│ Bắt đầu: 21/04/2026 10:30                       │
│ Thời gian: 2 phút 30 giây                        │
│                                                   │
│ [Xem logs]  [Hủy xử lý]  [Xử lý lại]           │
└──────────────────────────────────────────────────┘
```

**API**: `api.documents.getProcessingJob(documentId)` (polling mỗi 3s)

---

### TASK 5: Metadata Management Pages

**Priority**: P2
**Effort**: Medium

#### 5.1 Categories Admin Page — Cần tạo mới
**File**: `app/admin/metadata/categories/page.tsx` (route mới)

**Features**:
- Table: Name, Slug, Parent Category, Display Order, Status, Actions
- Create category (modal): Name, Slug (auto-generate), Description, Parent (dropdown), Display Order, Icon
- Edit category
- Delete/Deactivate category (confirm dialog)

**RBAC**: ADMIN only

**API**:
```typescript
api.metadata.getAllCategories()     // GET /api/v1/categories
api.metadata.createCategory(data) // POST /api/v1/categories
api.metadata.updateCategory(id, data) // PUT /api/v1/categories/{id}
api.metadata.deleteCategory(id)    // DELETE /api/v1/categories/{id}
```

#### 5.2 Tags Admin Page — Cần tạo mới
**File**: `app/admin/metadata/tags/page.tsx` (route mới)

**Features**:
- Table: Name, Slug, Color, Usage Count, Actions
- Create tag (modal): Name, Color (color picker)
- Edit tag
- Delete tag
- Popular tags section (top 20 by usage count)

**RBAC**: ADMIN only

**API**:
```typescript
api.metadata.getAllTags()          // GET /api/v1/tags
api.metadata.createTag(data)       // POST /api/v1/tags
api.metadata.updateTag(id, data)    // PUT /api/v1/tags/{id}
api.metadata.deleteTag(id)         // DELETE /api/v1/tags/{id}
```

#### 5.3 Access Rules Page — Cần tạo mới
**File**: `app/admin/access-rules/page.tsx` (route mới)

**Features**:
- List all access rules
- Filter by document, role, department, user
- Create rule (modal): Document (searchable select), Type (Role/Department/User), Target, Permission (READ/VIEW)
- Delete rule

**RBAC**: ADMIN only

**API**:
```typescript
api.metadata.getAccessRules(documentId)   // GET /api/v1/access-rules?documentId=xxx
api.metadata.createAccessRule(data)     // POST /api/v1/access-rules
api.metadata.deleteAccessRule(id)       // DELETE /api/v1/access-rules/{id}
```

#### 5.4 Metadata Sidebar — Cần cải tiến
**Cải tiến**: Thêm tab "Metadata" trong Sidebar cho ADMIN.

```typescript
const adminItems: NavItem[] = [
  // ... existing
  { label: 'Quản lý người dùng', href: '/admin/users', roles: [ADMIN] },
  { label: 'Danh mục', href: '/admin/metadata/categories', roles: [ADMIN] },
  { label: 'Nhãn', href: '/admin/metadata/tags', roles: [ADMIN] },
  { label: 'Quyền truy cập', href: '/admin/access-rules', roles: [ADMIN] },
  { label: 'Nhật ký hệ thống', href: '/admin/audit-logs', roles: [ADMIN] },
];
```

---

### TASK 6: Analytics & Reporting Pages

**Priority**: P1
**Effort**: Medium

#### 6.1 Analytics Dashboard — Cần mở rộng
**File**: `app/analytics/page.tsx`

**Hiện trạng**: Có `DashboardStats` display nhưng chỉ là skeleton.

**Cải tiến**:

1. **Stat cards row** (4 cards):
   - Tổng câu hỏi (icon: MessageSquare)
   - Tỷ lệ hài lòng (icon: ThumbsUp)
   - Tài liệu đang hoạt động (icon: BookOpen)
   - Người dùng đang hoạt động (icon: Users)

2. **Charts section**:
   - Line chart: Câu hỏi theo ngày (7/30 ngày)
   - Pie/Donut chart: Tỷ lệ LIKE/DISLIKE
   - Bar chart: Top 5 câu hỏi phổ biến
   - Bar chart: Top 5 tài liệu được trích dẫn

3. **Quick stats table**:
   - Top câu hỏi phổ biến nhất
   - Tài liệu được hỏi nhiều nhất
   - Thời gian phản hồi trung bình

4. **Period selector**: Hôm nay / 7 ngày / 30 ngày / Tùy chỉnh

**Sử dụng thư viện chart**: Chọn một trong:
- `recharts` (đơn giản, nhẹ, React-native friendly)
- `chart.js` + `react-chartjs-2`

**RBAC**: MANAGER, ADMIN

**API**:
```typescript
api.analytics.getDashboard()         // DashboardStats + overview
api.analytics.getOverview()           // AnalyticsOverview
api.analytics.getTrends(days)         // TrendResponse[]
```

#### 6.2 Reports Page — Cần tạo mới
**File**: `app/analytics/reports/page.tsx` (route mới)

**Features**:

1. **Create Report section**:
   - Report type selector (tabs/cards):
     - Tổng quan sử dụng (USAGE_SUMMARY)
     - Phân tích câu hỏi (QUESTION_ANALYTICS)
     - Phân tích phản hồi (FEEDBACK_ANALYSIS)
     - Engagement người dùng (USER_ENGAGEMENT)
     - Tài liệu phổ biến (DOCUMENT_POPULARITY)
     - Câu hỏi chưa trả lời (UNANSWERED_QUESTIONS)
     - Phân tích theo phòng ban (DEPARTMENT_BREAKDOWN)
   - Format: CSV / JSON
   - Date range: from → to
   - Department filter (optional)
   - [Tạo báo cáo] button

2. **My Reports table**:
   - Report name, Type, Format, Status, Created, Actions
   - Status badges: 🟡 Đang tạo / 🟢 Hoàn thành / 🔴 Thất bại
   - Actions: Tải về (nếu COMPLETED), Xóa

3. **Download**: `GET /api/v1/reports/{id}/download` → save as file

**RBAC**: MANAGER, ADMIN

**API**:
```typescript
api.reports.createReport(data)     // POST /api/v1/reports
api.reports.getReportStatus(id)    // GET /api/v1/reports/{id}
api.reports.downloadReport(id)     // GET /api/v1/reports/{id}/download → Blob
api.reports.getMyReports(params)  // GET /api/v1/reports
```

#### 6.3 Unanswered Questions Page — Cần tạo mới
**File**: `app/admin/unanswered/page.tsx` (route: `/admin/unanswered`)

**Hiện trạng**: Có trong `analytics/page.tsx` nhưng gọi sai endpoint.

**Features**:
- Table: Câu hỏi, Người hỏi, Phòng ban, Số lần hỏi, Ngày đầu tiên, Ngày gần nhất, Trạng thái, Actions
- Filter: Trạng thái (PENDING / REVIEWING / ANSWERED / REJECTED), Department, Date range
- Search: Tìm kiếm trong câu hỏi
- Action: Đánh dấu đã trả lời → Mở modal nhập câu trả lời

**RBAC**: MANAGER, ADMIN

**API**:
```typescript
api.analytics.getUnansweredQuestions(params)  // GET /api/v1/ai/unanswered
// Backend có: PUT /api/v1/ai/unanswered/{id}/resolve (cần thêm vào frontend)
// Hoặc: POST /api/v1/feedback/unanswered/{id}/resolve
```

#### 6.4 Department Analytics Page — Cần tạo mới
**File**: `app/analytics/departments/[id]/page.tsx` (route mới)

**Features**:
- Department stats: câu hỏi, users active, likes/dislikes, satisfaction rate
- Chart: Câu hỏi theo ngày cho department
- Top câu hỏi trong department
- Top tài liệu được trích dẫn bởi department

**RBAC**: MANAGER, ADMIN

**API**: `api.analytics.getDepartmentStats(deptId, date)`

---

### TASK 7: Audit Logs Page

**Priority**: P2
**Effort**: Small

#### 7.1 Audit Logs Page — Cần tạo mới
**File**: `app/admin/audit-logs/page.tsx` (route mới)

**Features**:
- Table: Thời gian, Người dùng, Hành động, Tài nguyên, IP, Actions
- Filters: Action type, User, Resource type, Date range
- Search: Tìm kiếm trong resource name
- Pagination

**Action badges by color**:
- 🟢 Login/Logout → success
- 🔵 Create/Update → info
- 🟡 Password change → warning
- 🟠 Deactivate/Revoke → warning
- 🔴 Delete/Revoke → destructive

**RBAC**: ADMIN only

**API**:
```typescript
api.audit.search(params)    // GET /api/v1/analytics/audit-logs
api.audit.getById(id)      // GET /api/v1/analytics/audit-logs/{id}
```

---

### TASK 8: Settings & System Pages

**Priority**: P3
**Effort**: Small

#### 8.1 Settings Page — Cần tạo mới
**File**: `app/admin/settings/page.tsx` (route mới)

**Sections**:
1. **Thông tin hệ thống**: Version, Environment, Uptime
2. **Cấu hình**: (chỉ display, chưa có API để sửa)
   - Rate limits
   - Document upload limits
   - Cleanup schedules
3. **Ngôn ngữ giao diện**: (nếu implement i18n sau này)

**RBAC**: ADMIN only

#### 8.2 Admin Dashboard Redirect
**Cải tiến**: Khi ADMIN truy cập `/admin`, redirect đến `/admin/users` (hiện tại không có `/admin` page).

```typescript
// app/admin/page.tsx hoặc redirect
router.replace('/admin/users');
```

---

### TASK 9: Layout & Navigation Improvements

**Priority**: P1
**Effort**: Small

#### 9.1 Update Sidebar Navigation
Thêm các items mới:

```typescript
const adminItems: NavItem[] = [
  { label: 'Quản lý người dùng', href: '/admin/users', icon: <Users />, roles: [ADMIN] },
  { label: 'Quản lý tài liệu', href: '/admin/documents', icon: <FileText />, roles: [ADMIN] },
  { label: 'Danh mục', href: '/admin/metadata/categories', icon: <FolderOpen />, roles: [ADMIN] },
  { label: 'Nhãn', href: '/admin/metadata/tags', icon: <Tag />, roles: [ADMIN] },
  { label: 'Quyền truy cập', href: '/admin/access-rules', icon: <Shield />, roles: [ADMIN] },
  { label: 'Nhật ký hệ thống', href: '/admin/audit-logs', icon: <ScrollText />, roles: [ADMIN] },
  { divider: true },
  { label: 'Câu hỏi chưa trả lời', href: '/admin/unanswered', icon: <HelpCircle />, roles: [ADMIN, MANAGER] },
  { label: 'Xuất báo cáo', href: '/analytics/reports', icon: <FileBarChart />, roles: [ADMIN, MANAGER] },
  { divider: true },
  { label: 'Cài đặt', href: '/admin/settings', icon: <Settings />, roles: [ADMIN] },
];
```

#### 9.2 Breadcrumb Component
Thêm breadcrumb vào tất cả các page (ngoại trừ chat và login):

```typescript
// app/documents/[id]/page.tsx
<Breadcrumb items={[
  { label: 'Tài liệu', href: '/documents' },
  { label: document.title }
]} />
```

#### 9.3 PageHeader Component
Dùng cho tất cả pages để đồng nhất:

```tsx
<PageHeader
  title="Quản lý người dùng"
  description="Quản lý tài khoản và phân quyền người dùng"
  actions={<Button>Thêm người dùng</Button>}
/>
```

#### 9.4 Loading States
Thêm Skeleton loading cho tất cả pages:
- Table: Skeleton rows (5 rows)
- Card: Skeleton card (3 cards)
- Stats: Skeleton stat cards (4 cards)

---

## V. Danh sách files cần tạo mới hoặc cải tiến

### Files cần TẠO MỚI hoàn toàn

| # | File | Type | Priority | Notes |
|---|------|------|----------|-------|
| 1 | `components/ui/button/` | Component | P0 | Design system |
| 2 | `components/ui/input/` | Component | P0 | Design system |
| 3 | `components/ui/select/` | Component | P0 | Design system |
| 4 | `components/ui/badge/` | Component | P0 | Design system |
| 5 | `components/ui/card/` | Component | P0 | Design system |
| 6 | `components/ui/modal/` | Component | P0 | Design system |
| 7 | `components/ui/table/` | Component | P0 | Design system |
| 8 | `components/ui/pagination/` | Component | P0 | Design system |
| 9 | `components/ui/tabs/` | Component | P0 | Design system |
| 10 | `components/ui/avatar/` | Component | P0 | Design system |
| 11 | `components/ui/spinner/` | Component | P0 | Design system |
| 12 | `components/ui/skeleton/` | Component | P0 | Design system |
| 13 | `components/ui/empty-state/` | Component | P0 | Design system |
| 14 | `components/ui/confirm-dialog/` | Component | P0 | Design system |
| 15 | `components/ui/page-header/` | Component | P0 | Design system |
| 16 | `components/ui/stat-card/` | Component | P0 | Design system |
| 17 | `components/ui/breadcrumb/` | Component | P0 | Design system |
| 18 | `components/ui/index.ts` | Export | P0 | Barrel export |
| 19 | `app/register/page.tsx` | Page | P0 | Auth flow |
| 20 | `app/forgot-password/page.tsx` | Page | P1 | Auth flow |
| 21 | `app/reset-password/page.tsx` | Page | P1 | Auth flow |
| 22 | `app/sessions/page.tsx` | Page | P1 | Auth flow |
| 23 | `app/admin/departments/page.tsx` | Page | P2 | User mgmt |
| 24 | `app/documents/[id]/page.tsx` | Page | P1 | Documents |
| 25 | `app/documents/[id]/versions/page.tsx` | Page | P1 | Documents |
| 26 | `app/documents/compare/page.tsx` | Page | P2 | Documents |
| 27 | `app/admin/documents/[id]/process/page.tsx` | Page | P2 | Documents |
| 28 | `app/admin/metadata/categories/page.tsx` | Page | P2 | Metadata |
| 29 | `app/admin/metadata/tags/page.tsx` | Page | P2 | Metadata |
| 30 | `app/admin/access-rules/page.tsx` | Page | P2 | Metadata |
| 31 | `app/analytics/reports/page.tsx` | Page | P1 | Analytics |
| 32 | `app/admin/unanswered/page.tsx` | Page | P1 | Analytics |
| 33 | `app/admin/audit-logs/page.tsx` | Page | P2 | Admin |
| 34 | `app/admin/settings/page.tsx` | Page | P3 | Admin |
| 35 | `types/sessions.ts` | Types | P0 | |
| 36 | `types/metadata.ts` | Types | P1 | |
| 37 | `types/reports.ts` | Types | P1 | |
| 38 | `types/audit.ts` | Types | P2 | |
| 39 | `lib/utils.ts` | Utils | P0 | |

### Files cần CẢI TIẾN

| # | File | Changes | Priority |
|---|------|---------|----------|
| 1 | `lib/api.ts` | Consolidate: thêm endpoints thiếu, merge với `services/ai.service.ts`, sửa feedback body | P0 |
| 2 | `app/login/page.tsx` | Cải tiến UX: remember me, forgot password link, error chi tiết | P0 |
| 3 | `app/profile/page.tsx` | Mở rộng: avatar upload, phone, position, bio, change password section, department change | P1 |
| 4 | `app/admin/users/page.tsx` | Mở rộng: filter bar đầy đủ, actions menu, bulk actions, create user link | P1 |
| 5 | `app/documents/page.tsx` | Mở rộng: filter bar đầy đủ, view mode cải thiện, actions menu | P1 |
| 6 | `components/documents/UploadModal.tsx` | Cải tiến UX: progress bar, retry, cancel confirm, success callback | P1 |
| 7 | `app/analytics/page.tsx` | Mở rộng: charts, stat cards, period selector, top questions/docs | P1 |
| 8 | `components/layout/Sidebar.tsx` | Thêm navigation items mới | P1 |
| 9 | `types/ai.ts` | Thêm `messageId` vào feedback request | P0 |
| 10 | `store/auth-store.ts` | Thêm helper: `useDepartment`, `useDepartmentId` | P2 |
| 11 | `app/admin/page.tsx` | Tạo redirect → `/admin/users` | P1 |

### Files cần XÓA

| # | File | Lý do |
|---|------|--------|
| 1 | `services/ai.service.ts` | Duplicate với `lib/api.ts` |
| 2 | `services/api-client.ts` | Logic đã merge vào `lib/api.ts` |
| 3 | `interfaces/models/` | Thay bằng `types/` (consolidate) |

---

## VI. Implementation Order (Sprint Planning)

### Sprint 1: Foundation (1 tuần)
**Goal**: Design System + API consolidation + Auth flows

1. Xây dựng base UI components (Button, Input, Select, Badge, Card, Modal, Table, Pagination)
2. Consolidate `lib/api.ts` + xóa duplicates
3. Fix critical API bugs (feedback thiếu messageId)
4. Cải tiến Login page
5. Tạo Register page
6. Tạo Forgot Password + Reset Password pages

### Sprint 2: Core User Features (1 tuần)
**Goal**: User management + Profile

1. Cải tiến Profile page (avatar, fields mới)
2. Cải tiến Admin Users page (filters, actions)
3. Tạo Sessions page
4. Tạo Departments page
5. Breadcrumb + PageHeader components

### Sprint 3: Document Management (1 tuần)
**Goal**: Full document lifecycle

1. Cải tiến Documents List page
2. Tạo Document Detail page
3. Tạo Document Versions page
4. Cải tiến UploadModal
5. Tạo Policy Comparison page

### Sprint 4: Analytics & Reporting (1 tuần)
**Goal**: Analytics + Reports

1. Cải tiến Analytics Dashboard (charts, stat cards)
2. Tạo Reports page
3. Tạo Unanswered Questions page
4. Tạo Audit Logs page

### Sprint 5: Metadata & Polish (1 tuần)
**Goal**: Admin metadata + Polish

1. Tạo Categories page
2. Tạo Tags page
3. Tạo Access Rules page
4. Tạo Settings page
5. Loading states (skeleton)
6. Empty states
7. Polish UX: animations, transitions

---

## VII. Dependencies & Prerequisites

### Trước Sprint 1

1. **Backend fix**: Thêm endpoint `/api/v1/auth/forgot-password` và `/api/v1/auth/reset-password` (hiện chưa có)
2. **Backend fix**: Feedback cần nhận `messageId` (đang thiếu)
3. **Backend**: Verify `/api/v1/ai/history` vs `/api/v1/ai/conversations` endpoint
4. **Decide**: Dùng `recharts` hay `chart.js` cho charts

### Sau mỗi Sprint

1. Chạy `pnpm lint` và fix tất cả errors
2. Test trên cả mobile và desktop
3. Verify RBAC: test từng role (USER, MANAGER, ADMIN)
4. Test error handling (network errors, 401, 403, 404, 500)

---

## VIII. Naming Conventions

### Routes
- Route segments lowercase, hyphenated: `/admin/audit-logs`
- Dynamic segments: `[id]`, `[id]/versions`
- Route groups: `(auth)/`, `(main)/`, `(admin)/`

### Components
- PascalCase: `PageHeader.tsx`, `StatCard.tsx`
- Compound components: `Table.Row`, `Table.Cell` (nếu dùng compound pattern)

### State
- Zustand stores: `{domain}-store.ts` → `auth-store.ts`
- Store hooks: `useAuthStore` (auto-generated patterns)
- State variables: `camelCase`

### CSS Classes
- CSS Modules: `.pageHeader`, `.statCard`, `.tableCell`
- CSS Variables: kebab-case `--primary-color`

### API
- Methods: camelCase: `getDocuments`, `updateStatus`
- Response types: PascalCase: `DocumentResponse`, `UserListResponse`

---

## IX. Key Backend Issues to Resolve First

Trước khi implement frontend, cần xác nhận từ backend team:

1. **AI Q&A service**: Khi nào `ai-qa-service` được implement? Frontend chat UI có thể build trước với mock data.

2. **Feedback endpoint**: Backend `FeedbackController` nhận `messageId` nhưng frontend gọi không truyền. Cần fix backend hoặc fix frontend.

3. **Document search**: Backend `DocumentController` có `list()` endpoint nhưng cần xác nhận query params chính xác.

4. **Report PDF/XLSX**: Backend chỉ có CSV/JSON hoạt động. Frontend cần hiển thị đúng status.

5. **AI streaming**: Backend có định nghĩa `/ai/chat/stream` (SSE) trong Gateway nhưng service không có. Frontend streaming UI đã có.

---

## X. Success Criteria

Mỗi sprint kết thúc khi:

- [ ] Tất cả components/pages có UI hoàn chỉnh (không placeholder, không TODO)
- [ ] Tất cả API calls được kết nối và xử lý error đúng
- [ ] RBAC được test đầy đủ (USER/MANAGER/ADMIN)
- [ ] Loading states cho tất cả async operations
- [ ] Error states (network error, 404, 403, 500) được handle hiển thị
- [ ] Empty states cho tất cả list pages
- [ ] Mobile responsive cho tất cả pages
- [ ] Không có TypeScript errors
- [ ] `pnpm lint` không có warnings
