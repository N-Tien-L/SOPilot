---
id: PLAN-V2-SOPILOT-MVP
title: "Kế hoạch triển khai SOPilot V2: eval-first, chạy local, bàn giao nghiên cứu"
status: approved
created: 2026-10-17
updated: 2026-10-20
refs:
  - docs/01-requirements/PRD-V2-sopilot-mvp.md
  - docs/02-architecture/adr/ADR-004-two-service-architecture.md
  - docs/02-architecture/adr/ADR-005-workspace-tenancy-and-google-jit.md
  - docs/02-architecture/adr/ADR-006-free-tier-providers-and-environments.md
  - docs/04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md
  - docs/04-reports/AUDIT-ingestion-sop-data-2026-10-19.md
  - docs/02-architecture/adr/ADR-007-departments-member-profiles-document-access.md
milestone: "V2: SOPilot MVP"
total_tickets: 26
completed_tickets: 1
implemented_tickets: 4
review_tickets: 3
---

# KẾ HOẠCH TRIỂN KHAI THỰC THI (EXECUTION PLAN)

> **Mã kế hoạch:** `PLAN-V2-SOPILOT-MVP` | **Trạng thái:** `approved` (owner duyệt 2026-10-20)
>
> **Ràng buộc quy trình:** PRD-V2 và ADR-004/005/006/007 được owner duyệt ngày 2026-10-20 (`V2-01`). Ngày 2026-10-19 phạm vi được mở lại để giữ quản lý nhân sự, phòng ban phẳng, category/metadata và phân quyền tài liệu theo phòng ban (ADR-007). Theo `AGENTS.md`, PLAN này chưa được `approved` cho tới khi `V2-01` hoàn thành. Các ticket nghiên cứu (`V2-05` đến `V2-07`, `V2-19`) không phụ thuộc quyết định kiến trúc nên được chạy trước. Ingestion được tách thành `V2-19` đến `V2-22` theo [AUDIT-ingestion-sop-data](../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md).

---

## 1. Mục tiêu & phạm vi

**Đích:** bàn giao nghiên cứu khoa học, hệ thống **chạy được bằng `docker compose up` trên máy local**. Không deploy (B1/B2 ngoài phạm vi; B3 Cloudflare Tunnel chỉ là tùy chọn sau cùng).

**Thứ tự (hướng A, owner chốt 2026-10-17):** làm phần có giá trị nghiên cứu trước (đo chất lượng truy xuất), rồi mới viết lại sang 2 service, trim và thêm tính năng. Lý do: lõi RAG đa ngôn ngữ (VI, EN) chưa từng được đo; nếu số liệu kém thì chỉnh hướng trước khi đầu tư vào phần còn lại.

**Nguyên tắc khả thi (owner chốt 2026-10-17):** mục tiêu là hệ thống chạy được và bench được để báo cáo, không phải chọn cấu hình tốt nhất tuyệt đối. Áp dụng khi chọn bất kỳ thứ gì trong kế hoạch:
1. Phải chạy được trên máy owner (CPU, không GPU) và miễn phí; nếu không chắc thì đo thử trước khi cam kết.
2. Mỗi lựa chọn nặng (rerank, LLM giám khảo, model embedding lớn) có phương án rút gọn: tập con cố định hoặc model nhỏ hơn; báo cáo ghi chi phí đo được.
3. Khi hai phương án chênh nhau ít mà một bên khó chạy hơn nhiều, chọn bên chạy được và ghi lại đánh đổi.
4. Cắt P1 và tính năng không phục vụ bench/chạy được trước khi cắt thời gian của phần đo.

| Nhóm việc | Nội dung | Ticket |
|---|---|---|
| **Quyết định** | Duyệt tài liệu, TECH, xác nhận provider, đóng backlog cũ | V2-01 đến V2-04 |
| **Nghiên cứu** | Eval harness, bộ dữ liệu, chạy RQ1–RQ3/RQ5 | V2-05 đến V2-07 |
| **Cập nhật tính năng hiện có** | Sửa LLM, reranker, thang điểm, embedding provenance, auth hardening (khi port sang V2) | V2-09, V2-10, V2-11 |
| **Trim** | Còn 2 service; bỏ roster tạo trước, ACL tổng quát, cây phòng ban/category, OTP/mật khẩu, OnlyOffice, analytics, gateway, RabbitMQ, Redis | V2-08, V2-17 (gỡ code cũ) |
| **Thêm tính năng quan trọng** | Workspace + tenant + RLS, lời mời, trích dẫn có kiểm chứng, từ chối có căn cứ, hạn mức, audit, khoảng trống tri thức, demo data | V2-09 đến V2-16 |
| **Ingestion SOP** | Corpus trích xuất thật, trích xuất có cấu trúc, tách khung + metadata, chunk theo cấu trúc | V2-19 đến V2-22 |
| **Nhân sự, phòng ban, metadata (ADR-007)** | Hồ sơ thành viên, tạm khóa, phòng ban phẳng, category/tags, phạm vi hiển thị theo phòng ban, gợi ý metadata chạy nền, test phân quyền phòng ban | V2-23 đến V2-26 |
| **Nghiệm thu** | FR-19 trong CI, RQ4, parity, báo cáo bàn giao | V2-14, V2-17, V2-18 |

---

## 2. Đồ thị phụ thuộc

```mermaid
flowchart TD
    V01["V2-01 Duyệt PRD/ADR"] --> V03["V2-03 TECH-V2 (review)"]
    V01 --> V04["V2-04 Đóng backlog M1/NEXT"]
    V01 --> V08["V2-08 Flyway + compose"]
    V05["V2-05 Eval harness (review)"] --> V07["V2-07 Chạy RQ1-RQ3, RQ5"]
    V06["V2-06 Corpus + câu hỏi đa ngôn ngữ"] --> V07
    V19["V2-19 Corpus trích xuất SOP"] --> V20["V2-20 Trích xuất có cấu trúc"]
    V03 --> V20
    V20 --> V21["V2-21 Tách khung + metadata"]
    V20 --> V22["V2-22 Chunk theo cấu trúc"]
    V03 --> V09["V2-09 ai-service: worker ingest + retrieval + RLS"]
    V08 --> V09
    V20 --> V09
    V22 --> V09
    V03 --> V11["V2-11 core-api: login + workspace"]
    V08 --> V11
    V09 --> V10["V2-10 ai-service: pipeline hỏi đáp"]
    V02["V2-02 Xác nhận provider (review)"] --> V10
    V11 --> V12["V2-12 core-api: tài liệu + outbox"]
    V11 --> V23["V2-23 Hồ sơ thành viên + phòng ban"]
    V12 & V23 --> V24["V2-24 Metadata + phạm vi hiển thị"]
    V09 & V21 & V24 --> V25["V2-25 Gợi ý metadata chạy nền"]
    V10 & V23 & V24 --> V26["V2-26 Test phân quyền phòng ban"]
    V09 --> V12
    V12 --> V13["V2-13 Phản hồi + khoảng trống"]
    V10 --> V13
    V12 --> V14["V2-14 FR-19 tenant test + RQ4"]
    V09 --> V14
    V11 & V12 & V10 & V23 & V24 & V25 --> V15["V2-15 Frontend"]
    V12 & V10 & V21 & V24 --> V16["V2-16 Demo data + compose 1 lệnh"]
    V15 & V16 & V14 & V26 --> V17["V2-17 Parity + gỡ code cũ"]
    V07 & V14 & V17 --> V18["V2-18 Báo cáo bàn giao"]
```

---

## 3. Phân rã ticket

### Phase 0: Quyết định (không cần code)
| Ticket | Tiêu đề | Scope | Size | Phụ thuộc | Trạng thái |
|---|---|---|:---:|---|:---:|
| `V2-01` | Duyệt PRD-V2/ADR-004/005/006/007, chốt câu hỏi mở | docs | S | None | done |
| `V2-02` | Xác nhận model LLM còn sống bằng key thật | ai-qa | S | None | review |
| `V2-03` | Viết TECH-V2-core-api và TECH-V2-ai-service | docs | L | `V2-01` | review |
| `V2-04` | Đóng backlog M1/NEXT, dọn `docs/plans/` | docs | S | `V2-01` | todo |

### Phase 1: Nghiên cứu (chạy sớm, độc lập với viết lại)
| Ticket | Tiêu đề | Scope | Size | Phụ thuộc | Trạng thái |
|---|---|---|:---:|---|:---:|
| `V2-05` | Eval harness truy xuất (FR-18) | tests | M | None | review |
| `V2-06` | Corpus và bộ câu hỏi đa ngôn ngữ (VI, EN) có người duyệt | tests | L | None | todo |
| `V2-07` | Chạy RQ1–RQ3 và RQ5, báo cáo | tests | M | `V2-05`, `V2-06` | todo |

### Phase 2: Nền tảng và ai-service
| Ticket | Tiêu đề | Scope | Size | Phụ thuộc | Trạng thái |
|---|---|---|:---:|---|:---:|
| `V2-08` | Khung Flyway + compose (Postgres/pgvector, MinIO ghim bản) | infra | M | `V2-01` | todo |
| `V2-09` | ai-service: worker ingest, embedding, hybrid retrieval, RLS, 4 loại điểm, provider interface | ai-qa | L | `V2-03`, `V2-08`, `V2-20`, `V2-22` | todo |
| `V2-10` | ai-service: pipeline 2 lần gọi LLM, SSE, trích dẫn, từ chối | ai-qa | L | `V2-02`, `V2-09` | todo |

### Phase 2b: Ingestion SOP (AUDIT-ingestion-sop-data)
| Ticket | Tiêu đề | Scope | Size | Phụ thuộc | Trạng thái |
|---|---|---|:---:|---|:---:|
| `V2-19` | Corpus SOP thật (VI, EN; DOCX/PDF/MD) và bộ đo trích xuất | tests | M | None | todo |
| `V2-20` | ai-service: bộ trích xuất duy nhất ra văn bản có cấu trúc | ai-qa | L | `V2-03`, `V2-19` | todo |
| `V2-21` | ai-service: tách phần khung và trích metadata SOP | ai-qa | M | `V2-20` | todo |
| `V2-22` | ai-service: nhận diện loại tài liệu, bảng quy trình, chunk theo cấu trúc | ai-qa | L | `V2-20` | todo |

Contextual retrieval (bước 10 của audit) không có ticket; chỉ xét sau khi có kết quả `V2-07`.

### Phase 3: core-api
| Ticket | Tiêu đề | Scope | Size | Phụ thuộc | Trạng thái |
|---|---|---|:---:|---|:---:|
| `V2-11` | core-api: Google login, JIT, workspace, thành viên, lời mời, dev login | user | XL | `V2-03`, `V2-08` | todo |
| `V2-12` | core-api: tài liệu, upload, outbox, hạn mức, audit log | knowledge | L | `V2-09`, `V2-11` | todo |
| `V2-13` | Phản hồi và danh sách khoảng trống tri thức | feedback | M | `V2-10`, `V2-12` | todo |
| `V2-14` | Test cách ly tenant FR-19 trong CI và đo RQ4 | tests | M | `V2-09`, `V2-12` | todo |
| `V2-23` | core-api: hồ sơ thành viên, tạm khóa, phòng ban phẳng | user | M | `V2-11` | todo |
| `V2-24` | core-api: metadata, category/tags phẳng, phạm vi hiển thị theo phòng ban | knowledge | L | `V2-12`, `V2-23` | todo |
| `V2-25` | ai-service: gợi ý metadata chạy nền và đo độ trễ | ai-qa | M | `V2-09`, `V2-21`, `V2-24` | todo |
| `V2-26` | Test phân quyền tài liệu theo phòng ban (FR-29) trong CI | tests | M | `V2-10`, `V2-23`, `V2-24` | todo |

### Phase 4: Frontend, tích hợp, bàn giao
| Ticket | Tiêu đề | Scope | Size | Phụ thuộc | Trạng thái |
|---|---|---|:---:|---|:---:|
| `V2-15` | Frontend: thu gọn, chọn workspace, trình xem trích dẫn, thành viên/phòng ban/metadata | web | XL | `V2-10`, `V2-11`, `V2-12`, `V2-23`, `V2-24`, `V2-25` | todo |
| `V2-16` | Dữ liệu demo và `docker compose up` một lệnh | platform | M | `V2-10`, `V2-12`, `V2-21`, `V2-24` | todo |
| `V2-17` | Kiểm tra parity, gỡ 8 service cũ, cập nhật AGENTS.md và `.agent/context/` | platform | L | `V2-14`, `V2-15`, `V2-16`, `V2-26` | todo |
| `V2-18` | Báo cáo nghiên cứu và gói bàn giao | docs | M | `V2-07`, `V2-14`, `V2-17` | todo |

---

## 4. Rủi ro

| Rủi ro | Mức độ | Giảm thiểu |
|---|:---:|---|
| Chưa có SOP thật để đo trích xuất; `V2-19` chặn chuỗi ingestion và `V2-09` | Cao | Owner gom tài liệu sớm; `V2-19` chạy song song Phase 0–1 |
| Chất lượng RAG đa ngôn ngữ kém (nhất là cross-lingual), làm đổi hướng | Cao | Đo ở Phase 1 trước khi viết lại; `V2-07` là cổng quyết định |
| Máy không có GPU: embed `bge-m3` và rerank chậm | Cao | Cache embedding, chạy một lần; ghi thời gian vào báo cáo; có thể giảm kích thước corpus |
| Bộ câu hỏi thiếu chất lượng hoặc chưa có người duyệt | Cao | `V2-06` bắt buộc owner duyệt; ghi quy trình trong báo cáo |
| Viết lại quá lớn, không kịp hạn | Cao | Code cũ chạy song song; cắt P1 (domain join) và FR-05 trước nếu thiếu thời gian |
| Quota LLM chặn câu hỏi | Trung bình | Chỉ đo câu trả lời trên tập con; truy xuất đo không dùng LLM |
| RLS cấu hình sai | Cao | FR-19 chạy trong CI từ `V2-14`, ưu tiên sớm |
| Lộ tài liệu giới hạn phòng ban trong cùng workspace (lọc sau top-k, cache, lịch sử, bản sao quyền lệch) | Cao | Lọc trước `LIMIT` trong SQL, fail closed khi thiếu dòng quyền, FR-29 (`V2-26`) trong CI |
| Phạm vi tăng thêm 4 ticket (khoảng 1 XL quy đổi) | Trung bình | `V2-24`/`V2-25` không nằm trên đường tới RQ1–RQ3; nếu thiếu thời gian, hoãn import CSV (P1) và phương án nâng cấp gợi ý metadata trước |

## 5. Definition of Done
- [ ] 26/26 ticket `done` với bằng chứng.
- [ ] `docker compose up` dựng toàn bộ hệ thống trên máy local; UC-01 đến UC-06 chạy được.
- [ ] FR-19 và FR-29: 0 rò rỉ. Báo cáo RQ1–RQ3 trong `docs/04-reports/`.
- [ ] `AGENTS.md`, `CLAUDE.md` (mục drift) và `.agent/context/` phản ánh kiến trúc mới.
