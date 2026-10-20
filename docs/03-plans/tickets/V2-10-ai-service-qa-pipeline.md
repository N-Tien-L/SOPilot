---
id: V2-10
title: "ai-service: pipeline hỏi đáp 2 lần gọi LLM, SSE, trích dẫn, từ chối"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-21
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-02, V2-09]
blocks: [V2-13, V2-15, V2-16, V2-26, V2-27]
branch: "feat/ai-qa-v2-qa-pipeline"
assignee: pair
---

# TICKET V2-10: Pipeline hỏi đáp

## 1. Bối cảnh & Mục tiêu
Thay pipeline 5–6 lần gọi LLM bằng guard + sinh câu trả lời. Sửa việc dùng model đã bị tắt.

## 2. Tiêu chí Hoàn thành
- [ ] `LLMProvider` kiểu OpenAI-compatible (Gemini, Groq, Ollama/llama.cpp) chọn bằng env; không gán cứng model ID; khởi động gọi `/models` và cảnh báo nếu model bị gỡ.
- [ ] Mỗi câu hỏi tối đa 1 lần gọi LLM sinh (guard bằng luật, có bộ câu kiểm tra riêng không trùng bộ dùng để viết luật); viết lại câu hỏi chỉ khi có lịch sử; tiêu đề hội thoại sinh bằng luật.
- [ ] Định tuyến bằng luật (FR-13): chào hỏi/cảm ơn/hỏi về bot (VI/EN) trả lời bằng mẫu, không gọi LLM; dưới ngưỡng bằng chứng thì từ chối mà không gọi LLM sinh. Không có node LLM phân loại ý định (tầng semantic router dùng embedding thêm sau luật ở `V2-27`; `router.py` để sẵn chỗ cho tầng này).
- [ ] Router theo kiểu "bóc rồi xét": bỏ token chào hỏi/cảm ơn/thô tục khỏi câu đã chuẩn hóa; phần còn lại rỗng hoặc dưới ngưỡng token có nghĩa (cấu hình được) thì trả câu mẫu theo loại token đã bỏ (`outcome = TEMPLATE`); còn nội dung thì chạy RAG trên phần đã bóc. Câu chỉ chửi bot nhận câu mẫu trung tính kèm gợi ý cách hỏi; câu thô tục kèm câu hỏi vẫn được trả lời và ghi `guard_events(INPUT_FLAG)`.
- [ ] Từ điển thô tục VI/EN trong `qa/guard_rules.yaml`, so khớp theo ranh giới từ (không theo chuỗi con). Từ trùng nghĩa thường khi bỏ dấu (vd. dạng bỏ dấu trùng "các"; "ngu" trong "nguồn"; "cc"/"đm" có thể là "chứng chỉ"/"định mức") chỉ so trên văn bản còn dấu; dạng bỏ dấu chỉ dùng cho teencode không có nghĩa khác.
- [ ] Nhóm có hại thật (đe dọa, tự hại, quấy rối người có tên) có luật riêng ở mức chặn: câu cố định, riêng tự hại kèm câu hỗ trợ và đầu mối liên hệ cấu hình được; `guard_events(INPUT_BLOCK)` chỉ lưu `rule_id`, không lưu nguyên văn.
- [ ] Câu đi nhánh `TEMPLATE` không tính hạn mức và không vào danh sách chưa trả lời được (V2-13). System prompt có quy tắc giữ giọng trung lập khi câu hỏi có lời lẽ thô tục.
- [ ] Bộ giới hạn tốc độ theo provider (RPM/TPM) luôn bật, tự chuyển sang dự phòng khi 429 (ADR-006 §4.4). Hạn mức câu hỏi theo user và trần toàn hệ thống cấu hình được, **mặc định tắt** (owner chốt 2026-10-20, FR-09, TECH-V2-ai-service §7.4).
- [ ] SSE stream; trả lời theo ngôn ngữ câu hỏi (VI/EN).
- [ ] Mỗi `[n]` ánh xạ `document_id`, `page`, đoạn trích; trích dẫn không ánh xạ được bị loại.
- [ ] Dưới ngưỡng bằng chứng: trả lời "không tìm thấy" kèm tài liệu gần nhất, ghi vào danh sách chưa trả lời được.
- [ ] Guard bốn lớp theo FR-13: chuẩn hóa + luật VI/EN hai mức (chặn / gắn cờ), chunk bọc thẻ dữ liệu có escape, canary token kiểm đầu ra, log cờ guard.
- [ ] Bộ câu kiểm tra guard riêng (80–100 câu, owner duyệt, không trùng `eval/provider_check/prompt_guard_cases.jsonl`) gồm ≥ 10 câu đòi lộ system prompt, ≥ 15 câu thô tục VI/EN (có teencode, không dấu, kèm và không kèm câu hỏi) và ≥ 15 câu hợp lệ dễ chặn nhầm (các ca trùng khi bỏ dấu ở trên): chặn nhầm câu hợp lệ ≤ 2%, 0 lần lộ canary; báo cáo tỉ lệ chặn đúng ở lớp luật. Chạy trong CI.
- [ ] Hội thoại chỉ người tạo xem được (lọc theo user và workspace). Khi mở lại, câu trả lời có trích dẫn tới tài liệu không còn quyền bị ẩn kèm lý do (ADR-007 §4.5).
- [ ] Rerank và context LLM chỉ nhận ứng viên đã lọc quyền; cache câu trả lời/truy xuất (nếu có) có khóa gồm `workspace_id`, `wrole`, `wdept`.
- [ ] Mở rộng harness: đo citation precision, tỉ lệ từ chối đúng, faithfulness trên tập con cố định (LLM cố định, `temperature=0`).

## 3. Hướng dẫn
- **File:** `services/ai-service/src/sopilot_ai/{qa,providers,conversations,quota,api}` theo TECH-V2-ai-service §1.1 (`qa/pipeline.py`, `qa/guard.py`, `qa/router.py`, `qa/prompt.py`, `qa/citations.py`, `providers/llm.py`); harness thêm `eval/sopilot_eval/answers.py`.
- Có thể tham khảo `services/ai-qa-service/src/services/generation/prompt_builder.py` nhưng không port intent classification.
- Không port `layer1_toxic_filter.py`: nó gọi `llama-guard-3-8b`/`llama-3.1-8b-instant` (đã ngừng) và coi lỗi gọi là an toàn.
- `rule_id` theo nhóm: `inject.*`, `abuse.*`, `harm.*`, `template.*`; không cần đổi CHECK của `rag.guard_events.layer`.
- Cập nhật TECH-V2-ai-service §7.1 bước 2–3 (từ điển thô tục, "bóc rồi xét", nhóm có hại) trong cùng thay đổi.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | trích dẫn không hợp lệ bị loại, đếm số lần gọi LLM ≤ 2 (mock) | `uv run pytest tests/unit` |
| Unit | "bóc rồi xét": câu chỉ chửi → `TEMPLATE`, chửi kèm câu hỏi → RAG với câu đã bóc, các ca trùng khi bỏ dấu không bị chặn | `uv run pytest tests/unit` |
| Integration | câu hỏi trả lời được / không trả lời được trên DB thật, LLM mock | `uv run pytest tests/integration` |
| Thủ công | một câu hỏi thật với provider thật, ghi model và kết quả | — |
