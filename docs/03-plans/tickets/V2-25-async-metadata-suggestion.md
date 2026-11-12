---
id: V2-25
title: "ai-service: gợi ý metadata chạy nền và đo độ trễ"
type: feat
status: review
created: 2026-10-19
updated: 2026-11-13
author: "Owner"
scope: ai-qa
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-21, V2-24]
blocks: [V2-33]
branch: "feat/ai-qa-async-metadata-suggestion"
assignee: pair
---

# TICKET V2-25: Gợi ý metadata chạy nền

## 1. Bối cảnh & Mục tiêu
PRD-V2 FR-28 và NFR hiệu năng. Code cũ gọi gợi ý **đồng bộ trong request upload** (`knowledge-service` `DocumentController` → ingestion `/metadata/suggest`, timeout 30 s), tải và parse lại file bằng `preview_extractor.py`, gọi Groq `llama-3.3-70b-versatile` (đã bị tắt theo CLAUDE.md) với `timeout=10`, `max_retries=2`.

## 2. Tiêu chí Hoàn thành
- [x] Job gợi ý chạy sau trích xuất, không nằm trên đường tới `READY`; upload trả về ngay.
- [x] Dùng lại `extracted_documents` (cấu trúc và Markdown chuẩn sau làm sạch, V2-20/V2-21); không tải hay parse lại file (test: job gợi ý chạy được khi object S3 đã bị xóa).
- [x] Luật trước: tiêu đề (heading đầu hoặc tên file), ngôn ngữ, mã số/lần ban hành/ngày hiệu lực (V2-21).
- [x] Một lần gọi LLM structured output cho mô tả, category (chỉ từ danh sách category hiện có của workspace, hoặc rỗng kèm tên đề xuất), tags (ưu tiên tags đã có). Đầu vào: tiêu đề, dàn ý heading, tối đa vài đoạn đại diện với trần token cấu hình được.
- [x] Timeout cấu hình được, tối đa một lần thử lại; provider lỗi thì lưu kết quả luật và đánh dấu `fallback`.
- [x] Cache theo `(workspace_id, sha256 nội dung, prompt_version, model, hash danh sách category)`; không dùng chung giữa workspace.
- [x] Gợi ý lưu riêng; chỉ áp dụng vào trường có nguồn khác `USER`; không bao giờ đổi phạm vi hiển thị hay phòng ban.
- [ ] Ghi số đo theo job: `t_upload_ack`, `t_ready`, `t_suggest`, độ trễ LLM, token vào/ra, `fallback`; báo cáo p50/p95 trên corpus V2-19 trước khi đặt mục tiêu.

## 2a. Bằng chứng và khoảng trống đã biết (cập nhật 2026-11-12)
- Đã có: test unit và integration (ai-service), `DocumentSuggestionIT` (core-api) gồm ca cô lập tenant, ca version của tài liệu khác bị từ chối không ghi, ca thiếu hoặc sai `X-Internal-Token` trả 401; ca worker mất lease không hoàn tất và không phát lại sự kiện.
- **Chưa đo:** `t_upload_ack`, `t_ready`, p50/p95 trên corpus V2-19. Chưa có số nào để đặt mục tiêu.
- **Đã chạy thật 2026-11-12 (một tài liệu, một lần):** `GET /models` của Groq trả 200 và có `qwen/qwen3.8-27b`. Upload `gitlab-meetings.md` qua `dev-login`: ingest xong `READY` sau khoảng 50 s (embedding `embed_ms=52257`, 6 chunk), rồi `suggest_done method=LLM attempts=1 cache_hit=False llm_ms=2135`. Mô tả, ngôn ngữ được điền với nguồn `SUGGESTED`. Đây là một mẫu, chưa phải p50/p95.
- **Số đo ban đầu 2026-11-12** (`scripts/measure-ingest-latency.ps1`, 5 tài liệu markdown nhỏ nạp tuần tự, không fallback): `t_upload_ack` p50 27 ms, p95 34 ms; `t_ready` p50 468 ms, p95 926 ms; `t_suggest` p50 454 ms, p95 940 ms (gần như toàn bộ là `llm_ms`). **Không dùng làm mục tiêu:** n = 5 và `t_ready` bị méo vì cache embedding (hai tài liệu GitLab đã nhúng trước đó, `embed_cached` = số chunk; ba tài liệu smoke chỉ có 1 chunk ngắn). Embedding thật trên CPU: tài liệu 5 chunk chưa cache mất `embed_ms` = 12 864 (lần đầu sau khi worker khởi động mất 52 257, gồm nạp model).
- **Chưa đo:** p50/p95 trên corpus V2-19 với nội dung chưa cache. Cần corpus đủ lớn (ít nhất vài chục tài liệu) và chạy trên cache trống, hoặc báo `t_ready` tách riêng phần embedding.
- **Quyết định owner 2026-11-12:**
  - Dùng Groq cho gợi ý (ADR-006 §4.4).
  - Gợi ý chạy **cùng vòng lặp worker, sau ingest** (không tách tiến trình): thực đo khoảng 2 s/job; xấu nhất khoảng 40 s (timeout 20 s, một lần thử lại) chỉ làm chậm ingest kế tiếp, không làm hỏng `READY`. Lỗi provider cho kết quả rỗng `RULES_FALLBACK`. Chỉ tách tiến trình nếu nhập hàng loạt khi Groq suy giảm.
  - **Tiêu đề gợi ý không tự áp dụng**, chỉ lưu; quy tắc ở TECH-V2-core-api (mục áp dụng gợi ý). Chưa có endpoint để người dùng nhận tiêu đề gợi ý.
  - **Form gợi ý (owner chốt 2026-11-12):** một form chỉnh sửa được, điền sẵn từ tài liệu và `suggestions`, mỗi trường kèm nhãn nguồn (`fieldSources`). Để trống tiêu đề = giữ tên tệp (UI bỏ `title` khỏi `PATCH`, vì backend không nhận tiêu đề rỗng). Bắt buộc description/category/tags chỉ là quy tắc UI; category chỉ bắt buộc khi workspace đã có category.
  - **`doc_code`, `revision_label`, `effective_date` chỉ đọc** trong form, kèm ghi chú "trích xuất tự động, có thể sai" (extractor không bảo đảm đúng). Sửa các trường này cần endpoint cấp version, để sau.
  - **Category mới:** nút "tạo category gợi ý" ở cuối dropdown, chỉ OWNER/ADMIN (`requireManager`): `POST /categories` rồi `PATCH categoryId`. Publisher chỉ chọn category có sẵn và thấy tên gợi ý dạng văn bản. Người đề xuất tên category là bước gợi ý (AI), không phải publisher; trong lúc chờ, category để trống. Luồng publisher tự đề xuất, admin duyệt, thông báo là ticket riêng.
  - **Nhiều tài liệu gợi ý cùng một ý với tên khác nhau** (ví dụ "Mua hàng", "Quy trình mua sắm"): admin gom theo tên gợi ý, nhập **một** tên (hoặc chọn category có sẵn) rồi áp dụng cho cả nhóm. Cần endpoint liệt kê tài liệu có `proposedCategoryName` chưa áp dụng và endpoint gán category hàng loạt (chưa có; ticket riêng cùng luồng duyệt).

- **Cập nhật 2026-11-13:** chuyển `review` (mã, migration `core/V010`, `rag/V004` và test đã commit). Không đổi mã trong đợt này. Tiêu chí số đo vẫn mở: p50/p95 của `t_upload_ack`, `t_ready`, `t_suggest` trên corpus V2-19 với cache embedding trống; chưa đặt mục tiêu. Bulk gán category cho nhóm đề xuất và luồng publisher đề xuất/admin duyệt là ticket riêng sau này, không làm ở đây.

## 3. Hướng dẫn
- Phương án nâng cấp (chỉ khi số đo cho thấy cần): phân loại category bằng embedding gần nhất thay cho LLM, hoặc model nhỏ hơn. Ghi lựa chọn và số đo vào báo cáo.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Luật trích tiêu đề/ngôn ngữ/mã số; ràng buộc category trong danh sách; không ghi đè trường `USER`; fallback khi timeout | `uv run pytest tests/unit` |
| Integration | Upload → `READY` không chờ LLM (LLM mock chậm); cache không trúng chéo workspace | `uv run pytest tests/integration` |
