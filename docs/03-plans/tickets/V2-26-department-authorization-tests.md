---
id: V2-26
title: "Test phân quyền tài liệu theo phòng ban (FR-29) trong CI"
type: test
status: done
created: 2026-10-19
updated: 2026-11-10
author: "Owner"
scope: tests
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-10, V2-23, V2-24]
blocks: [V2-17]
branch: "test/tests-department-authorization"
assignee: pair
---

# TICKET V2-26: Test phân quyền phòng ban

## 1. Bối cảnh & Mục tiêu
PRD-V2 FR-29, ADR-007 §4.4–4.5. Lớp kiểm thử thứ hai, độc lập với cách ly workspace (V2-14/FR-19): trong **cùng một workspace**, tài liệu giới hạn phòng ban không lộ cho người ngoài phòng ban.

## 2. Tiêu chí Hoàn thành
- [x] Dữ liệu test: một workspace, phòng ban A và B, thành viên ở A, ở B, chưa có phòng ban, `SUSPENDED`, cùng OWNER và ADMIN; tài liệu `WORKSPACE`, `DEPARTMENTS[A]`, `DEPARTMENTS[A,B]`, mỗi tài liệu có tiêu đề và chuỗi bí mật riêng.
- [x] Mọi ô **đọc** của ma trận ADR-007 §4.4 được kiểm qua từng kênh:
  - core-api: danh sách, tìm kiếm, chi tiết, URL tải; tài liệu ngoài quyền trả `404`.
  - ai-service: dense, BM25, rerank, chunk mở rộng khi ghép context, context gửi LLM (LLM mock ghi lại prompt), trích dẫn, xem nội dung (`GET /ai/v1/documents/{id}/versions/{versionId}/content`), "tài liệu gần nhất" trong câu từ chối `NO_EVIDENCE`, lịch sử hội thoại khi mở lại và lịch sử gửi cho bước viết lại câu hỏi.
  - Cache: chỉ có `rag.embedding_cache` (khóa theo hash nội dung chunk, chỉ lưu vector, ADR-007 §4.5); chỉ cần xác nhận bảng không có cột văn bản. Chưa có cache câu trả lời hay kết quả truy xuất nên không có ô cần kiểm.
- [x] Dòng ghi của ma trận chỉ kiểm MEMBER bị từ chối; quyền ghi theo phòng ban thuộc ADR-009/V2-36.
- [x] Ca thay đổi, mỗi ca có kết quả mong đợi:
  - Chuyển A → B: sau refresh, token mới mang `wdept = B` và chỉ đọc được tài liệu của B; access token cũ giữ quyền cũ tới khi hết hạn (≤ 15 phút, ADR-007 §5).
  - Tạm khóa: refresh trả `403 MEMBERSHIP_SUSPENDED` và chuỗi refresh bị thu hồi; access token đang giữ còn dùng được tới khi hết hạn (≤ 15 phút, ADR-007 §5). Test ghi lại khoảng hở này, không coi là lỗi.
  - Archive phòng ban A: tài liệu giữ `visibility` và `department_ids`; thành viên còn thuộc A vẫn đọc được (ADR-007 §4.3).
  - Xóa phòng ban A còn tài liệu: `409 DEPARTMENT_IN_USE`.
  - Thu hẹp tài liệu từ `WORKSPACE` sang `DEPARTMENTS[A]`: sau khi ai-service nhận `ACCESS_UPDATED`, thành viên B và người chưa có phòng ban không còn thấy tài liệu ở mọi kênh.
  - Thu hẹp mà ai-service **chưa nhận** cập nhật: phạm vi cũ còn hiệu lực ở ai-service tới khi outbox gửi xong (ADR-007 §5). Đây là khoảng hở đã biết, không phải fail-closed; test ghi lại hành vi.
  - Fail-closed: tài liệu chưa có dòng `rag.document_access`, đã xóa hoặc chưa kích hoạt phiên bản thì không ai đọc được, kể cả OWNER.
- [x] Không câu trả lời nào trả về tên hay nội dung tài liệu ngoài quyền; số chunk vào context không giảm vì lọc sau top-k (lọc trước `LIMIT`).
- [x] Có kiểm chứng âm: tắt điều kiện phòng ban trong bộ lọc thì bộ test phải đỏ.
- [x] Chạy trong GitHub Actions cùng FR-19 trên mỗi PR.

## 3. Hướng dẫn
- Dùng chung khung test của V2-14; giữ bộ FR-29 tách khỏi bộ FR-19 để lỗi chỉ ra đúng lớp bị hỏng.
- Hai suite chạy độc lập như V2-14, không cần chạy hai service cùng lúc:
  - core-api: `services/core-api/src/test/java/com/sopilot/core/tenancy/` (mẫu `TenantIsolationApiIT`), Testcontainers, ai-service giả lập.
  - ai-service: `services/ai-service/tests/integration/` (mẫu `test_qa_isolation.py`), Postgres thật, provider và LLM mock, token ký bằng khóa test.
- Điểm lọc cần nhắm tới: core-api TECH-V2-core-api §5.6; ai-service `sopilot_ai/retrieval/access_filter.py` (`allowed_cte`, `cited_access_cte`), TECH-V2-ai-service §7.5.
- Khoảng trễ của token và của đồng bộ quyền: ADR-007 §5, TECH-V2-document-access-sync §7.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Integration (core-api) | Phần core của FR-29 trên Postgres thật, ai-service giả lập | `./scripts/run-tests.ps1 -Scope core-api -Type all` |
| Integration (ai-service) | Truy xuất, context LLM, trích dẫn, lịch sử, LLM mock | `./scripts/run-tests.ps1 -Scope ai-service -Type integration` |
| CI | Hai suite trên chạy trong `tenant-isolation.yml` trên mỗi PR | GitHub Actions |

## 5. Kết quả triển khai
Ngày 2026-11-10, nhánh `test/tests-department-authorization`. Chỉ thêm test và một job CI; không sửa mã sản phẩm. Hai suite chạy độc lập như V2-14, không có harness chạy hai service cùng lúc.

**File**
- `services/core-api/src/test/java/com/sopilot/core/tenancy/DepartmentAuthorizationIT.java`: 81 lượt chạy (tham số hóa theo ô, lỗi chỉ ra đúng ô `actor x tài liệu`).
- `services/ai-service/tests/integration/test_department_authorization.py`: 60 lượt chạy.
- `.github/workflows/tenant-isolation.yml`: thêm job `department-authorization` (chạy cả hai suite), không đổi các job FR-19.

**Ma trận đọc.** Năm người (OWNER, ADMIN, MEMBER ở A, MEMBER ở B, MEMBER chưa có phòng ban) × ba tài liệu (`WORKSPACE`, `DEPARTMENTS[A]`, `DEPARTMENTS[A,B]`), mỗi tài liệu có tiêu đề và chuỗi bí mật riêng. Ô ngoài quyền kiểm tiêu đề, bí mật, `documentId` và `versionId` vắng trong toàn bộ phản hồi, không chỉ đếm số lượng.
- core-api: chi tiết, URL tải, danh sách, tìm kiếm `?q=` (khớp tiêu đề), tập kết quả đúng bằng tập đọc được; ngoài quyền luôn `404`. Dòng ghi: MEMBER nhận `403` ở PATCH, PUT `/visibility`, DELETE, retry và upload, kể cả với id ngẫu nhiên (không lộ sự tồn tại), tài liệu không đổi.
- ai-service: dense, BM25, hybrid, rerank (reranker ghi lại mọi đoạn nhận được), SQL ghép context (`load_chunks`, `load_sections`, `load_version_info`) và `BuildContextStep` với hit đã cũ, prompt gửi LLM, luồng trả lời, trích dẫn, lượt hội thoại đã lưu (`context_sources`, `message_citations`, `retrieval_results`), mở lại hội thoại, `nearestDocuments` của `NO_EVIDENCE`, endpoint nội dung.
- Không áp dụng: thành viên `SUSPENDED` ở ai-service (ai-service chỉ xác thực token, khoảng hở ghi ở core-api).

**Ca thay đổi** (core-api: `DepartmentAuthorizationIT`; ai-service: `test_department_authorization.py`)
| Ca | Kết quả quan sát |
|---|---|
| Chuyển A → B | Trước refresh token cũ (`wdept = A`) vẫn đọc tài liệu chỉ của A (khoảng hở, `exp - iat` ≤ 900 s được kiểm). Sau refresh `wdept = B`: tài liệu chỉ của A thành `404`, tài liệu `[A,B]` còn đọc được. |
| Tạm khóa | Đặt `SUSPENDED` trực tiếp trong DB: refresh trả `403 MEMBERSHIP_SUSPENDED`, chuỗi bị thu hồi, không dùng lại được sau khi bỏ khóa. Tạm khóa qua API: chuỗi bị thu hồi ngay nên refresh là `401` (xem GAP 1). Cả hai đường: access token đang giữ còn đọc được tới khi hết hạn; cấp token mới bị `MEMBERSHIP_SUSPENDED`. |
| Archive phòng ban A | Tài liệu giữ `visibility` và `department_ids`; thành viên A đọc được, B và người chưa có phòng ban vẫn `404`; không phát sinh `ACCESS_UPDATED`. |
| Xóa phòng ban còn tham chiếu | `409 DEPARTMENT_IN_USE` (chi tiết `documents` / thành viên), tài liệu nguyên vẹn. |
| Thu hẹp `WORKSPACE` → `DEPARTMENTS[A]` | core-api: B và người chưa có phòng ban `404` ngay ở mọi kênh; một `ACCESS_UPDATED` với `accessRevision = 2` và `departmentIds = [A]`. ai-service: sau `PUT /internal/document-access` mọi kênh đều đóng. |
| Thu hẹp, ai-service chưa nhận | Phạm vi cũ còn hiệu lực ở mọi kênh tới khi cập nhật tới (khoảng hở đã biết, không phải fail-closed); test khẳng định hành vi này rồi kiểm nó đóng lại sau `PUT`. |
| Revision cũ hoặc bằng | `applied: false` với revision 2, 1, 0; không mở rộng quyền; revision 3 được áp dụng (đối chứng). |
| Fail-closed | Thiếu dòng `rag.document_access` (chunk vẫn còn), phiên bản chưa kích hoạt, đã xóa: không ai đọc được ở mọi kênh, kể cả OWNER. |
| Hội thoại mở lại / bước viết lại | Câu trả lời dựng từ tài liệu vừa bị thu hẹp bị ẩn `ACCESS_REVOKED`, không còn `content` hay nội dung; bước viết lại không nhận lượt đó, chỉ nhận lượt còn đọc được. |

**Lọc trước `LIMIT`.** Tài liệu bị cấm có 40 mục, tài liệu mở có 40 mục, `candidate_pool = rerank_pool = context_k = 5`. Đối chứng: người đọc được cả hai nhận 5 chunk toàn của tài liệu bị cấm (chúng xếp trên). Người ngoài phòng ban vẫn nhận đủ 5 chunk dense, 5 BM25, 5 ứng viên hybrid, tất cả của tài liệu mở.

**Cache.** Chỉ `rag.embedding_cache` được dùng: khóa `(model, revision, content_sha256)`, không cột `workspace_id`, cột kiểu văn bản chỉ là `model`, `revision`, bản dump hàng không chứa chuỗi bí mật hay tiêu đề nào. Không có cache câu trả lời hay truy xuất. Có thêm bảng `rag.suggestion_cache` (V2-25, hiện chưa ai ghi); test khẳng định bảng rỗng và đỏ khi V2-25 bắt đầu ghi (GAP 2).

**Kiểm chứng âm** (chạy cục bộ, đã khôi phục file, `git diff` của file rỗng)
| Suite | Sửa tạm | Số test đỏ |
|---|---|---|
| core-api | `DocumentRepository.VISIBLE`: `dd.department_id = ?::uuid` → `(… OR true)` | 8 / 81 |
| core-api | `VISIBLE`: nhánh phòng ban luôn đúng (`?::uuid IS NOT NULL OR true OR EXISTS …`) | 18 / 81 |
| ai-service | `access_filter._READABLE`: điều kiện phòng ban → `OR true` | 27 / 60 |
| ai-service | `_READABLE`: bỏ nhánh phòng ban | 23 / 60 |

**GAP và câu hỏi thiết kế**
1. Tiêu chí tạm khóa nói "refresh trả `403 MEMBERSHIP_SUSPENDED`". Qua API (`MemberService.java:116`) chuỗi refresh bị thu hồi ngay lúc khóa nên refresh nhận `401` (`RefreshTokenService.java:76`); `403` chỉ xuất hiện khi trạng thái đổi mà chuỗi chưa bị thu hồi (`RefreshTokenService.java:89`, test `SessionWorkspaceIT` cũng làm vậy). An toàn hơn tài liệu mô tả; nên sửa lời trong ADR-007/ticket V2-23 hoặc chấp nhận hai mã.
2. `rag.suggestion_cache` (V2-25) khóa theo `workspace_id` và `cache_key`, không có `wdept`; kết quả sinh từ nội dung tài liệu. Khi V2-25 ghi bảng này cần quyết định ai được xem gợi ý của tài liệu giới hạn phòng ban.
3. Hai khoảng hở đã biết, được test khẳng định chứ không phải lỗi: token cũ sau khi đổi phòng ban hoặc tạm khóa còn hiệu lực tới 15 phút; ai-service còn dùng phạm vi cũ tới khi nhận `ACCESS_UPDATED`.
4. `?q=` của core-api tìm theo tiêu đề (`ILIKE`), không tìm trong nội dung; tìm theo nội dung nằm ở ai-service.

**GitHub Actions:** job `department-authorization` xanh trên PR #12 ([run](https://github.com/N-Tien-L/SOPilot/actions/runs/42851584792/job/129953412037)): `DepartmentAuthorizationIT` 81/81, `test_department_authorization.py` 60 passed; các job FR-19 (`database`, `negative-control`, `core-api`, `ai-service`) cũng xanh.

**Chưa kiểm:** kiểm chứng âm chưa tự động hóa trong CI (như job `negative-control` của FR-19 làm cho RLS); chưa chạy core-api và ai-service cùng lúc.
