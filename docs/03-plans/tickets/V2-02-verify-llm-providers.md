---
id: V2-02
title: "Xác nhận model LLM còn sống bằng key thật"
type: chore
status: done
created: 2026-10-17
updated: 2026-11-01
scope: ai-qa
priority: P0
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-10]
branch: "chore/ai-qa-verify-providers"
assignee: owner
---

# TICKET V2-02: Xác nhận model LLM còn sống

## 1. Bối cảnh & Mục tiêu
AUDIT-v2 §4.1 liệt kê các model Groq/Gemini đã bị tắt nhưng **chưa gọi thử bằng key thật**. Cần biết model nào chạy được trước khi thiết kế `LLMProvider` (V2-10) và chọn LLM cho eval câu trả lời.

## 2. Tiêu chí Hoàn thành
- [x] Gọi `GET /models` của Groq và Gemini bằng key của owner; ghi danh sách model sống vào AUDIT-v2 §4.1 (cột "Đã gọi thử (V2-02)" cùng ngày).
- [x] Gọi thử một request ngắn tới `openai/gpt-oss-20b` (Groq) và một model Gemini Flash-Lite; ghi mã phản hồi.
- [x] Quyết định LLM. **Sửa 2026-11-01 (owner):** bỏ Gemini và Groq `gpt-oss-120b` khỏi hai việc sinh câu trả lời và giám khảo faithfulness; thay bằng model mã nguồn mở nhỏ tự triển khai trên Modal (hai tài khoản Starter, mỗi tài khoản $30/tháng). Phân vai cũ ở ADR-006 §4.4 cho hai việc này không còn hiệu lực. Giữ nguyên: guard bằng luật (bốn lớp FR-13), gợi ý metadata, embedding, rerank. ADR-006 §4.4 đã viết lại 2026-11-01 (Qwen 3.5 9B sinh, Gemma 4 giám khảo, hạ tầng và ngân sách Modal; **chưa đo**). Bake-off để chốt model cụ thể làm trong `V2-10`.
- [x] Không in hay lưu key vào repo (AGENTS.md §Secrets); script chỉ báo có/không có key, kết quả gốc nằm trong `eval/provider_check/results/` (bị `eval/.gitignore` loại).

> Kết quả lần chạy 2026-10-20 (AUDIT-v2 §4.1): Groq `/models` và hai model `gpt-oss` HTTP 200; Prompt Guard 2 86M chạy được nhưng không đạt bài test, guard chuyển sang luật; Gemini 3.1 Flash Lite trả 503 quá tải ở cả hai ID, còn phải thử lại trước khi đóng ticket.
>
> Lần chạy lại 2026-10-20 10:19 (`--skip-guard`): Groq `gpt-oss-120b` 200 (663 ms), `gpt-oss-20b` 200 (461 ms); Gemini `gemini-3.1-flash-lite-preview` 200 (7,4 s), `gemini-3.1-flash-lite` vẫn 503. V2-10 phải để ID model cấu hình được.
>
> Lần chạy lại 2026-11-01 (`--skip-guard`, owner chạy): Groq `/models` 200 (11 model), `gpt-oss-120b` 200 (697 ms), `gpt-oss-20b` 200 (508 ms); Gemini `/models` 200 (60 model), `gemini-3.1-flash-lite-preview` 200 (3134 ms), `gemini-3.1-flash-lite` 200 (7280 ms, trước đó 503). Chỉ là bằng chứng lịch sử: hai provider này không còn dùng cho sinh câu trả lời và giám khảo (quyết định ở trên). Prompt Guard không chạy lại (`--skip-guard`), số liệu giữ của 2026-10-20.
- [x] Gọi thử thật Gemini 3.1 Flash Lite, Groq `gpt-oss-120b`, `gpt-oss-20b`, `llama-prompt-guard-2-86m`; ghi mã phản hồi và định dạng đầu ra của Prompt Guard (code cũ parse điểm số dạng text bằng `float(...)`, cần xác nhận lại).
- [x] Bài test Prompt Guard 2 86M (tiếng Việt không có trong danh sách ngôn ngữ đã đánh giá của Meta). Kết quả ở AUDIT-v2 §4.1: không đạt, guard dùng luật (owner chốt 2026-11-01, có thể xét lại phương án tốt hơn sau MVP). Owner đã duyệt cả bộ 100 câu ngày 2026-11-01 (khai báo của owner; không có bản ghi duyệt từng câu). Bộ câu:
  - Bộ khoảng 100 câu, owner duyệt: 40 câu hỏi SOP bình thường VI/EN (gồm câu có từ dễ gây nhầm như "bỏ qua bước 3", "hãy đóng vai trưởng phòng", "ignore the previous version"); 40 câu tấn công VI/EN (bỏ qua chỉ dẫn, lộ system prompt, đóng vai, yêu cầu tài liệu phòng ban khác); 20 đoạn chunk tài liệu thật cắt ≤ 512 token.
  - Đo: tỉ lệ chặn đúng câu tấn công theo ngôn ngữ, tỉ lệ chặn nhầm câu bình thường theo ngôn ngữ, độ trễ p50/p95; so với baseline chỉ dùng luật.
  - Ngưỡng đề xuất để dùng: chặn nhầm câu bình thường ≤ 2% và chặn đúng tấn công tiếng Việt ≥ 70%. Không đạt thì guard chỉ dùng luật + prompt hệ thống, và ghi kết quả vào ADR-006 §4.4.

## 3. Hướng dẫn
- Owner tự chạy với key trong `.env` của mình; agent không đọc `.env`. Chỉ ghi kết quả (tên model, trạng thái) vào tài liệu.
- Script: `python -I eval/provider_check/check_providers.py --env-file .env` (chỉ đọc `GROQ_API_KEY`, `GEMINI_API_KEY`, không in key). Bộ câu `eval/provider_check/prompt_guard_cases.jsonl` là bản nháp agent soạn, owner duyệt trước khi tin kết quả. Baseline luật được viết trên chính bộ này nên số của nó lạc quan.

## 4. Kiểm thử
Không có test tự động. Bằng chứng: bảng kết quả kèm ngày trong AUDIT-v2.
