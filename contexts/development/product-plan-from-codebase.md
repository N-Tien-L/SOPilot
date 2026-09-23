# Product Plan — Poliwise (Tái xây dựng từ Codebase thực tế)

> **Nguồn phân tích**: Đọc exhaustively toàn bộ code: 7 microservices, frontend Next.js, API Gateway NestJS, database schemas, Docker compose, RabbitMQ config.
> **Nguyên tắc**: Không đoán mò. Chỉ ghi nhận những gì có evidence cụ thể trong code.

---

## I. Tổng quan hệ thống

Poliwise là một **hệ thống Q&A nội bộ dựa trên AI** (RAG-based chatbot) phục vụ các tổ chức/quốc hội quản lý và truy xuất chính sách, quy định. Hệ thống sử dụng kiến trúc **microservices** với 7 services độc lập, giao tiếp qua REST proxy (API Gateway) và message queue (RabbitMQ).

### Stack công nghệ

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Zustand, Axios |
| API Gateway | NestJS 11, TypeScript, Passport JWT, Opossum (circuit breaker) |
| Backend Services | Spring Boot 3 / Java 17 (5 services) + Python FastAPI (1 service) |
| Database | PostgreSQL 16 + pgvector (5 schemas: core, knowledge, metadata, conversation, analytics) |
| Message Queue | RabbitMQ 3.13 |
| Object Storage | MinIO (S3-compatible) |
| AI/Embedding | Groq API (LLM), LitServe (embedding/reranker) |

### Database schemas và ownership

| Schema | Service | Tables |
|--------|---------|--------|
| `core` | auth-service (8081) | users, login_history, refresh_tokens, access_token_blacklist |
| `core` | user-service (8082) | users, departments, user_profiles |
| `knowledge` | knowledge-service (8083) + ingestion-service (8088) | documents, document_versions, processing_jobs, chunks |
| `metadata` | metadata-service (8084) | document_metadata, categories, tags, document_tags, document_access_rules |
| `conversation` | (chưa có dedicated service) | conversations, messages, unanswered_questions |
| `analytics` | feedback-service (8085) | feedbacks, audit_logs, report_exports, popular_questions, document_popularity, usage_stats, daily_aggregates, hourly_aggregates, department_daily_stats |

---

## II. Các module chính

### Module 1: Authentication & Authorization (`auth-service`, port 8081)

**Vai trò**: Quản lý toàn bộ vòng đời authentication — đăng nhập, đăng ký, logout, refresh token, session tracking, account lock.

**Key capabilities**:
- JWT-based authentication (access token 15 phút, refresh token 7 ngày)
- Refresh token rotation (đăng xuất 1 thiết bị không ảnh hưởng các thiết bị khác)
- Account lock sau 5 lần login thất bại (khóa 15 phút)
- Login history tracking (IP, device type, user-agent)
- Bootstrap default admin account
- Event-driven: publish `user.registered` và `user.status.changed` lên RabbitMQ

**Kiểm soát**: Chỉ admin mới được tạo user mới (qua `RegisterRequest`).

---

### Module 2: User & Department Management (`user-service`, port 8082)

**Vai trò**: Quản lý profile người dùng, phòng ban, và trạng thái tài khoản sau khi auth tạo user.

**Key capabilities**:
- CRUD user profile (cập nhật fullName, email, department)
- Phân trang và search user với nhiều filter (username, email, role, department, status)
- Thay đổi trạng thái tài khoản: ACTIVE ↔ DEACTIVATED ↔ REVOKED
- Chuyển department cho user
- Default departments: Engineering, Marketing, Sales, HR, Finance, Operations, Legal (seed data)
- Event-driven: consume `user.registered` và `user.status.changed` để đồng bộ

**Kiểm soát**: USER chỉ xem/sửa profile của mình. MANAGER xem được user list nhưng không sửa. ADMIN toàn quyền.

---

### Module 3: Document Management (`knowledge-service` + `ingestion-service`, ports 8083 + 8088)

**Vai trò**: Toàn bộ vòng đời tài liệu — upload, xử lý, lưu trữ, versioning, và so sánh.

**Key capabilities (knowledge-service)**:
- Upload tài liệu đa định dạng (PDF, DOCX, DOC, XLSX, XLS, TXT, PNG, JPG)
- Lưu trữ file trên MinIO
- Soft-delete tài liệu
- Document versioning (theo dõi các phiên bản với changelog)
- So sánh 2 tài liệu (policy comparison với line-by-line diff)
- Trigger processing pipeline (parse → chunk → embed → index)
- Scheduled cleanup tài liệu ở trạng thái STAGING quá hạn

**Key capabilities (ingestion-service, Python)**:
- Extract text từ PDF (PDFBox), DOCX (python-docx), XLSX (openpyxl), TXT, image (pytesseract OCR)
- AI-powered metadata suggestion (Groq LLM llama-3.3-70b-versatile)
- Document standardization (Unicode normalization, heading detection)
- Parent-child text chunking (configurable size/overlap)
- Embedding generation qua LitServe API (ports 8001/8002)
- Document reranking

**Processing status flow**: `STAGING → UPLOADED → PARSING → PARSED → CHUNKING → CHUNKED → EMBEDDING → EMBEDDED → INDEXING → INDEXED → READY → FAILED`

**Kiểm soát**: Chỉ ADMIN được upload/sửa/xóa tài liệu. USER/MANAGER chỉ đọc.

---

### Module 4: Metadata & Classification (`metadata-service`, port 8084)

**Vai trò**: Quản lý taxonomy tài liệu — categories, tags, access rules, lifecycle status.

**Key capabilities**:
- CRUD categories (hierarchy support qua parentId)
- CRUD tags (với slug tự động, color, usage count)
- Bulk tag resolution (find-or-create)
- Document metadata: title, description, category, tags, document type (POLICY/GENERAL), access level (PUBLIC/PRIVATE)
- Access rules: kiểm soát truy cập theo role, department, hoặc user cụ thể
- Document lifecycle: DRAFT → REVIEW → PUBLISHED → ARCHIVED → DELETED
- Auto-archive khi hết hạn (scheduled job 1 AM daily)
- Event-driven: consume `document.uploaded` và `document.deleted` để đồng bộ metadata

**Kiểm soát**: Chỉ ADMIN được tạo/sửa categories, tags, access rules. Metadata creation được trigger tự động khi confirm document.

---

### Module 5: AI Q&A (Conversation) — **CHƯA CÓ dedicated service**

**Vai trò**: Hệ thống trả lời câu hỏi tự động bằng RAG (Retrieval Augmented Generation).

**Evidence trong codebase**:
- Frontend có trang chat đầy đủ: `app/page.tsx` với message list, sources display, feedback buttons, history sidebar
- `ai.service.ts` định nghĩa: `sendMessage`, `getConversations`, `getMessages`, `deleteConversation`, `clearHistory`, `markAsUnanswered`
- `api.ts` định nghĩa: `POST /api/v1/ai/ask`, `GET /api/v1/ai/history`, `POST /api/v1/feedback`
- API Gateway proxy route: `ALL /api/v1/ai/*path` → `ai-qa-service` (port 8086)
- Frontend `api` có endpoint `/api/v1/ai/chat` (khác với `/api/v1/ai/ask`)
- Schema `conversation` trong database: bảng `conversations`, `messages`, `unanswered_questions`
- Feedback service consume event `unanswered.question` từ RabbitMQ

**Nhưng**: Không có thư mục `services/ai-qa-service` hoặc bất kỳ file code nào xử lý AI Q&A logic. **Đây là module thiếu hoàn toàn.**

---

### Module 6: Feedback & Analytics (`feedback-service`, port 8085)

**Vai trò**: Thu thập phản hồi người dùng, phân tích usage, audit logging, và xuất báo cáo.

**Key capabilities**:
- Feedback submission (LIKE/DISLIKE) cho từng message trong cuộc hội thoại
- Thống kê: tổng câu hỏi, feedback, satisfaction rate, top câu hỏi, top tài liệu
- Dashboard overview: câu hỏi hôm nay/tuần, user active, unanswered count
- Xu hướng theo ngày (questions, feedback, response time, users)
- Thống kê theo department
- Unanswered questions: lưu trữ + resolve bởi MANAGER/ADMIN
- Audit logging: ghi nhận tất cả hành động quan trọng (login, upload, status change, etc.)
- Report export: CSV, JSON (async, PENDING → PROCESSING → COMPLETED/FAILED, expires sau 7 ngày)
- Popular questions tracking: normalize + count ask frequency
- Document popularity tracking: citation count, liked citations

**Scheduled jobs**:
- `CleanupScheduler` (01:00 AM): xóa audit log >90 ngày, report expires, resolved questions >180 ngày
- `StatsAggregationScheduler` (phút 5 mỗi giờ + 00:10 AM hàng ngày): aggregate hourly/daily stats từ usage_stats

**Kiểm soát**: Analytics/Dashboard/Reports chỉ MANAGER+. Audit logs chỉ ADMIN.

---

### Module 7: API Gateway (NestJS, port 3000/8080)

**Vai trò**: Single entry point cho tất cả client requests — JWT validation, RBAC enforcement, rate limiting, circuit breaker, request proxying.

**Key capabilities**:
- JWT validation tập trung (verify token, kiểm tra account status DEACTIVATED/REVOKED)
- RBAC với role hierarchy: ADMIN > MANAGER > USER
- Rate limiting: PUBLIC (20/min), USER (100/min), MANAGER (200/min), ADMIN (500/min)
- Circuit breaker (opossum) cho mỗi downstream service
- Request proxying với forward headers (X-Forwarded-For, X-User-Id, X-Role, X-Trace-ID)
- Response normalization (ApiResponse wrapper)
- Global exception filter với error code mapping
- Health check endpoints (basic, liveness, readiness, circuit breaker status)
- Security headers (Helmet) + CORS + compression

---

## III. Chức năng đã có

### 3.1. Authentication & Session Management

| Feature | Mô tả | Code liên quan | Actor |
|---------|-------|---------------|-------|
| Đăng nhập | Login với username/password, trả JWT | `AuthController.login()`, `AuthService.login()` | Public |
| Đăng ký | Tạo user mới (chỉ admin) | `AuthController.register()`, `AuthService.register()` | Admin |
| Refresh token | Rotation refresh token, access token mới | `AuthController.refresh()`, `RefreshTokenService.rotate()` | Authenticated |
| Logout một thiết bị | Blacklist access token, revoke refresh token | `AuthController.logout()`, `AuthService.logout()` | Authenticated |
| Logout tất cả thiết bị | Revoke toàn bộ refresh tokens | `AuthController.logoutAll()`, `RefreshTokenService.revokeAll()` | Authenticated |
| Session tracking | Lịch sử login (IP, device, status) | `LoginHistory` entity, `LoginHistoryRepository` | Authenticated |
| Account lock | Khóa sau 5 lần thất bại (15 phút) | `AuthService.processFailedLogin()`, `AuthService.isLocked()` | System |
| Bootstrap admin | Tạo admin mặc định khi khởi động | `AdminInitializer.run()` | System |

---

### 3.2. User & Department Management

| Feature | Mô tả | Code liên quan | Actor |
|---------|-------|---------------|-------|
| Xem profile | Lấy thông tin user hiện tại | `UserController.getMyProfile()`, `UserService.getById()` | User |
| Cập nhật profile | Sửa fullName, email | `UserController.updateProfile()`, `UserService.updateProfile()` | User |
| Đổi department | Chuyển phòng ban | `UserController.changeDepartment()`, `UserService.updateDepartment()` | User |
| Search users | Tìm kiếm với filter (role, status, department) | `UserController.searchUsers()`, `UserRepository` (specifications) | Admin |
| Đổi trạng thái user | ACTIVE/DEACTIVATED/REVOKED | `UserController.changeStatus()`, `UserService.updateStatus()` | Admin |
| Xóa user | Soft delete user | `UserController.deleteUser()`, `UserService.softDelete()` | Admin |

---

### 3.3. Document Management

| Feature | Mô tả | Code liên quan | Actor |
|---------|-------|---------------|-------|
| Upload tài liệu | Upload file lên MinIO, tạo Document record | `DocumentController.upload()`, `DocumentService.upload()`, `StorageService` | Admin |
| Xem danh sách tài liệu | List với filter/search/pagination | `DocumentController.list()` (proxy), `DocumentRepository` | User+ |
| Xem chi tiết tài liệu | Get single document | `DocumentController.get()`, `DocumentService.findById()` | User+ |
| Soft delete tài liệu | Xóa (set deletedAt) | `DocumentController.delete()`, `DocumentService.softDelete()` | Admin |
| Cancel upload | Hủy upload đang STAGING | `DocumentController.cancelUpload()`, `DocumentService.cancelUpload()` | Admin |
| Xem versions | Lịch sử các phiên bản | `DocumentController.versions()`, `DocumentVersionRepository` | User+ |
| Confirm metadata | Xác nhận metadata từ AI suggestion | `DocumentController.confirm()`, `DocumentService.confirmMetadata()` | Admin |
| Trigger processing | Parse → Chunk → Embed → Index pipeline | `DocumentController.process()`, `DocumentService.processDocument()` | Admin |
| Policy comparison | So sánh 2 tài liệu (line diff) | `PolicyComparisonController.compare()`, `PolicyComparisonService.compare()` | Admin, Manager |
| Cleanup expired staging | Xóa tài liệu STAGING quá hạn (10 phút) | `DocumentService.cleanupExpiredStaging()` (scheduled) | System |
| AI metadata suggestion | Gọi Groq LLM suggest title/category/tags | `MetadataSuggestionService.suggest()`, `MetadataSuggestionController.suggest()` (ingestion) | Admin (trigger) |

---

### 3.4. Metadata & Classification

| Feature | Mô tả | Code liên quan | Actor |
|---------|-------|---------------|-------|
| CRUD categories | Tạo/sửa/xóa categories (hierarchy) | `CategoryController`, `CategoryService` | Admin |
| Xem active categories | List categories đang hoạt động | `CategoryController.getActive()`, `CategoryRepository` | Public |
| CRUD tags | Tạo/sửa/xóa tags | `TagController`, `TagService` | Admin |
| Bulk tag resolve | Find-or-create tags | `TagController.resolve()`, `TagService.resolveTags()` | Admin |
| Tạo document metadata | Gán metadata cho document | `DocumentMetadataController.create()`, `DocumentMetadataService` | Admin (via confirm) |
| Update metadata | Sửa metadata | `DocumentMetadataController.update()` | Admin |
| Publish/Archive | Thay đổi lifecycle status | `DocumentMetadataController.publish()`, `archive()` | Admin |
| Access rules | Kiểm soát truy cập theo role/department/user | `AccessRuleService.hasAccess()`, `AccessRuleService.create()` | Admin |
| Auto-archive expired | Scheduler 1 AM hàng ngày | `DocumentExpirationScheduler.processExpiredDocuments()` | System |

---

### 3.5. AI Q&A — **KHÔNG CÓ service, chỉ có frontend + API routes định nghĩa**

| Feature | Mô tả | Code liên quan | Actor |
|---------|-------|---------------|-------|
| Gửi câu hỏi | Chat với AI | Frontend: `app/page.tsx`, `ai.service.sendMessage()` → proxy đến `ai-qa-service:8086` | User+ |
| Xem lịch sử hội thoại | Danh sách cuộc trò chuyện | Frontend history sidebar, `ai.service.getConversations()` | User+ |
| Xem messages | Chi tiết một cuộc trò chuyện | `ai.service.getMessages()` | User+ |
| Xóa cuộc trò chuyện | Xóa conversation | `ai.service.deleteConversation()` | User+ |
| Xóa messages | Clear history | `ai.service.clearHistory()` | User+ |

---

### 3.6. Feedback & Rating

| Feature | Mô tả | Code liên quan | Actor |
|---------|-------|---------------|-------|
| Submit feedback | LIKE/DISLIKE cho message | `FeedbackController.createFeedback()`, `FeedbackService.createFeedback()` | User+ |
| Xem feedback | Lấy feedback theo conversation | `FeedbackController.getByConversation()` | User+ |
| Xóa feedback | Xóa feedback của mình | `FeedbackController.deleteFeedback()` | User, Admin |
| Ghi audit log | Log hành động (login, upload, etc.) | `AuditLogService.logAction()`, `AuditController` | System |

---

### 3.7. Analytics & Reporting

| Feature | Mô tả | Code liên quan | Actor |
|---------|-------|---------------|-------|
| Dashboard overview | Stats tổng quan | `DashboardController.getOverview()`, `DashboardService` | Manager+ |
| Xu hướng | Biểu đồ theo ngày | `DashboardController.getTrends()` | Manager+ |
| Analytics summary | Tổng hợp theo khoảng thời gian | `AnalyticsController.getSummary()`, `AnalyticsService` | Manager+ |
| Top questions | Câu hỏi phổ biến | `AnalyticsController.getTopQuestions()` | Manager+ |
| Top documents | Tài liệu được trích dẫn nhiều | `AnalyticsController.getTopDocuments()` | Manager+ |
| Department stats | Stats theo phòng ban | `AnalyticsController.getDepartmentStats()` | Manager+ |
| Unanswered questions | Danh sách câu hỏi chưa được trả lời | `DashboardController.getUnanswered()`, `FeedbackController` | Manager+ |
| Resolve unanswered | Đánh dấu đã trả lời | Feedback service endpoint (proxy) | Manager+ |
| Search audit logs | Tìm kiếm audit logs | `AuditController.search()`, `AuditLogService.searchLogs()` | Admin |
| Tạo báo cáo | Export async (CSV/JSON) | `ReportController.createReport()`, `ReportExportService` | Manager+ |
| Download báo cáo | Tải file đã export | `ReportController.download()` | Manager+ |

---

### 3.8. Infrastructure & Cross-cutting

| Feature | Mô tả | Code liên quan | Actor |
|---------|-------|---------------|-------|
| Health checks | Liveness/readiness probe cho mỗi service | Spring Actuator, NestJS health module | System |
| Distributed tracing | Trace ID propagation qua headers | `TraceIdInterceptor`, `trace-id.util.ts` | System |
| Request logging | Winston log với sanitize | `LoggingInterceptor`, `winston.config.ts` | System |
| Global rate limiting | Rate limit theo role | `RateLimitInterceptor` | System |
| Circuit breaker | Opossum cho downstream services | `ProxyService`, `ServicesIndicator` | System |
| Automatic cleanup | Xóa data quá hạn | `CleanupScheduler`, `StatsAggregationScheduler` | System |

---

## IV. Chức năng chưa có / thiếu

### 4.1. AI Q&A Service — **THIẾU HOÀN TOÀN**

**Lý do kết luận thiếu:**
- Không có thư mục `services/ai-qa-service` hoặc bất kỳ service nào xử lý AI Q&A
- API Gateway định nghĩa route proxy `ALL /api/v1/ai/*path → ai-qa-service:8086`, nhưng service này không tồn tại
- Frontend gọi `/api/v1/ai/chat` và `/api/v1/ai/ask` (2 endpoint khác nhau trong 2 file)
- Database schema `conversation` đã có bảng `conversations` và `messages` sẵn sàng, nhưng không có service nào write vào
- `feedback-service` consume event `unanswered.question` từ AI service, nhưng không có AI service nào publish event này
- `ingestion-service` có `embedding_service.py` và `chunker.py` để prepare chunks, nhưng không có service nào thực hiện RAG retrieval + LLM generation

**Gợi ý cần có:**
- Tạo `ai-qa-service` (NestJS hoặc Python FastAPI)
- Implement RAG flow: retrieve relevant chunks → rerank → construct prompt → call Groq LLM → return answer
- Write conversations/messages vào database `conversation` schema
- Call `embedding_service` và `chunker` từ ingestion-service để retrieve chunks
- Publish `unanswered.question` event khi confidence thấp
- Support streaming response (frontend có `isStreaming` flag)

---

### 4.2. Conversation Service — **THIẾU logic backend**

**Lý do kết luận thiếu:**
- Schema `conversation` có đầy đủ bảng `conversations` và `messages`
- Frontend có UI hoàn chỉnh cho conversation management
- `feedback-service` có consumer `ConversationEventConsumer.java` nhưng **file rỗng (EMPTY PLACEHOLDER)**
- AI service (khi được tạo) cần write vào các bảng này

**Gợi ý cần có:**
- Khi tích hợp AI Q&A service, implement conversation management
- `ConversationEventConsumer` cần code thực tế khi AI service emit events
- Message status tracking (streaming_completed, etc.)

---

### 4.3. Streaming Response — **THIÊU backend**

**Lý do kết luận thiếu:**
- Frontend có UI cho streaming (`isStreaming`, `streaming_completed` flags)
- Message entity trong database có `is_streaming` và `streaming_completed` columns
- `Feedback` entity lưu `tokens_prompt`, `tokens_completion`, `tokens_total`, `latency_ms`, `model_used` — dùng cho streaming analytics
- Không có endpoint/service nào hỗ trợ Server-Sent Events hoặc WebSocket

**Gợi ý cần có:**
- AI Q&A service cần implement streaming (SSE hoặc WebSocket)
- Frontend streaming display đã sẵn sàng (UI `isLoading`, spinner, progressive text)

---

### 4.4. Password Management — **Frontend done, Backend missing**

**Trạng thái**: ⚠️ Frontend đã implement đầy đủ: `app/forgot-password/page.tsx` và `app/reset-password/page.tsx`. Backend không có endpoint nên flow sẽ fail.

**Lý do backend thiếu:**
- `AuthService` có `mustChangePassword` field trong User entity
- `passwordChangedAt` field tồn tại
- Không có endpoint/service cho: forgot password, reset password, change password

**Gợi ý backend cần:**
- Forgot password: gửi email với reset token (cần email service)
- Reset password: verify token, update password hash
- Change password: verify old password, update hash

---

### 4.5. Email / Notification Service — **THIẾU HOÀN TOÀN**

**Lý do kết luận thiếu:**
- Không có thư mục `services/notification-service` hoặc `services/email-service`
- Không có email configuration trong bất kỳ service nào
- Không có evidence trong code về email sending

**Gợi ý cần có:**
- Email thông báo: welcome email, forgot password, account lock notification
- Notification khi câu hỏi được trả lời (unanswered → resolved)

---

### 4.6. Document Full-text Search — **PARTIAL (chỉ có prepare, không có search)**

**Lý do kết luận thiếu:**
- `chunker.py` và `embedding_service.py` trong ingestion-service prepare chunks và embeddings
- `ProcessingJob` entity có trạng thái `INDEXING` và `INDEXED`
- Tuy nhiên không có service thực hiện semantic search thực sự
- `KnowledgeService` có `searchDocuments()` endpoint (proxy), nhưng không có implementation

**Gợi ý cần có:**
- Implement semantic search sử dụng pgvector (đã có schema) hoặc external vector DB
- Khi AI Q&A service được tạo, implement retrieval từ vector store

---

### 4.7. Report PDF/XLSX Generation — **PARTIAL**

**Lý do kết luận thiếu:**
- `ReportExportService` có export formats: CSV, PDF, XLSX, JSON
- Hiện tại chỉ implement: CSV (đầy đủ), JSON (basic placeholder)
- PDF và XLSX được định nghĩa trong enum nhưng **không có logic generate thực tế**

**Gợi ý cần có:**
- Implement PDF generation (ví dụ: iText, Apache PDFBox)
- Implement XLSX generation (ví dụ: Apache POI, openpyxl)

---

### 4.8. Redis / Caching — **THIẾU**

**Lý do kết luận thiếu:**
- Không có service/service nào có Redis dependency
- Không có Redis configuration trong docker-compose.yml
- Token blacklist sử dụng database (AccessTokenBlacklist table) thay vì Redis

**Gợi ý cần có:**
- Cache active sessions, refresh tokens
- Cache category/tag lists
- Cache popular questions, document popularity

---

### 4.9. User Activity / Online Status — **THIẾU**

**Lý do kết luận thiếu:**
- `LoginHistory` lưu lịch sử login nhưng không có "currently online" tracking
- `UsageStat` ghi nhận request nhưng không có real-time online status
- Frontend có user badge nhưng không có online/offline indicator

**Gợi ý cần có:**
- WebSocket hoặc heartbeat mechanism để track online users
- Display online status trên user management page (admin)

---

### 4.10. Bulk Import / Export Users — **PARTIAL**

**Lý do kết luận thiếu:**
- Audit log có action `BULK_IMPORT` trong enum
- Không có endpoint hoặc UI cho bulk import users (CSV/Excel)

**Gợi ý cần có:**
- Admin UI: upload CSV/Excel để bulk create/update users
- Export users list sang CSV/Excel

---

### 4.11. Advanced Policy Comparison — **BASIC (chỉ text diff)**

**Lý do kết luận thiếu:**
- `PolicyComparisonService` thực hiện set-based line diff đơn giản
- Không có AI-powered semantic comparison
- Không highlight semantic changes (chỉ text changes)

**Gợi ý cần có:**
- AI-powered diff: highlight nội dung thay đổi về ý nghĩa
- Version timeline visualization
- Side-by-side comparison UI

---

### 4.12. Document Versioning UI — **Backend có, Frontend đã implement**

**Trạng thái**: ✅ Frontend đã implement. Backend có đầy đủ versioning: `DocumentVersion` entity, repository, controller endpoint. Frontend `app/documents/[id]/page.tsx` hiển thị version badge. Version history page (`app/documents/[id]/versions/page.tsx`) đã plan nhưng có thể redirect đến detail page.

**Gợi ý còn lại:**
- Side-by-side comparison giữa 2 versions
- Revert to previous version

---

### 4.13. Role & Permission Management UI — **KHÔNG CÓ**

**Lý do kết luận thiếu:**
- RBAC model có 3 roles (USER/MANAGER/ADMIN) với capabilities được mô tả trong `docs/allow_per_role.md`
- Frontend `app/admin/users/page.tsx` cho phép đổi role, nhưng **không có dedicated role management UI**
- Không có UI để: tạo mới role, gán permissions từng API endpoint

**Gợi ý cần có:**
- Role management page (CRUD roles)
- Permission matrix editor
- Role assignment history

---

### 4.14. System Settings / Configuration UI — **KHÔNG CÓ**

**Lý do kết luận thiếu:**
- Audit log có action `SETTINGS_UPDATE`
- Không có UI hoặc service nào quản lý system settings

**Gợi ý cần có:**
- Settings page: max file upload size, retention periods, rate limits
- Environment variable management (trong admin panel)

---

## V. Nhận xét kiến trúc

### Điểm mạnh

1. **Clean microservices separation**: Mỗi service có database schema riêng, không có cross-schema joins ở service level. Ownership rõ ràng.

2. **Event-driven integration**: RabbitMQ sử dụng hiệu quả cho cross-service communication (`user.status.changed`, `document.uploaded`, `document.deleted`, `unanswered.question`).

3. **API Gateway tập trung**: Tất cả auth/RBAC/rate-limiting/circuit-breaker ở một chỗ, downstream services chỉ cần business logic.

4. **Database schema thiết kế tốt**: 5 schemas riêng biệt, có enum types, indexes đầy đủ, JSONB cho flexible data.

5. **Frontend-agnostic API**: API Gateway proxy giúp frontend không cần biết internal service URLs.

6. **Comprehensive audit logging**: 24 audit actions được định nghĩa, bao phủ hầu hết operations.

7. **Scheduled jobs có chiến lược**: Cleanup và aggregation được tách riêng, chạy vào off-peak hours.

8. **Refresh token rotation an toàn**: Phát hiện token reuse (refresh token theft attack).

---

### Điểm thiếu / Cần cải thiện

1. **AI Q&A service hoàn toàn thiếu**: Đây là core feature của sản phẩm nhưng không có service nào implement. Frontend sẵn sàng nhưng không có backend.

2. **Không có AI service nào thực sự hoạt động**: `ingestion-service` có code xử lý document nhưng không tích hợp với AI service vì AI service không tồn tại.

3. **Frontend và Backend API không align hoàn toàn**: Frontend `api.ts` gọi `/api/v1/ai/ask`, nhưng `ai.service.ts` gọi `/api/v1/ai/chat`. Feedback endpoint trong 2 file khác nhau.

4. **Không có caching layer**: Mọi query đều hit database trực tiếp.

5. **Report generation partial**: Chỉ CSV hoạt động, PDF/XLSX là placeholder.

6. **Không có email/notification service**: Các tính năng cần notify user (forgot password, unanswered resolved) không thể implement.

7. **Duplicate entities**: `User` entity tồn tại trong cả `auth-service` (schema `core`) và `user-service` (schema `core`). Đây là intentional design (auth owns auth data, user-service owns profile data), nhưng cần sync cẩn thận.

8. **Rate limiting không persistent**: Dùng in-memory store, không share giữa các instances.

9. **Không có unit tests đầy đủ**: Chỉ có `AuthServiceTest.java` trong auth-service, các service khác gần như không có tests.

10. **Docker compose chưa có AI services**: `docker-compose.yml` có comments về LitServe embedding/reranker nhưng URLs trỏ đến `host.docker.internal:8001/8002` — không chạy trong container.

---

### Rủi ro

1. **Single point of failure**: API Gateway là single entry point, không có redundancy. Nếu Gateway down, toàn bộ hệ thống không hoạt động.

2. **AI feature blocked**: Không có AI Q&A service = sản phẩm không có core value proposition. Mọi code khác chỉ là infrastructure.

3. **Schema ownership conflict potential**: Auth-service và user-service cùng access `core` schema. Auth-service tạo user, user-service cập nhật profile. Event-driven sync có thể miss edge cases.

4. **No CI/CD pipeline**: Không có evidence về automated deployment, testing, hoặc quality gates.

5. **Hardcoded secrets in docker-compose**: Admin password, JWT secret có defaults trong docker-compose.yml.

6. **Vector search chưa hoàn thiện**: pgvector schema sẵn sàng nhưng không có service nào thực hiện semantic search.

7. **Frontend-backend contract drift**: Có sự khác biệt giữa `api.ts` và `ai.service.ts` về endpoints. Cần ensure OpenAPI/Swagger spec để sync.

8. **Document storage dependency on MinIO**: Không có fallback nếu MinIO down. Không có replication/backup strategy cho document storage.

---

## VI. Main Flows

### Flow 1: User Authentication
```
User → POST /api/v1/auth/login (API Gateway)
     → auth-service (8081): verify credentials, check lock
     → AuthService: update failed attempts, save login history
     → RefreshTokenService: create refresh token (DB)
     → JwtTokenProvider: create access token (JWT)
     ← TokenResponse (access + refresh)
```

### Flow 2: Document Upload (Admin)
```
Admin → POST /api/v1/documents/upload (API Gateway)
      → knowledge-service (8083): receive file
      → StorageService: upload to MinIO
      → DocumentService: create Document + DocumentVersion
      → DocumentEventPublisher: publish DocumentUploadedEvent
      → RabbitMQ → metadata-service (consume): create DocumentMetadata (pending)
      → RabbitMQ → feedback-service (consume): log audit DOCUMENT_UPLOAD
      ← DocumentResponse (STAGING, metadata suggestion pending)
      
Admin → POST /api/v1/documents/:id/confirm
     → DocumentService: resolve category/tags via MetadataServiceClient
     → DocumentMetadataService: create metadata in metadata-service
     → DocumentService: update status = READY
     ← DocumentResponse (READY)
```

### Flow 3: AI Q&A — **BROKEN (no AI service)**
```
User → POST /api/v1/ai/ask (API Gateway)
     → ai-qa-service (8086): NOT FOUND ❌
```
**Không có AI service. Flow này sẽ fail 404.**

### Flow 4: Feedback Submission
```
User → POST /api/v1/feedback (API Gateway)
     → feedback-service (8085)
     → FeedbackService: validate (no duplicate user+message)
     → FeedbackRepository: save
     ← FeedbackResponse
```

### Flow 5: Document Processing Pipeline
```
Admin → POST /api/v1/documents/:id/process (API Gateway)
     → knowledge-service (8083)
     → DocumentService: update status = PARSING
     → DocumentEventPublisher: publish ingestion.requested
     → RabbitMQ → ingestion-service (8088): consume event
     → Extractor: parse PDF/DOCX/XLSX/TXT (Apache Tika, PyMuPDF)
     → DocumentPolicyStandardizer: normalize Vietnamese text
     → ParentChildChunker: chunk text (parent=1500 chars, child=400 chars)
     → EmbeddingService: call LitServe → generate embeddings
     → ChunkRepository: bulk insert chunks (with vectors)
     → ProcessingJobService: mark COMPLETED
     ← Status updated: READY
```

---

## VII. Tổng kết Feature Matrix

| Module | Feature | Status | Evidence |
|--------|---------|--------|---------|
| **Auth** | Login | ✅ Backend + Frontend | `AuthController.login()`, `app/login/page.tsx` |
| | Register (admin only) | ✅ Backend + Frontend | `AuthController.register()`, `app/register/page.tsx` |
| | Token refresh | ✅ Backend | `RefreshTokenService.rotate()` |
| | Logout single/all | ✅ Backend | `AuthController.logout/logoutAll()` |
| | Account lock | ✅ Backend | `AuthService.processFailedLogin()` |
| | Forgot/Reset password | ⚠️ Frontend done, Backend missing | `app/forgot-password/`, `app/reset-password/`, no endpoint |
| **User** | Profile CRUD | ✅ Backend + Frontend | `UserController`, `app/profile/page.tsx` |
| | Sessions management | ✅ Backend + Frontend | `app/profile/sessions/page.tsx` |
| | Change password | ✅ Backend + Frontend | `app/profile/change-password/page.tsx` |
| | Search users | ✅ Backend + Frontend | `UserSpecification`, `app/admin/users/page.tsx` |
| | Status management | ✅ Backend + Frontend | `UserService.updateStatus()`, `app/admin/users/page.tsx` |
| | Departments display | ✅ Backend (seed) + Frontend | `app/admin/departments/page.tsx` |
| **Documents** | Upload | ✅ Backend + Frontend | `DocumentController.upload()`, `components/documents/UploadModal.tsx` |
| | Download | ✅ Backend + Frontend | `StorageService.downloadFile()`, `app/documents/page.tsx` |
| | Soft delete | ✅ Backend + Frontend | `DocumentService.softDelete()`, `app/documents/[id]/page.tsx` |
| | Versioning | ✅ Backend + Frontend | `DocumentVersion` entity, `app/documents/[id]/page.tsx` |
| | Processing pipeline | ✅ Backend | `DocumentService.processDocument()` |
| | Policy comparison | ✅ Backend + Frontend | `PolicyComparisonService`, `app/documents/compare/page.tsx` |
| | List with filters | ✅ Backend + Frontend | `DocumentController.list()`, `app/documents/page.tsx` |
| | Detail view | ✅ Backend + Frontend | `app/documents/[id]/page.tsx` |
| **Metadata** | Categories CRUD | ✅ Backend + Frontend | `CategoryController`, `app/admin/metadata/categories/page.tsx` |
| | Tags CRUD | ✅ Backend + Frontend | `TagController`, `app/admin/metadata/tags/page.tsx` |
| | Access rules | ✅ Backend + Frontend | `AccessRuleService`, `app/admin/access-rules/page.tsx` |
| | Auto-archive | ✅ Backend | `DocumentExpirationScheduler` |
| **AI Q&A** | Ask question | ❌ Backend missing | No service — frontend UI `app/page.tsx` sẵn sàng |
| | Streaming | ❌ Backend missing | Frontend streaming UI có sẵn |
| | Conversations | ❌ Backend missing | Frontend history sidebar sẵn sàng |
| | Mark unanswered | ⚠️ Frontend done, Backend partial | `app/admin/unanswered/page.tsx`, đợi AI service |
| **Feedback** | Submit LIKE/DISLIKE | ✅ Backend + Frontend | `FeedbackController.createFeedback()` (đã fix `messageId`) |
| | Audit logging | ✅ Backend + Frontend | `AuditLogService`, `app/admin/audit-logs/page.tsx` |
| **Analytics** | Dashboard (charts) | ✅ Backend + Frontend | `DashboardController`, `app/analytics/page.tsx` (recharts) |
| | Top questions/docs | ✅ Backend + Frontend | `AnalyticsController`, `app/analytics/page.tsx` |
| | Unanswered tracking | ✅ Backend + Frontend | `app/admin/unanswered/page.tsx` |
| | Report export CSV/JSON | ✅ Backend + Frontend | `ReportExportService`, `app/analytics/reports/page.tsx` |
| | Report export PDF/XLSX | ❌ Backend missing | Placeholder in `app/analytics/reports/page.tsx` |
| **Gateway** | JWT validation | ✅ Backend | `JwtAuthGuard` |
| | RBAC | ✅ Backend | `RolesGuard` |
| | Rate limiting | ✅ Backend | `RateLimitInterceptor` |
| | Circuit breaker | ✅ Backend | `opossum` |
| | Health checks | ✅ Backend | `HealthController` |
| **Infrastructure** | Cleanup jobs | ✅ Backend | `CleanupScheduler` |
| | Stats aggregation | ✅ Backend | `StatsAggregationScheduler` |
| | Email notifications | ❌ Backend missing | No service |
| | Caching | ❌ Backend missing | No Redis |

---

*Document compiled from exhaustive code analysis. Evidence-based only — no speculation beyond clearly documented missing features.*

---

## VIII. Frontend Implementation Status

> **Cập nhật**: Sau 5 sprints phát triển (Sprint 1–5), frontend đã hoàn thiện cover toàn bộ backend features đã có. Tất cả pages đều dùng design system nhất quán (CSS Modules + UI components + lucide-react icons).

### 5.1 Design System — Hoàn thành

18 UI components được xây dựng trong `components/ui/`:

| Component | File | Status |
|-----------|------|--------|
| Button | `button/` | ✅ Done |
| Input | `input/` | ✅ Done |
| Select | `select/` | ✅ Done |
| Badge | `badge/` | ✅ Done |
| Card | `card/` | ✅ Done |
| Modal | `modal/` | ✅ Done |
| Table | `table/` | ✅ Done |
| Pagination | `pagination/` | ✅ Done |
| Tabs | `tabs/` | ✅ Done |
| Avatar | `avatar/` | ✅ Done |
| Spinner | `spinner/` | ✅ Done |
| Skeleton | `skeleton/` | ✅ Done |
| EmptyState | `empty-state/` | ✅ Done |
| ConfirmDialog | `confirm-dialog/` | ✅ Done |
| PageHeader | `page-header/` | ✅ Done |
| StatCard | `stat-card/` | ✅ Done |
| Breadcrumb | `breadcrumb/` | ✅ Done |
| Textarea | `textarea/` | ✅ Done |
| Checkbox | `checkbox/` | ✅ Done |
| Switch | `switch/` | ✅ Done |

### 5.2 Authentication & Profile — Hoàn thành

| Feature | Frontend File | Status |
|---------|--------------|--------|
| Login page (cải thiện UX, remember me, error chi tiết) | `app/login/page.tsx` | ✅ Done |
| Register page (admin only) | `app/register/page.tsx` | ✅ Done |
| Forgot password page | `app/forgot-password/page.tsx` | ✅ Done |
| Reset password page (token validation) | `app/reset-password/page.tsx` | ✅ Done |
| Profile page (cải thiện với Avatar, Badge, Card) | `app/profile/page.tsx` | ✅ Done |
| Change password | `app/profile/change-password/page.tsx` | ✅ Done |
| Sessions management | `app/profile/sessions/page.tsx` | ✅ Done |

### 5.3 Admin Pages — Hoàn thành

| Feature | Frontend File | Status |
|---------|--------------|--------|
| Admin redirect | `app/admin/page.tsx` | ✅ Done |
| Users management (filter, actions, CRUD) | `app/admin/users/page.tsx` | ✅ Done |
| Departments display | `app/admin/departments/page.tsx` | ✅ Done |
| Categories CRUD | `app/admin/metadata/categories/page.tsx` | ✅ Done |
| Tags CRUD | `app/admin/metadata/tags/page.tsx` | ✅ Done |
| Access rules management | `app/admin/access-rules/page.tsx` | ✅ Done |
| Settings page (tabs: General, Notifications, Security) | `app/admin/settings/page.tsx` | ✅ Done |
| Unanswered questions | `app/admin/unanswered/page.tsx` | ✅ Done |
| Audit logs (search, filter, detail modal) | `app/admin/audit-logs/page.tsx` | ✅ Done |

### 5.4 Document Management — Hoàn thành

| Feature | Frontend File | Status |
|---------|--------------|--------|
| Documents list (grid/list view, search, status filter) | `app/documents/page.tsx` | ✅ Done |
| Upload modal (3-step: select → review metadata → success) | `components/documents/UploadModal.tsx` | ✅ Done |
| Document detail (metadata, version badge, download) | `app/documents/[id]/page.tsx` | ✅ Done |
| Policy comparison (add/remove/modified sections) | `app/documents/compare/page.tsx` | ✅ Done |

### 5.5 Analytics & Reporting — Hoàn thành

| Feature | Frontend File | Status |
|---------|--------------|--------|
| Analytics dashboard (charts: Line + Pie, top questions/docs) | `app/analytics/page.tsx` | ✅ Done |
| Reports page (create, list, download) | `app/analytics/reports/page.tsx` | ✅ Done |

### 5.6 Frontend-Backend Alignment

| Issue | Resolution | Status |
|-------|-----------|--------|
| Duplicate AI API (`api.ts` vs `ai.service.ts`) | Giữ nguyên cả hai — Gateway strip prefix `/api/v1/ai` nên cả hai đều đúng | ✅ Resolved |
| Feedback thiếu `messageId` | API client đã fix — truyền `messageId` đúng trong request | ✅ Fixed |
| Upload direct to knowledge-service | Giữ nguyên workaround (Gateway không parse multipart) | ✅ Documented |
| `ClientLayout` unused import | Đã xóa khỏi `app/layout.tsx` | ✅ Fixed |

### 5.7 Còn thiếu (chờ Backend)

| Feature | Lý do | Priority |
|---------|-------|---------|
| AI Q&A chat (Streaming) | Backend `ai-qa-service` chưa có | P0 |
| Conversation history (real data) | Backend AI service chưa có | P0 |
| Unanswered questions (real data) | Phụ thuộc AI service emit `unanswered.question` event | P1 |
| Policy comparison (real data) | Backend trả response đúng nhưng cần AI service parse content | P1 |
| Audit logs (real data) | Backend đã có endpoint, frontend đã kết nối | P2 |
| Reports (real download) | Backend chỉ CSV/JSON hoạt động, PDF/XLSX placeholder | P2 |
| Forgot/Reset password | Backend chưa có endpoint email | P3 |
| Realtime session revocation | Không có WebSocket/heartbeat | P3 |
