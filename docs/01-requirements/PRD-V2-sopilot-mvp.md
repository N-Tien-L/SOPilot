---
id: PRD-V2-SOPILOT-MVP
title: "SOPilot V2 MVP: workspace hỏi đáp tài liệu có trích dẫn, đa tổ chức"
status: approved
created: 2026-10-16
updated: 2026-10-20
author: "Owner"
milestone: "V2: SOPilot MVP"
priority: P0
refs:
  - docs/04-reports/AUDIT-project-progress-2026-10-14.md
  - docs/04-reports/AUDIT-google-admission-2026-10-15.md
  - docs/04-reports/AUDIT-v2-baseline-analysis-2026-10-17.md
  - docs/04-reports/AUDIT-ingestion-sop-data-2026-10-19.md
  - docs/02-architecture/adr/ADR-007-departments-member-profiles-document-access.md
---

# YÊU CẦU NGHIỆP VỤ & ĐẶC TẢ TÍNH NĂNG (PRD)

> **Mã tài liệu:** `PRD-V2-SOPILOT-MVP` | **Milestone:** `V2: SOPilot MVP` | **Trạng thái:** `approved` (owner duyệt 2026-10-20, V2-01)
>
> Khi được duyệt, PRD này thay thế `PRD-M1-jit-onboarding.md` (mô hình một tổ chức + roster). Kiến trúc: [ADR-004](../02-architecture/adr/ADR-004-two-service-architecture.md). Tenancy và đăng nhập: [ADR-005](../02-architecture/adr/ADR-005-workspace-tenancy-and-google-jit.md). Hồ sơ thành viên, phòng ban và quyền tài liệu: [ADR-007](../02-architecture/adr/ADR-007-departments-member-profiles-document-access.md).

---

## 1. Problem Statement & Motivation

### Bối cảnh & điểm nghẽn hiện tại
- SOPilot là bản sao của Poliwise, một hệ thống phục vụ **một tổ chức cố định**: roster do HR nạp sẵn, phòng ban toàn cục, quyền theo phòng ban. Schema, JWT và tài liệu spec không có khái niệm tổ chức (tenant). Nếu có tổ chức thứ hai, truy xuất RAG chỉ lọc theo role/phòng ban nên có thể lộ tài liệu chéo.
- Khách hàng mục tiêu mới đa dạng: người dùng đơn lẻ, nhóm/startup nhỏ, doanh nghiệp lớn. Mô hình roster chặn 403 mọi người không có HR, nên không phục vụ được hai nhóm đầu.
- Hệ thống mang nhiều tính năng vận hành doanh nghiệp (OnlyOffice, so sánh version, analytics, export, quản lý phiên, OTP...) trong khi lõi giá trị là **hỏi đáp có trích dẫn đáng tin** chưa được đo chất lượng.
- 8 service + RabbitMQ + Redis + MinIO không host miễn phí được và vượt sức bảo trì của một người.

### Mục tiêu mong đợi
1. Một MVP hoàn chỉnh, chạy thật, chi phí vận hành mục tiêu **0 USD/tháng**, đủ để đưa vào CV (AI Engineer và Software Engineer) và nộp nghiên cứu cho trường.
2. Lõi giá trị: hỏi đáp **đa ngôn ngữ** (tối thiểu tiếng Việt và tiếng Anh, kể cả hỏi một ngôn ngữ trên tài liệu ngôn ngữ khác) trên tài liệu của workspace, câu trả lời có trích dẫn tới trang/đoạn, biết từ chối khi thiếu bằng chứng, không bao giờ lộ tài liệu giữa các workspace.
3. Chất lượng được **đo bằng số liệu** (bộ eval + ablation), không chỉ demo.

---

## 2. User Personas & Use Cases

| Persona | Mô tả vai trò | Mục tiêu chính |
|---|---|---|
| **Solo user** | Cá nhân dùng Gmail | Tải tài liệu của mình lên và hỏi đáp ngay, không cần ai duyệt |
| **Workspace Owner / Admin** | Người lập nhóm, trưởng nhóm, IT của công ty | Tạo workspace, mời thành viên, quản lý tài liệu, xem câu hỏi chưa trả lời được |
| **Member** | Thành viên nhóm/nhân viên | Hỏi đáp trên tài liệu chung của workspace, kiểm tra nguồn trích dẫn |
| **Evaluator** | Tác giả dự án, người chấm nghiên cứu | Chạy bộ đánh giá, so sánh cấu hình truy xuất, tái lập kết quả |

Vai trò trong workspace: `OWNER`, `ADMIN`, `MEMBER`. Không còn role toàn hệ thống `USER/MANAGER/ADMIN`. Phòng ban được giữ ở dạng phẳng, thuộc từng workspace, dùng để giới hạn quyền đọc tài liệu (ADR-007); phòng ban không phải role.

### Use Case Scenarios
1. **UC-01: Đăng nhập lần đầu (solo)**
   - **Actor:** Solo user. **Tiền điều kiện:** có tài khoản Google, email đã xác minh.
   - **Luồng chính:** bấm "Sign in with Google" → backend xác minh ID token → tạo user theo `(issuer, sub)` → tự tạo workspace cá nhân với role `OWNER` → vào trang chat.
   - **Hậu điều kiện:** user có đúng 1 workspace cá nhân; đăng nhập lại không tạo thêm.
2. **UC-02: Mời thành viên**
   - **Actor:** Owner/Admin. **Luồng chính:** nhập email + role → hệ thống tạo link mời một lần, hạn 7 ngày → người được mời đăng nhập Google bằng đúng email đó → trở thành member.
   - **Ngoại lệ:** email Google không khớp lời mời → từ chối, lời mời vẫn còn hiệu lực.
3. **UC-03: Tự gia nhập theo domain (P1)**
   - **Actor:** Owner dùng tài khoản Google Workspace (claim `hd = acme.com`). **Luồng chính:** owner bật "cho phép mọi người @acme.com gia nhập" → nhân viên đăng nhập Google có `hd = acme.com` thấy workspace và gia nhập với role `MEMBER`.
4. **UC-04: Tải tài liệu và hỏi đáp**
   - **Actor:** Owner/Admin tải lên; Member hỏi. **Luồng chính:** tải PDF → trạng thái `PROCESSING` → `READY` → member hỏi → câu trả lời stream kèm trích dẫn `[1]`, `[2]` → bấm trích dẫn mở tài liệu đúng trang, tô sáng đoạn nguồn.
5. **UC-05: Câu hỏi không có trong tài liệu**
   - **Luồng chính:** điểm truy xuất dưới ngưỡng → hệ thống trả lời "không tìm thấy trong tài liệu của workspace" thay vì suy đoán → câu hỏi vào danh sách "chưa trả lời được" cho Admin.
6. **UC-06: Chạy đánh giá**
   - **Actor:** Evaluator. **Luồng chính:** chạy lệnh eval với một bộ câu hỏi chuẩn và danh sách cấu hình → nhận báo cáo chỉ số cho từng cấu hình.
7. **UC-07: Mời nhân sự kèm hồ sơ**
   - **Actor:** Owner/Admin. **Luồng chính:** nhập email, role, họ tên, phòng ban và (tùy chọn) mã nhân viên, chức danh → lời mời ở trạng thái chờ → người được mời đăng nhập Google đúng email → membership `ACTIVE` mang hồ sơ đã nhập. Không cần tạo hồ sơ nhân sự trước lời mời.
8. **UC-08: Gán và chuyển phòng ban**
   - **Actor:** Owner/Admin. **Luồng chính:** chọn thành viên → đổi phòng ban → từ lần cấp token kế tiếp (≤ 15 phút), thành viên chỉ đọc được tài liệu của phòng ban mới cộng tài liệu toàn workspace.
9. **UC-09: Upload và gợi ý metadata**
   - **Actor:** Owner/Admin. **Luồng chính:** tải file, chọn phạm vi hiển thị (mặc định toàn workspace) → tài liệu xử lý tới `READY` mà không chờ gợi ý → gợi ý tiêu đề, mô tả, category, tags, ngôn ngữ xuất hiện khi chạy nền xong → người quản lý chấp nhận hoặc sửa. Gợi ý không bao giờ đổi phạm vi hiển thị.
10. **UC-10: Hỏi tài liệu giới hạn phòng ban**
   - **Actor:** Member. **Luồng chính:** hỏi câu có đáp án nằm trong tài liệu chỉ dành cho phòng ban khác → hệ thống trả lời không tìm thấy bằng chứng, không tiết lộ tên hay nội dung tài liệu đó. Khi thuộc đúng phòng ban → trả lời kèm trích dẫn.
11. **UC-11: Thu hồi quyền**
   - **Actor:** Owner/Admin. **Luồng chính:** tạm khóa thành viên hoặc chuyển phòng ban → bị chặn chậm nhất khi access token hết hạn (≤ 15 phút). Thu hẹp phạm vi tài liệu → bị chặn ngay khi ai-service nhận cập nhật (gọi đồng bộ, outbox thử lại). Lịch sử hội thoại ẩn đoạn trích và câu trả lời dựa trên tài liệu không còn quyền.

---

## 3. Functional Requirements (FR)

### Danh tính và workspace
- [ ] **FR-01: Đăng nhập chỉ bằng Google.** Xác minh ID token (chữ ký RS256 qua JWKS, `iss`, `aud`, `exp`, `email_verified`). Định danh theo `(issuer, sub)`, email chỉ là thuộc tính. User được tạo just-in-time ở lần đăng nhập đầu. Không có đăng ký/mật khẩu/OTP. Đăng nhập dev (không cần Google) chỉ bật ở profile `local`/`test`.
- [ ] **FR-02: Workspace cá nhân tự động.** Lần đăng nhập đầu tạo workspace cá nhân, idempotent.
- [ ] **FR-03: Quản lý workspace.** Tạo, đổi tên, xóa (chỉ `OWNER`), liệt kê workspace của tôi, chuyển workspace đang hoạt động.
- [ ] **FR-04: Thành viên và lời mời.** Lời mời mang hồ sơ ban đầu (họ tên, phòng ban, mã nhân viên và chức danh tùy chọn), được áp dụng khi chấp nhận. Owner/Admin mời theo email + role; link một lần, hạn 7 ngày, thu hồi được. Đổi role, xóa thành viên, rời workspace. Workspace luôn còn ít nhất một `OWNER`. Admin không được nâng ai lên `OWNER` hoặc xóa `OWNER`.
- [ ] **FR-05 (P1): Gia nhập theo domain.** Chỉ owner có claim `hd` mới bật được, và chỉ cho domain bằng `hd` của chính họ. Người có `hd` trùng gia nhập với role `MEMBER`.

- [ ] **FR-22: Hồ sơ thành viên.** Tài khoản đăng nhập là toàn cục; hồ sơ nằm ở membership trong từng workspace: họ tên hiển thị, email, mã nhân viên (tùy chọn, duy nhất trong workspace nếu có), chức danh (tùy chọn), phòng ban (tối đa một), trạng thái `ACTIVE | SUSPENDED`. Lời mời chưa nhận là trạng thái chờ. Vòng đời: mời → `ACTIVE` → `SUSPENDED` (khóa truy cập, giữ dữ liệu, mở lại được) hoặc rời/bị xóa khỏi workspace. Khóa truy cập workspace không xóa tài khoản toàn cục. Không có chấm công, lương, nghỉ phép. Workspace cá nhân không yêu cầu hồ sơ hay phòng ban, và việc thiếu hồ sơ không bao giờ chặn tạo workspace cá nhân.
- [ ] **FR-23: Phòng ban phẳng.** Owner/Admin tạo, đổi tên, ngừng sử dụng phòng ban của workspace; không có cha/con. Chỉ xóa hẳn khi không còn thành viên và không tài liệu nào tham chiếu; ngược lại chỉ ngừng sử dụng. Ngừng sử dụng hay xóa không bao giờ mở rộng quyền của tài liệu đang giới hạn cho phòng ban đó.
- [ ] **FR-24 (P1): Import thành viên từ CSV.** Tạo hàng loạt lời mời kèm hồ sơ; báo lỗi theo dòng.

### Tài liệu
- [ ] **FR-06: Tải tài liệu.** PDF, DOCX, MD, TXT; tối đa 20 MB/file. Chặn trùng theo SHA-256 trong cùng workspace. Chỉ `OWNER`/`ADMIN` tải lên và xóa; mọi member xem và tải xuống.
- [ ] **FR-07: Vòng đời tài liệu.** `UPLOADED → PROCESSING → READY | FAILED`. Thử lại khi `FAILED`. Tải bản mới thay thế bản cũ (chunk cũ bị xóa sau khi bản mới `READY`). Xóa tài liệu xóa file và toàn bộ chunk.
- [ ] **FR-08: Ingestion.** Trích xuất văn bản giữ số trang và tiêu đề mục, chia chunk, tạo embedding, lưu kèm `workspace_id`, `document_id`, `page`, vị trí ký tự. Có hàng đợi bền (không mất job khi service khởi động lại). Bổ sung theo [AUDIT-ingestion-sop-data](../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md):
  - Một bộ trích xuất duy nhất, xuất văn bản có cấu trúc (heading, danh sách có số thứ tự tự động của Word, bảng nằm đúng vị trí).
  - Tách phần khung khỏi nội dung được index: header/footer lặp mỗi trang, quốc hiệu/tiêu ngữ, chữ ký, nơi nhận, bảng phê duyệt, bảng theo dõi sửa đổi.
  - Trích metadata từ nội dung khi có: mã số, lần ban hành, ngày hiệu lực.
  - Nhận diện cấu trúc theo loại tài liệu (quy trình ISO, Chương/Điều/Khoản, Markdown, văn xuôi không chuẩn); bảng quy trình (Trách nhiệm/Bước/Mô tả/Biểu mẫu) được giữ theo từng bước.
  - Mỗi chunk mang đường dẫn tiêu đề; đếm token bằng tokenizer của model embedding.
  - PDF không có lớp chữ (scan) và file ảnh bị từ chối với thông báo rõ, trạng thái `FAILED` kèm lý do.
- [ ] **FR-25: Phạm vi hiển thị tài liệu.** Mỗi tài liệu là `WORKSPACE` (mọi thành viên `ACTIVE`) hoặc `DEPARTMENTS` (một hoặc nhiều phòng ban). OWNER/ADMIN đọc và quản lý mọi tài liệu. MEMBER đọc tài liệu `WORKSPACE` và tài liệu `DEPARTMENTS` có phòng ban của mình; MEMBER chưa có phòng ban chỉ đọc tài liệu `WORKSPACE`. Quyền đọc áp dụng cho danh sách, tìm kiếm, chi tiết, xem trước, tải xuống (URL ký sẵn hạn ≤ 5 phút), dense, BM25, rerank, context gửi LLM, trích dẫn, cache và lịch sử hội thoại. Lọc xảy ra **trước** khi chọn top-k, nên không có dữ liệu ngoài quyền vào context LLM. Không có ACL theo từng người.
- [ ] **FR-26: Metadata tài liệu.** Metadata hệ thống (tên file, loại, kích thước, SHA-256, số trang, trạng thái, phiên bản, người/ngày tải lên, ngôn ngữ phát hiện, nguồn gốc embedding, mã số/lần ban hành/ngày hiệu lực trích từ nội dung) chỉ hệ thống ghi. Metadata do Owner/Admin sửa: tiêu đề, mô tả ngắn, một category, nhiều tags, ngôn ngữ, phạm vi hiển thị. Sửa tiêu đề, mô tả, category, tags chỉ cập nhật thuộc tính. Sửa phạm vi hiển thị chỉ cập nhật bản sao quyền ở ai-service, không embed lại. Sửa ngôn ngữ chỉ làm lại chỉ mục BM25 nếu BM25 cấu hình theo ngôn ngữ. Không có custom field động.
- [ ] **FR-27: Category và tags phẳng.** Category thuộc workspace, không cây; mỗi tài liệu tối đa một category. Category dùng để phân loại và lọc, không phải cơ chế cấp quyền. Tags thuộc workspace, tạo khi gắn.
- [ ] **FR-28: Gợi ý metadata chạy nền.** Không chặn upload và không chặn `READY`. Dùng lại văn bản đã trích xuất, không tải hay parse lại file. Luật trước (tiêu đề từ heading đầu hoặc tên file, ngôn ngữ, mã số/lần ban hành/ngày hiệu lực); sau đó một lần gọi LLM có structured output cho mô tả, category (chọn trong danh sách hiện có, hoặc để trống kèm đề xuất tên mới), tags (ưu tiên tags đã có). Đầu vào giới hạn ở tiêu đề, dàn ý heading và đoạn đại diện. Có timeout, tối đa một lần thử lại; lỗi thì chỉ dùng kết quả luật. Cache theo `(workspace_id, sha256 nội dung, phiên bản prompt/model, danh sách category)`. Gợi ý không ghi đè trường người dùng đã sửa và không bao giờ đổi phạm vi hiển thị.
- [ ] **FR-09: Hạn mức.** Mặc định mỗi workspace tối đa 50 tài liệu và 200 MB; mỗi user tối đa 20 câu hỏi/ngày; toàn hệ thống có trần câu hỏi/ngày đặt dưới RPD của provider sinh câu trả lời (mặc định 400 với Gemini 3.1 Flash Lite 500 RPD). Cấu hình được qua biến môi trường. Có bộ giới hạn tốc độ theo provider (RPM/TPM) và tự chuyển sang model dự phòng khi gặp 429.

### Hỏi đáp
- [ ] **FR-10: Hybrid RAG.** Dense (pgvector) + BM25, gộp bằng RRF, rerank là tùy chọn bật/tắt bằng cấu hình (mặc định tắt khi deploy miễn phí, ADR-006). **Mọi truy vấn bắt buộc lọc theo `workspace_id`** của token.
- [ ] **FR-11: Sinh câu trả lời có trích dẫn.** Stream qua SSE. Trả lời theo ngôn ngữ câu hỏi (đa ngôn ngữ; ngôn ngữ được kiểm chứng là VI và EN, ngôn ngữ khác là best-effort và không cam kết chất lượng). Mỗi khẳng định gắn `[n]`; mỗi `[n]` ánh xạ tới `document_id`, `page`, đoạn trích. Trích dẫn không ánh xạ được thì bị loại khỏi câu trả lời.
- [ ] **FR-12: Từ chối có căn cứ.** Khi bằng chứng dưới ngưỡng cấu hình, trả lời "không tìm thấy" kèm gợi ý tài liệu gần nhất (nếu có), và ghi câu hỏi vào danh sách chưa trả lời được.
- [ ] **FR-13: Guard nhiều lớp, không dùng classifier.** Phòng thủ chính là kiến trúc: quyền đọc lọc trong SQL trước khi vào LLM (FR-19, FR-25), system prompt không chứa bí mật, trích dẫn không ánh xạ được bị loại (FR-11), thiếu bằng chứng thì từ chối (FR-12). Guard thêm bốn lớp, không lớp nào gọi thêm LLM: (1) đầu vào: chuẩn hóa (NFC, bỏ dấu, leetspeak), giới hạn độ dài, luật VI/EN hai mức: mức chặn (đòi lộ system prompt/quy tắc ẩn, ghi đè chỉ dẫn nhắm vào chỉ dẫn/prompt, giả mạo vai trò hệ thống) trả câu từ chối cố định; mức gắn cờ (đóng vai, bỏ qua...) vẫn trả lời và chỉ ghi log; chào hỏi/cảm ơn/hỏi về bot trả lời bằng mẫu; (2) ghép prompt: chunk bọc trong thẻ dữ liệu có escape, câu hỏi ở message riêng; (3) đầu ra: canary token trong system prompt, câu trả lời chứa canary hoặc đoạn dài của system prompt bị thay bằng từ chối; (4) log cờ guard cho Admin. Nội dung độc hại dựa vào bộ lọc an toàn của provider. Không có node LLM phân loại ý định hay trả lời kiến thức chung. Llama Prompt Guard 2 86M bị loại sau bài test V2-02 (2026-10-20).
- [ ] **FR-14: Trình xem trích dẫn.** Bấm `[n]` mở tài liệu ở đúng trang (PDF) hoặc đúng đoạn (văn bản), tô sáng đoạn nguồn.
- [ ] **FR-15: Hội thoại.** Danh sách theo workspace, tiêu đề tự sinh, đổi tên, xóa. Chỉ người tạo xem được hội thoại của mình.

### Phản hồi và chất lượng
- [ ] **FR-16: Phản hồi câu trả lời.** Upvote/downvote + bình luận tùy chọn.
- [ ] **FR-17: Danh sách khoảng trống tri thức.** Admin xem các câu bị từ chối và câu bị downvote, đánh dấu đã xử lý. Không có quy trình duyệt nhiều bước.
- [ ] **FR-18: Eval harness.** Định dạng bộ dữ liệu (câu hỏi, tài liệu/trang kỳ vọng, câu trả lời tham chiếu, cờ `answerable`). Lệnh CLI chạy nhiều cấu hình (dense, BM25, hybrid, hybrid + rerank) và xuất báo cáo Markdown/JSON có thể tái lập.
- [ ] **FR-19: Bộ test cách ly tenant.** Test tự động tạo nhiều workspace có tài liệu chứa "chuỗi bí mật" riêng và chứng minh không câu hỏi/API nào trả về dữ liệu của workspace khác.
- [ ] **FR-29: Bộ test phân quyền phòng ban.** Lớp riêng với FR-19, trong cùng workspace: tài liệu `DEPARTMENTS` chứa chuỗi bí mật không xuất hiện với thành viên ngoài phòng ban qua mọi đường của FR-25 (API, dense, BM25, rerank, context LLM, trích dẫn, lịch sử, cache, URL tải). Gồm các ca chuyển phòng ban, tạm khóa, ngừng phòng ban, xóa phòng ban bị chặn, và thu hẹp phạm vi tài liệu.
- [ ] **FR-20: Audit log tối thiểu.** Ghi: đăng nhập, thay đổi thành viên/role/phòng ban, tạm khóa/mở khóa, tải lên/xóa tài liệu, đổi phạm vi hiển thị tài liệu. Owner xem được log của workspace.
- [ ] **FR-21: Dữ liệu demo.** Script tạo workspace mẫu với bộ SOP công khai để demo và chạy eval.

---

## 4. Non-Functional Requirements (NFR)
- **Cách ly tenant (bắt buộc):** mọi bảng dữ liệu nghiệp vụ có `workspace_id`; mọi truy vấn lọc theo nó ở tầng ứng dụng, cộng thêm Postgres Row-Level Security làm lớp phòng thủ thứ hai (ADR-005). FR-19 phải đạt **0 rò rỉ**.
- **Bảo mật:** access token ngắn hạn (≤ 15 phút), refresh token xoay vòng và phát hiện tái sử dụng. Mất membership có hiệu lực chậm nhất khi access token hết hạn. Không log token/secret. Không trả chi tiết lỗi nội bộ ra client.
- **Hiệu năng (trên hạ tầng miễn phí):** token đầu tiên P95 < 3 s khi service đang chạy; ingest PDF 20 trang < 60 s. Gợi ý metadata không nằm trên đường tới `READY`. Đo riêng: thời gian phản hồi upload, upload → `READY`, `READY` → có gợi ý, độ trễ LLM p50/p95, tỉ lệ fallback, tỉ lệ chấp nhận gợi ý theo trường. Chưa đặt mục tiêu tốc độ gợi ý trước khi có baseline. Chấp nhận cold start của gói miễn phí và ghi rõ trong báo cáo.
- **Chi phí:** mục tiêu 0 USD/tháng. Hạn mức FR-09 bảo vệ quota của nhà cung cấp LLM/embedding.
- **Chất lượng RAG (mục tiêu ban đầu, chốt lại sau khi đo baseline):** recall@5 ≥ 0.80; độ chính xác trích dẫn ≥ 0.85; tỉ lệ từ chối đúng trên câu không trả lời được ≥ 0.80.
- **Kiểm thử & CI:** unit + integration chạy trên GitHub Actions (miễn phí); FR-19 chạy trong CI.
- **Khả năng tái lập:** một lệnh `docker compose up` dựng toàn bộ hệ thống cục bộ; eval chạy lại cho cùng kết quả truy xuất với cùng dữ liệu và cấu hình.

---

## 5. Scope & Boundary

| Hạng mục | Trong phạm vi | Ngoài phạm vi (cắt khỏi V2) |
|---|---|---|
| Danh tính | Google login, JIT user, workspace, membership kèm hồ sơ thành viên, lời mời mang hồ sơ, tạm khóa, domain join (P1), import CSV (P1), dev login cho test | Đăng ký/mật khẩu, OTP, quên/đổi mật khẩu, roster HR tạo trước khi đăng nhập, quản lý phiên, lịch sử đăng nhập, HRM (chấm công, lương, nghỉ phép), xóa tài khoản toàn cục |
| Tổ chức | Workspace + 3 role, phòng ban phẳng (mỗi thành viên tối đa một phòng ban) | Cây phòng ban, nhiều phòng ban mỗi người, quyền quản lý tài liệu cho trưởng phòng ban (P1) |
| Tài liệu | Upload, thay thế bản mới, xóa, xem, tải xuống, phạm vi hiển thị theo phòng ban, category và tags phẳng, metadata tối thiểu, gợi ý metadata chạy nền | OnlyOffice, khóa sửa, xung đột version, force-push, so sánh version, so sánh chính sách, OCR ảnh và PDF scan, import hàng loạt, danh mục dạng cây, custom field, ACL theo từng người |
| Hỏi đáp | Hybrid RAG, rerank, SSE, trích dẫn, từ chối, guardrail một bước, hội thoại | Intent classification nhiều tầng, chọn model LLM từ UI |
| Phân tích | Phản hồi, danh sách khoảng trống tri thức, audit tối thiểu, eval harness | Dashboard analytics, xu hướng, export, báo cáo, thống kê user/tài liệu |
| Hạ tầng | 2 backend service + Postgres/pgvector + object storage S3 | API Gateway riêng, RabbitMQ, Redis, circuit breaker, rate limit theo role |
| Giao diện | Đăng nhập, chọn workspace, chat + trình xem trích dẫn, tài liệu, thành viên, khoảng trống tri thức, cài đặt workspace | Trang admin hệ thống, analytics |

---

## 6. Câu hỏi nghiên cứu (phần nộp cho trường)
**Nguyên tắc khả thi:** mục tiêu là hệ thống *chạy được* và *đo được* để báo cáo, không phải chọn cấu hình tốt nhất tuyệt đối. Mỗi cấu hình đưa vào thí nghiệm phải chạy được trên máy của owner (CPU, không GPU), miễn phí, và báo cáo ghi chi phí đo được (thời gian, RAM). Cấu hình nặng (rerank, LLM làm giám khảo) chỉ chạy trên tập con cố định nếu cần, và báo cáo nêu rõ.

- **RQ1:** Trên tài liệu SOP đa ngôn ngữ (VI, EN), hybrid (dense + BM25, RRF) cải thiện recall@k bao nhiêu so với chỉ dense hoặc chỉ BM25? Báo cáo tách theo ngôn ngữ của câu hỏi.
- **RQ1b (phụ):** Khi câu hỏi và tài liệu khác ngôn ngữ (cross-lingual), dense, BM25 và hybrid chênh nhau thế nào? (BM25 dựa trên từ nên dự kiến yếu ở trường hợp này; cần đo, không giả định.)
- **RQ2:** Rerank tăng độ chính xác trích dẫn và faithfulness bao nhiêu, với chi phí độ trễ bao nhiêu?
- **RQ3:** Ngưỡng từ chối ảnh hưởng thế nào đến sự cân bằng giữa trả lời sai và từ chối nhầm?
- **RQ4 (phụ):** Lọc tenant (ứng dụng + RLS) ảnh hưởng thế nào đến độ trễ truy xuất?
- **RQ5 (đề xuất):** Model embedding mã nguồn mở nào (bge-m3, Qwen3-Embedding-0.6B, multilingual-e5-large-instruct) truy xuất tốt nhất trên corpus đa ngôn ngữ của dự án, xét cả chi phí chạy trên CPU?

**Giới hạn tuyên bố (owner chốt 2026-10-19):** corpus RQ1–RQ5 (V2-06) là tài liệu tiếng Anh dạng Markdown, câu hỏi VI và EN. Kết quả không chứng minh chất lượng trên tài liệu tiếng Việt hoặc DOCX/PDF. Chất lượng trích xuất DOCX/PDF tiếng Việt được đo riêng bằng corpus trích xuất của V2-19, không gộp vào RQ1–RQ5.

Môi trường và thiết kế thí nghiệm: ADR-006 §4.2 (chạy trên máy local, không phụ thuộc quota).

---

## 7. Acceptance Criteria tổng quan (DoD)
- [ ] UC-01 đến UC-11 chạy được trên giao diện và API khi dựng bằng `docker compose up` trên máy local (deploy công khai ngoài phạm vi, xem §8).
- [ ] FR-19 và FR-29 đạt 0 rò rỉ và chạy trong CI.
- [ ] Báo cáo eval (FR-18) trả lời RQ1–RQ3 với số liệu, lưu trong `docs/04-reports/`.
- [ ] Không phát sinh chi phí ngoài các API miễn phí; mọi chi phí phát sinh được ghi rõ.
- [ ] TECH cho core-api và ai-service được duyệt; `.agent/context/` cập nhật theo kiến trúc mới.

---

## 8. Quyết định cho các câu hỏi mở (owner chốt 2026-10-19)
1. **Java:** 21 (LTS) cho core-api.
2. **Nơi host:** chỉ chạy local bằng `docker compose up`. Deploy công khai (B1, B2) ngoài phạm vi V2; B3 (máy local + Cloudflare Tunnel) là tùy chọn sau cùng. Không dùng Oracle (quyết định 2026-10-17).
3. **Embedding:** `bge-m3` chạy local (ADR-006). Jina đã bỏ ngày 2026-10-17.
4. **Object storage:** MinIO ghim phiên bản cho local và CI. R2/B2 chỉ cần khi deploy, nên ngoài phạm vi V2.
5. **LLM (phân vai chốt 2026-10-19, ADR-006 §4.4):** sinh câu trả lời bằng Gemini 3.1 Flash Lite, dự phòng Groq `openai/gpt-oss-120b`; gợi ý metadata bằng Groq `openai/gpt-oss-20b`; guard injection bằng luật (Prompt Guard 2 86M bị loại sau bài test V2-02 ngày 2026-10-20); giám khảo eval bằng Groq `openai/gpt-oss-120b`. Mỗi câu hỏi tối đa 1 lần gọi LLM sinh. Groq đã gọi thử thành công ngày 2026-10-20; Gemini 3.1 Flash Lite trả 503 (quá tải) lúc thử, cần thử lại.
6. **Workspace demo công khai:** không làm, vì không deploy công khai. Dữ liệu demo cục bộ theo FR-21 (V2-16). ADR-005 không cần bổ sung.
7. **Phòng ban mỗi thành viên:** tối đa một phòng ban; tài liệu có thể giới hạn cho nhiều phòng ban. Nhiều phòng ban mỗi người để P1 nếu có nhu cầu thực tế.
8. **Lịch sử hội thoại khi mất quyền:** ẩn câu trả lời và đoạn trích có trích dẫn tới tài liệu người đó không còn quyền đọc; giữ câu hỏi và ghi chú lý do ẩn.
9. **Trưởng phòng ban quản lý tài liệu của phòng ban:** P1. Trong V2 chỉ OWNER/ADMIN tải lên, sửa, xóa và đổi phạm vi tài liệu.
