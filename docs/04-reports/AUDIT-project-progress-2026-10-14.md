---
report_id: AUDIT-PROJECT-2026-10-14
title: "Audit hiện trạng và tiến độ chuyển đổi Poliwise → SOPilot"
type: quality-audit
status: completed
date: 2026-10-14
author: Codex
milestone: "Toàn dự án; trọng tâm M1 JIT Onboarding"
target_scope: [all]
verdict: FAILED
---

# Audit hiện trạng và tiến độ SOPilot

## 1. Kết luận điều hành

SOPilot có nền tảng ứng dụng kế thừa khá rộng và đã triển khai backend/gateway cho onboarding Google + roster. Tuy nhiên **chưa đủ bằng chứng nghiệm thu M1 hoặc phát hành theo định hướng mới**. `FAILED` ở đây là chưa đạt điều kiện nghiệm thu, không có nghĩa mọi thành phần đều hỏng.

- Kế hoạch ghi 4/6 ticket hoàn thành, tức 66,7% theo số lượng ticket M1. Đây không phải phần trăm hoàn thành toàn sản phẩm hoặc phần trăm công sức.
- Hồ sơ ticket thực tế: M1-01/02 `done`, M1-03/04 `review`, M1-05/06 `todo`. Chỉ 2/6 được đánh dấu `done` nhất quán ở cấp ticket; cần hòa giải trước khi dùng số liệu quản trị.
- M1-05 đã có code Google login, roster và upload trong working tree; chưa nên xem là chưa làm, cũng chưa nên xem là đã nghiệm thu.
- Chưa thấy bộ E2E và SQL xác minh audit mà M1-06 yêu cầu.
- Định hướng được đặc tả rõ nhất hiện nay là M1. Chưa thấy backlog tổng thể quyết định từng tính năng kế thừa sẽ giữ, bỏ, sửa hay nâng cấp. Vì vậy không thể tính tiến độ chuyển đổi toàn dự án một cách đáng tin cậy.

## 2. Phạm vi và phương pháp

Snapshot: branch `feat/gateway-roster-routes`, HEAD `386dda1`. Audit cả mã tracked và thay đổi/untracked tại thời điểm kiểm tra. Ban đầu `git status --short` có 40 mục; nhiều thư mục untracked đại diện cho nhiều file. Báo cáo này là file mới duy nhất do audit chủ động thêm; không sửa code, commit, push, khởi động stack, reset DB hay gửi dữ liệu đến AI bên ngoài.

Đối chiếu README, `.agent/context/`, PRD/TECH/ADR, hai cây kế hoạch `docs/plans` và `docs/03-plans`, lịch sử Git, source/test, CI và cấu hình hạ tầng. Không có snapshot độc lập của project cũ để xác nhận đầy đủ diff trước/sau sao chép. Nhận định về phần kế thừa dựa trên lịch sử và cấu trúc trong checkout này.

Đây là audit tiến độ và rủi ro có trọng tâm, không phải chứng nhận bảo mật toàn bộ source hoặc đánh giá chất lượng RAG bằng benchmark.

## 3. Ma trận tiến độ sản phẩm

| Hạng mục | Bằng chứng hiện tại | Trạng thái đánh giá |
|---|---|---|
| Nền tảng microservices, gateway, frontend, DB, RabbitMQ, MinIO | Source và Compose; commit nền tảng `eb52f3b` | Có triển khai; runtime toàn stack chưa xác minh |
| Đổi tên Poliwise → SOPilot, dùng cloud embedding | README, cấu hình Python/Compose và thay đổi chưa commit | Đang chuyển đổi; còn mô tả và định danh cũ |
| Cắt tính năng thừa | Vẫn có register, forgot/reset password, sessions, analytics, compare documents, metadata, settings | Chưa có ma trận phạm vi để kết luận tính năng nào thừa; chưa chứng minh hoàn tất cắt bỏ |
| Sửa lỗi nền tảng/CI | Lịch sử có nhiều commit `fix(ci)` | Có hoạt động sửa lỗi; không đồng nghĩa CI hiện tại đã xanh |
| Nâng cấp tính năng có sẵn | UI roster/login đang thay đổi; source quản lý tài liệu và RAG có sẵn | Tiến độ UI có thể quan sát; chưa có checklist nâng cấp toàn sản phẩm |
| Tính năng mới M1 roster + Google JIT | Migration, service, controller, verifier, gateway, UI | Đã triển khai nhiều lớp; còn lệch hợp đồng và thiếu E2E |
| Q&A, citations, retrieval, ingestion | Source Python, routes, repos và tests | Có code; chưa đo độ đúng, phân quyền retrieval, latency, chi phí |
| Quản trị documents/users/departments/audit/unanswered | Các route `frontend/web/app/admin` và backend controller | Có bề mặt chức năng; chưa nghiệm thu hành trình admin |

Tên package Java `com.poliwise` hay tên package Python cũ tự nó không chứng minh lỗi chức năng và không cần ưu tiên đổi tên nếu không mang lợi ích sản phẩm.

### M1 theo từng ticket

| Ticket | Bằng chứng | Kết luận audit |
|---|---|---|
| M1-01 DB roster | `fe91419`, `infrastructure/init-db/010_employee_roster.sql` | Đã commit, ticket done; chưa chạy bootstrap DB trong đợt này |
| M1-02 roster/claim | `0325cc8`, service/controller/repository/test | Đã commit, ticket done; claim có transaction và pessimistic lock trên source; chưa kiểm chứng concurrency thực |
| M1-03 Google auth | `bf7c555`, verifier/auth service/test | Đã commit, ticket review; kiểm tra RS256, issuer, audience, expiry và verified email có trong source |
| M1-04 gateway | `386dda1`, controller/spec | Đã commit, ticket review; 39 gateway tests chạy thành công trong đợt này |
| M1-05 frontend | Login page, RosterTab/RosterUploadModal, API client/types | Có triển khai chưa commit; TypeScript pass; CSV lệch backend; chưa kiểm tra với phiên admin/Google thực |
| M1-06 E2E/audit | Ticket yêu cầu 15 cases, E2E spec và SQL | Chưa thấy artifact yêu cầu; chưa nghiệm thu |

## 4. Findings và mức ưu tiên

### F01 — P1: CSV được UI/PRD chấp nhận nhưng backend không có parser CSV

`frontend/web/app/admin/users/components/RosterUploadModal.tsx:35` chấp nhận `.xlsx`/`.csv`; `services/user-service/src/main/java/com/poliwise/user/service/RosterExcelService.java:166` gọi `WorkbookFactory.create(inputStream)`. Backend đọc workbook Excel; không thấy nhánh parser CSV. FR-01 yêu cầu cả Excel/CSV. Đây là lệch hợp đồng xác định bằng source, chưa tái hiện upload HTTP trong đợt này.

Hành động: triển khai parser CSV và kiểm tra import thực, hoặc điều chỉnh phạm vi PRD/UI nếu chủ sản phẩm chấp thuận bỏ CSV.

### F02 — P1: Người dùng đã tồn tại đăng nhập Google mà không qua roster

`services/auth-service/src/main/java/com/poliwise/auth/service/AuthService.java:196` tìm tài khoản theo email; nhánh existing ở dòng 199 đi thẳng kiểm tra account status/lock rồi cấp token, chỉ nhánh tài khoản mới gọi claim. Một tài khoản kế thừa active nhưng không thuộc roster có thể đi qua nhánh này, trái mục tiêu whitelist nếu yêu cầu áp dụng cho mọi nhân viên.

Đây là hành vi suy ra trực tiếp từ source; chưa tái hiện bằng Google token thật. Cần quyết định rõ chính sách cho tài khoản kế thừa/admin bootstrap, rồi kiểm thử trường hợp existing user không có roster, pending/deactivated và claimed.

### F03 — P1: Audit trail JIT chưa đáp ứng tiêu chí M1-06 và chưa đảm bảo delivery

`EmployeeRosterService.java:168` tạo `UserRegisteredEvent`; record tại `services/user-service/src/main/java/com/poliwise/user/dto/event/UserRegisteredEvent.java` không có `loginMethod`. Không thấy `GOOGLE_JIT` trong source service. M1-06 yêu cầu metadata `loginMethod: GOOGLE_JIT`.

Publish xảy ra trong method `@Transactional` trước khi transaction kết thúc; exception được bắt và bỏ qua tại dòng 180. Vì vậy transaction DB có thể thành công khi event thất bại, hoặc event được gửi trước khi commit DB. Chưa xác minh consumer và `analytics.audit_logs` thực tế. Cần cơ chế delivery phù hợp (ví dụ transactional outbox), xử lý idempotency và kiểm tra audit sau commit; không chỉ bổ sung trường JSON.

### F04 — P1: Gateway ghi toàn bộ body đăng nhập vào debug log

`services/api-gateway/src/auth/auth-proxy.controller.ts:35` dùng `JSON.stringify(request.body)` trong logger. Khi debug được bật, username/password có thể vào log. Không cần xem hay in secret để xác định nguy cơ này. Cần bỏ body hoặc redact trước khi log và rà soát log token ở các đường auth khác.

### F05 — P2: Luồng legacy chưa được hòa giải với định hướng onboarding

PRD/PLAN M1 yêu cầu thay thế hoàn toàn đăng ký/tạo tài khoản thủ công. Vẫn có `app/register/page.tsx`, các trang password và controller register. Gateway register là `@Public()` nhưng backend `AuthController.java:60` có `@PreAuthorize("hasRole('ADMIN')")`; **không kết luận public self-registration bypass** chỉ từ gateway/security permitAll. Tuy vậy admin vẫn có đường tạo tài khoản trực tiếp ngoài roster.

Cần liệt kê rõ đường nào giữ cho admin, đường nào bỏ cho nhân viên, và migration tài khoản cũ. Các module analytics/compare/settings chỉ được coi là ứng viên rà soát phạm vi, chưa đủ căn cứ gọi là tính năng thừa.

### F06 — P2: Embedding đã chuyển nhà cung cấp nhưng provenance/cache vẫn ghi BGE_M3

`services/ingestion-service/src/config/settings.py:32` và AI-QA settings dùng `jina-embeddings-v3`; `services/ingestion-service/src/services/embedding_service.py:27` vẫn đặt `EMBEDDING_MODEL_NAME = "BGE_M3"`, pipeline cũng ghi nhãn này. DB enum tại `003_knowledge.sql:29` chưa có Jina.

Đây là lệch provenance xác nhận từ source. Nếu cache/vector cũ còn tồn tại, có nguy cơ tái sử dụng vector khác model vì nhãn cache không đổi; chưa xác minh dữ liệu thực. Cần version hóa model/cache và kế hoạch reindex, kiểm tra dimension và query/document embedding cùng model. Không tự xóa cache hoặc reingest trong audit.

### F07 — P2: Tài liệu và quy tắc ownership mâu thuẫn thực thi

`.agent/context/overview.md` đầu file nói giữ `poliwise_*`, nhưng phần ownership nói `core/metadata/knowledge/conversation/analytics`; AGENTS và DDL dùng schema mới. Overview vẫn mô tả BGE-M3, còn settings đã dùng Jina.

Quy tắc strict schema isolation chưa phản ánh đường data thực: AI-QA truy vấn `knowledge.chunks` tại `src/db/repositories/chunk_repo.py:56`, ingestion ghi schema knowledge; `002_metadata.sql:62` có FK tới core. Cần ADR ghi quyền truy cập data plane thực và vai trò DB, hoặc thay đổi triển khai theo ranh giới đã duyệt. Không đổi routing/schema chỉ để làm tài liệu trông nhất quán.

### F08 — P2: Quản trị tiến độ và verification chưa đáng tin cậy

Hai cây kế hoạch trùng nhau; plan 4/6 done nhưng ticket 03/04 vẫn review. Frontend `package.json` không có script test trong khi `scripts/run-tests.ps1` gọi `pnpm test`. Ingestion tests ở `tests/ingestion_tests`, nhưng runner unit/integration chọn `tests/unit`/`tests/integration`. CI frontend/gateway chỉ build, không chạy gateway Jest hoặc frontend lint. Các gaps này có thể khiến build xanh bị hiểu nhầm thành nghiệm thu nghiệp vụ.

`003_knowledge.sql` đang được sửa trực tiếp default bucket thay vì thêm script migration: chỉ sửa bootstrap không cập nhật DB đã tồn tại. Nếu cần thay đổi DB hiện hữu, thực hiện script numbered additive theo handbook.

## 5. Ma trận kiểm tra thực thi

| Kiểm tra | Kết quả trong đợt này | Giới hạn |
|---|---|---|
| Frontend TypeScript: `node node_modules/typescript/bin/tsc --noEmit --incremental false` | PASS, exit 0 | Không phải build Next.js hoặc test UI |
| Gateway TypeScript, cùng lệnh | PASS, exit 0 | Không kiểm tra proxy với downstream thực |
| Frontend ESLint: `node node_modules/eslint/bin/eslint.js .` | FAIL, exit 1: 61 errors, 99 warnings | Toàn frontend hiện tại; chưa quy lỗi cho thay đổi mới khi chưa chạy baseline riêng. Ví dụ explicit-any ở `app/admin/audit-logs/page.tsx:365`, set-state-in-effect ở `providers/LanguageProvider.tsx:51` |
| Gateway Jest: `node node_modules/jest/bin/jest.js --runInBand` | PASS: 3 suites, 39 tests, 31,411s | Unit/controller mocks; không phải full E2E |
| User Maven wrapper `./mvnw.cmd test -B -Dstyle.color=never` | Không khởi chạy Maven: null-array/wrapper error | Không tính là assertion fail; chưa có kết quả test Java mới |
| `docker compose config --quiet` | Không thấy lỗi cấu hình; có warning không đọc được Docker user config | Không chứng minh container chạy |
| Health script qua PowerShell process ExecutionPolicy Bypass | 9/9 endpoint ứng dụng unreachable; PostgreSQL/RabbitMQ management/MinIO unreachable; Redis TCP reachable | Trạng thái từ môi trường audit; có thể do stack chưa bật hoặc hạn chế truy cập. TCP Redis không xác nhận đúng instance/dữ liệu |
| `docker ps` | Permission denied Docker named pipe | Không xác minh topology runtime |
| Python suites, full Java verify, Next build, pre-commit, E2E, performance | Chưa chạy/hoàn tất trong đợt này | Không dùng artifacts cũ để thay kết quả hiện tại |

Lệnh pnpm ban đầu bị EPERM `lstat C:\Users\Tien`; đã dùng entrypoint Node trong workspace để chạy TypeScript/Jest thành công. Health script ban đầu bị execution policy; chạy lại bằng policy chỉ áp dụng process, không đổi policy máy.

Tỷ lệ pass của **39 test thực sự chạy** là 100%; không có tỷ lệ pass toàn hệ thống. Không đo coverage, P95/P99, RAM, concurrency hay chi phí. Các claim README “production-ready”, phản hồi 1–2 giây và VPS 2–4GB chưa được chứng minh trong audit này.

Git chỉ track các `.env.example` theo kiểm tra tên file; chưa audit toàn bộ lịch sử secret, nên không kết luận không rò rỉ secret.

## 6. Thứ tự công việc đề xuất

1. **Chốt phạm vi sản phẩm:** một tài liệu quyết định giữ/bỏ/sửa/nâng cấp/mới cho mọi module kế thừa; ghi persona, hành trình chính và acceptance. Ưu tiên luồng admin nạp SOP → nhân viên được cấp quyền → hỏi đáp có dẫn nguồn.
2. **Khóa onboarding và dữ liệu nhạy cảm:** xử lý F02/F04, xác định ngoại lệ admin và tài khoản cũ; hòa giải luồng password/register với PRD.
3. **Hoàn thiện M1:** sửa hợp đồng CSV, audit metadata/delivery, kiểm tra UI với phiên admin và Google hợp lệ; chỉ cập nhật ticket done khi có evidence.
4. **Thực hiện M1-06:** tự động hóa import/login/claim/chat/403, concurrent claim, phân quyền và audit log; chạy full service gates trong môi trường khả dụng. Test có state phải dùng DB/test data cô lập.
5. **Ổn định RAG/ingestion:** model provenance/cache/reindex, ACL retrieval, upload → ready → citation → delete; đo chất lượng bằng bộ câu hỏi và expected sources trước khi tuyên bố hiệu năng.
6. **Dọn nền tảng kế thừa:** thống nhất một cây docs, bổ sung ADR data ownership, sửa test runner/CI và dùng additive migrations cho DB hiện hữu. Cắt từng module sau khi kiểm tra dependency API/event/table/UI.

Frontend lint hiện fail là gate chất lượng cần xử lý trước nghiệm thu; phân loại lỗi kế thừa và lỗi thay đổi mới trước khi mở ticket, tránh sửa hàng loạt ngoài phạm vi.

Không ước lượng ngày hoàn thành vì chưa có scope toàn sản phẩm và năng lực thực thi được thống nhất. Không nên lấy 66,7% M1 để suy ra dự án gần hoàn tất.

## 7. Sign-off

**Chưa nghiệm thu M1; chưa xác nhận sẵn sàng phát hành.** Bằng chứng hiện tại phù hợp với trạng thái “backend/gateway đã triển khai, frontend đang hoàn thiện, tích hợp và chuyển đổi sản phẩm chưa đóng”. Các findings trên là đầu vào backlog; audit không tự sửa lỗi hoặc đổi trạng thái ticket.
