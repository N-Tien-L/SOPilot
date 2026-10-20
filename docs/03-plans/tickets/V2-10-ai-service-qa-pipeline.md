---
id: V2-10
title: "ai-service: pipeline hỏi đáp 2 lần gọi LLM, SSE, trích dẫn, từ chối"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-20
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-02, V2-09]
blocks: [V2-13, V2-15, V2-16, V2-26]
branch: "feat/ai-qa-v2-qa-pipeline"
assignee: pair
---

# TICKET V2-10: Pipeline hỏi đáp

## 1. Bối cảnh & Mục tiêu
Thay pipeline 5–6 lần gọi LLM bằng guard + sinh câu trả lời. Sửa việc dùng model đã bị tắt.

## 2. Tiêu chí Hoàn thành
- [ ] `LLMProvider` kiểu OpenAI-compatible (Gemini, Groq, Ollama/llama.cpp) chọn bằng env; không gán cứng model ID; khởi động gọi `/models` và cảnh báo nếu model bị gỡ.
- [ ] Mỗi câu hỏi tối đa 1 lần gọi LLM sinh (guard bằng luật, có bộ câu kiểm tra riêng không trùng bộ dùng để viết luật); viết lại câu hỏi chỉ khi có lịch sử; tiêu đề hội thoại sinh bằng luật.
- [ ] Định tuyến bằng luật (FR-13): chào hỏi/cảm ơn/hỏi về bot (VI/EN) trả lời bằng mẫu, không gọi LLM; dưới ngưỡng bằng chứng thì từ chối mà không gọi LLM sinh. Không có node LLM phân loại ý định.
- [ ] Bộ giới hạn tốc độ theo provider (RPM/TPM), trần câu hỏi/ngày toàn hệ thống, tự chuyển sang dự phòng khi 429 (FR-09, ADR-006 §4.4).
- [ ] SSE stream; trả lời theo ngôn ngữ câu hỏi (VI/EN).
- [ ] Mỗi `[n]` ánh xạ `document_id`, `page`, đoạn trích; trích dẫn không ánh xạ được bị loại.
- [ ] Dưới ngưỡng bằng chứng: trả lời "không tìm thấy" kèm tài liệu gần nhất, ghi vào danh sách chưa trả lời được.
- [ ] Guard bốn lớp theo FR-13: chuẩn hóa + luật VI/EN hai mức (chặn / gắn cờ), chunk bọc thẻ dữ liệu có escape, canary token kiểm đầu ra, log cờ guard.
- [ ] Bộ câu kiểm tra guard riêng (80–100 câu, owner duyệt, không trùng `eval/provider_check/prompt_guard_cases.jsonl`) gồm ≥ 10 câu đòi lộ system prompt: chặn nhầm câu hợp lệ ≤ 2%, 0 lần lộ canary; báo cáo tỉ lệ chặn đúng ở lớp luật. Chạy trong CI.
- [ ] Hội thoại chỉ người tạo xem được (lọc theo user và workspace). Khi mở lại, câu trả lời có trích dẫn tới tài liệu không còn quyền bị ẩn kèm lý do (ADR-007 §4.5).
- [ ] Rerank và context LLM chỉ nhận ứng viên đã lọc quyền; cache câu trả lời/truy xuất (nếu có) có khóa gồm `workspace_id`, `wrole`, `wdept`.
- [ ] Mở rộng harness: đo citation precision, tỉ lệ từ chối đúng, faithfulness trên tập con cố định (LLM cố định, `temperature=0`).

## 3. Hướng dẫn
- **File:** `services/ai-service/src/{pipeline,llm,api}`; harness thêm `eval/sopilot_eval/answers.py`.
- Có thể tham khảo `services/ai-qa-service/src/services/generation/prompt_builder.py` nhưng không port intent classification.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | trích dẫn không hợp lệ bị loại, đếm số lần gọi LLM ≤ 2 (mock) | `uv run pytest tests/unit` |
| Integration | câu hỏi trả lời được / không trả lời được trên DB thật, LLM mock | `uv run pytest tests/integration` |
| Thủ công | một câu hỏi thật với provider thật, ghi model và kết quả | — |
