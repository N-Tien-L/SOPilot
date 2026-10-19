---
id: ADR-004
title: "V2: hai backend service (core-api Spring Boot + ai-service FastAPI), bỏ gateway, RabbitMQ và Redis"
status: approved
created: 2026-10-16
updated: 2026-10-20
refs: [docs/01-requirements/PRD-V2-sopilot-mvp.md]
deciders: ["Owner"]
amends: []
supersedes: [ADR-002]
superseded_by: ""
---

# ADR-004: Hai backend service, bỏ gateway, RabbitMQ và Redis

> **Trạng thái:** `approved` (2026-10-20) | **Ngày đề xuất:** `2026-10-16` | **Người quyết định:** `Owner`
>
> Khi được duyệt, ADR này thay thế ADR-002 (Gateway làm reverse proxy). Phần "backend tự xác minh Google ID token" của ADR-002 được giữ lại trong core-api.

---

## 1. Bối cảnh & vấn đề cần quyết định
- Hệ thống hiện có 8 service (gateway NestJS, 5 service Spring Boot, 2 service FastAPI) cùng RabbitMQ, Redis, MinIO, khoảng 40 nghìn dòng backend. Không thể host miễn phí, và một người không bảo trì nổi.
- PRD-V2 yêu cầu chi phí mục tiêu 0 USD/tháng, đồng thời dự án phải thể hiện được cả kỹ năng Java (SWE) lẫn Python (AIE).
- Mỗi service phải là một ranh giới có lý do thật (khác ngôn ngữ, khác tải, khác vòng đời), không chia nhỏ chỉ để có nhiều service.

## 2. Tiêu chí đánh giá
1. Chi phí vận hành và số tiến trình phải chạy.
2. Ranh giới sở hữu dữ liệu rõ ràng, không ghi chéo schema.
3. Công sức của một người trong một học kỳ.
4. Giá trị trình bày trên CV và trong báo cáo nghiên cứu.
5. Khả năng test cách ly tenant end-to-end.

## 3. Các phương án xem xét

### Phương án 1: Giữ 8 microservice, chỉ cắt tính năng
- **(+)** Ít viết lại.
- **(−)** Vẫn cần RabbitMQ/Redis/gateway; chi phí và độ phức tạp vận hành không giảm; bài toán tenant phải sửa ở 6 service.

### Phương án 2: FastAPI + Supabase (Auth, Postgres, Storage)
- **(+)** Rẻ và nhanh nhất; RLS có sẵn.
- **(−)** Không còn phần Java; owner đã loại phương án này ngày 2026-10-16.

### Phương án 3: core-api (Spring Boot) + ai-service (FastAPI) — modular monolith mỗi bên
- **(+)** Ranh giới theo ngôn ngữ và loại tải: nghiệp vụ/giao dịch ở Java, ML/RAG ở Python. Chỉ 2 tiến trình ứng dụng.
- **(+)** Có các mẫu thiết kế đáng giá cho CV: JWT RS256 + JWKS giữa các service, outbox gửi việc ingest, hàng đợi Postgres `FOR UPDATE SKIP LOCKED`, RLS.
- **(−)** Phải viết lại phần lớn code Java theo mô hình workspace.

## 4. Quyết định & biện luận
- **Phương án được chọn:** **Phương án 3.**

### 4.1 Thành phần
| Thành phần | Công nghệ | Trách nhiệm | Schema sở hữu |
|---|---|---|---|
| `frontend/web` | Next.js | Giao diện | — |
| `services/core-api` | Spring Boot 3.x | Google login, user, workspace, membership, lời mời, tài liệu (metadata + file), phản hồi, khoảng trống tri thức, audit, hạn mức | `core` |
| `services/ai-service` | FastAPI | Worker ingest, truy xuất hybrid, sinh câu trả lời SSE, hội thoại, eval harness | `rag` |
| PostgreSQL 16 + pgvector | — | Lưu trữ | `core`, `rag` |
| Object storage S3-compatible | MinIO ghim phiên bản (local), R2/B2 (deploy) | File gốc | bucket duy nhất, cấu hình qua env |

Lựa chọn embedding, LLM, reranker, storage và cách chạy ở từng môi trường (eval local, deploy): [ADR-006](ADR-006-free-tier-providers-and-environments.md).

Không có gateway, RabbitMQ hay Redis.

### 4.2 Xác thực giữa các thành phần
- core-api phát access token **RS256** và công bố public key tại `/.well-known/jwks.json`. ai-service xác minh token bằng JWKS này (có cache), không cần gọi core-api cho mỗi request.
- Gọi nội bộ giữa hai service dùng endpoint `/internal/**`, xác thực bằng token dịch vụ cấu hình qua env, và không được công bố ra ngoài.
- Trình duyệt chỉ thấy **một origin**: reverse proxy (hoặc Next.js rewrites) định tuyến `/api/**` tới core-api và `/ai/**` tới ai-service. Cách cụ thể chốt trong TECH.

### 4.3 Ingest không cần message broker
1. core-api lưu file vào storage và ghi `core.documents` với trạng thái `UPLOADED` trong cùng một transaction.
2. Một scheduler trong core-api (outbox) gửi các tài liệu `UPLOADED` tới `POST /internal/ingestions` của ai-service. ai-service ghi job vào `rag.ingestion_jobs` (idempotent theo `document_id` + `checksum`) và trả `202`.
3. Worker của ai-service lấy job bằng `SELECT ... FOR UPDATE SKIP LOCKED`, xử lý xong thì gọi `PATCH /internal/documents/{id}/status` của core-api.
4. Xóa tài liệu đi theo cùng cơ chế outbox để xóa chunk.

Mỗi service chỉ ghi schema của mình. ai-service không đọc `core`; mọi thông tin cần thiết (`workspace_id`, khóa object, checksum) đi trong job.

### 4.4 Migration và dữ liệu
- V2 bắt đầu từ **database mới**; không có dữ liệu production cần giữ. Bộ migration mới nằm ở `infrastructure/db/migrations/`, mỗi schema một chuỗi phiên bản, chạy bằng Flyway (container chạy một lần trong compose và trong CI).
- `infrastructure/init-db/` giữ nguyên cho tới khi các service cũ bị gỡ. Reset volume cục bộ chỉ chạy khi owner yêu cầu rõ ràng.

### 4.5 Chuyển đổi trong repo
- Viết service mới ở `services/core-api` và `services/ai-service`, song song với service cũ. Mã cũ chỉ để tham khảo/port, không sửa tiếp.
- Port có chọn lọc: xác minh Google token và binding `(issuer, sub)` (ADR-003), xoay vòng refresh token, trích xuất/chunk/embedding, SQL truy xuất hybrid, các component chat ở frontend.
- Khi V2 đạt parity với PRD-V2, gỡ các service cũ trong một commit riêng (lịch sử git giữ lại), rồi cập nhật `AGENTS.md`, script và `.agent/context/`.

## 5. Tác động & hệ quả
- **Tích cực:** chỉ 2 tiến trình ứng dụng; deploy được lên một VM miễn phí; ranh giới dữ liệu đơn giản; mỗi service có câu chuyện riêng cho CV.
- **Đánh đổi:**
  - Ingest không phát sự kiện tức thời: độ trễ phụ thuộc chu kỳ scheduler (vài giây).
  - Mất các tính năng gateway (rate limit theo role, circuit breaker); hạn mức chuyển vào core-api và ai-service.
  - Viết lại phần lớn Java; mã cũ tồn tại song song một thời gian và làm `check-conventions.ps1`/`run-tests.ps1` cần thêm scope mới.
- **Hành động tiếp theo:**
  - Viết `TECH-V2-core-api` và `TECH-V2-ai-service` (DDL, API, sequence).
  - Cập nhật script `validate-build.ps1`, `run-tests.ps1` thêm scope `core-api`, `ai-service`.
  - Khi duyệt: chuyển ADR-002 sang `superseded`, cập nhật `AGENTS.md` (bảng topology, quy tắc migration).
