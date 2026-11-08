---
id: V2-10
title: "ai-service: pipeline hỏi đáp 2 lần gọi LLM, SSE, trích dẫn, từ chối"
type: feat
status: todo
created: 2026-10-17
updated: 2026-10-24
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-02, V2-09]
blocks: [V2-13, V2-15, V2-16, V2-26, V2-27, V2-28, V2-32]
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
- [ ] Sửa 2026-10-21 (audit đầu-cuối theo loại query, owner chốt D2/D4/D5/D8; TECH-V2-ai-service §7.1): **đầu vào.** Câu rỗng hoặc dài hơn `SOPILOT_MAX_QUESTION_CHARS` (1000, code point sau NFC) bị từ chối, không cắt bớt: `refusal INPUT_INVALID`, `outcome = TEMPLATE`, không tính hạn mức. "Token có nghĩa" = token có trong `rag.chunk_terms` của tập tài liệu người hỏi được đọc (cùng CTE `scope` của §6.3) hoặc trong `qa/lexicon.yaml` (owner duyệt); dưới `min_meaningful_tokens` (mặc định 1) trả câu mẫu "chưa hiểu câu hỏi" (`INPUT_INVALID`), không truy xuất. Vector câu gốc chỉ dùng lại cho dense khi văn bản làm việc (sau che PII và bóc) trùng câu gốc; ngược lại embed lại.
- [ ] Sửa 2026-10-21 (D5): **viết lại và nối tiếp.** Ghi `messages.rewrite_status`. Viết lại lỗi và câu có dấu hiệu nối tiếp (`qa/followup_rules.yaml`: "đó", "này", "vậy còn", "thế còn", "it", "that", "what about", hoặc ít hơn `SOPILOT_FOLLOWUP_MAX_TOKENS` token) → câu mẫu đề nghị nêu đầy đủ câu hỏi, không truy xuất, `route.layer = 'followup_rule'`; không có dấu hiệu nối tiếp thì dùng câu gốc. Prompt sinh nhận câu đã viết lại cộng câu gốc, **không** nhận lịch sử hội thoại; test bằng provider giả ghi lại prompt.
- [ ] Sửa 2026-10-21 (D2): **outcome.** Điền `messages.refusal_reason` (`NO_EVIDENCE`, `GENERATOR_NOT_FOUND`, `OUT_OF_SCOPE`, `INPUT_INVALID`, TECH-V2-ai-service §3.4). System prompt bắt buộc câu mở đầu cố định khi source không có thông tin; so khớp chuỗi tất định (VI/EN) → `outcome = REFUSED_NO_EVIDENCE`, `GENERATOR_NOT_FOUND`, không lưu trích dẫn. Câu `ANSWERED` không có `[n]` hợp lệ nào ghi `checks.citationCount = 0`. Hàm `qa/pipeline.py` cung cấp điểm gắn `OUT_OF_SCOPE` cho router của `V2-27` (chỉ sau khi cổng từ chối, không kèm tài liệu gần nhất). Mục "Dưới ngưỡng bằng chứng… ghi vào danh sách chưa trả lời được" bên dưới chỉ áp dụng cho `NO_EVIDENCE` và `GENERATOR_NOT_FOUND`.
- [ ] Sửa 2026-10-21 (D3, P0-5, P1-4): **prompt.** `<source>` có `code`, `rev`, `effective` lấy từ `extracted_documents.extracted_meta` của `version_id` source (bảng `rag`, không đọc `core`; thuộc tính thiếu thì bỏ; escape), không đổi `index_text`; system prompt có dòng "Hôm nay là {ngày}" theo `SOPILOT_TIMEZONE`; thêm quy tắc câu tình huống (liệt kê điều kiện, nói điều kiện nào thỏa hoặc chưa đủ dữ kiện, trả lời dạng "nếu … thì …"); đổi `prompt_version`.
- [ ] Sửa 2026-10-21 (D8, P1-9): **PII.** `qa/pii.py` che email, số điện thoại VN, và CCCD/CMND, số tài khoản khi đi sau từ khóa (`cccd`, `cmnd`, `căn cước`, `hộ chiếu`, `stk`, `số tài khoản`…) bằng `[EMAIL]`, `[PHONE]`, `[ID]`, `[ACCOUNT]` trước guard, router, viết lại, embed và prompt; ghi `guard_events(INPUT_FLAG)` `rule_id = pii.*`. `messages.content` giữ nguyên văn; danh sách khoảng trống (`V2-13`) hiện bản đã che. Test: số tiền `500.000.000` không bị che; ca sát (chuỗi số không có từ khóa) không bị che.
- [ ] Sửa 2026-10-21 (P1-3): **kiểm số và ngày.** `qa/checks.py` (hàm thuần) đối chiếu số, ngày, số tiền trong câu trả lời cuối với nội dung các source; giá trị không có trong source → `done.warnings` `NUMBER_NOT_IN_SOURCES` và `checks.numberWarnings`. Chỉ gắn cờ, không sửa văn bản. Đo tương quan với nhãn faithfulness của tập con.
- [ ] Sửa 2026-10-21 (P1-5): **fallback.** Chỉ chuyển model kế tiếp trước khi phát `delta` đầu tiên; lỗi sau đó → `error LLM_UNAVAILABLE`, `outcome = ERROR`, hoàn lượt hạn mức. `models.yaml` có `context_max_tokens` theo model (đặt cho Groq sau khi đo trên dev); chuyển sang model có trần thấp hơn thì ghép lại context với trần đó. Ước lượng token prompt cho ngân sách dùng tokenizer của chính model nếu khai báo, không dùng cho chunking.
- [ ] Sửa 2026-10-21 (P0-8, P1-7): `messages.route`, `rewrite_status`, `checks` được điền cho mọi câu (cột nằm trong migration của `V2-09`). Đo TTFT đầu-cuối ở `V2-16`.
- [ ] Từ điển thô tục VI/EN trong `qa/guard_rules.yaml`, so khớp theo ranh giới từ (không theo chuỗi con). Từ trùng nghĩa thường khi bỏ dấu (vd. dạng bỏ dấu trùng "các"; "ngu" trong "nguồn"; "cc"/"đm" có thể là "chứng chỉ"/"định mức") chỉ so trên văn bản còn dấu; dạng bỏ dấu chỉ dùng cho teencode không có nghĩa khác.
- [ ] Nhóm có hại thật (đe dọa, tự hại, quấy rối người có tên) có luật riêng ở mức chặn: câu cố định, riêng tự hại kèm câu hỗ trợ và đầu mối liên hệ cấu hình được; `guard_events(INPUT_BLOCK)` chỉ lưu `rule_id`, không lưu nguyên văn.
- [ ] Câu đi nhánh `TEMPLATE` không tính hạn mức và không vào danh sách chưa trả lời được (V2-13). System prompt có quy tắc giữ giọng trung lập khi câu hỏi có lời lẽ thô tục.
- [ ] Bộ giới hạn tốc độ theo provider (RPM/TPM) luôn bật, tự chuyển sang dự phòng khi 429 (ADR-006 §4.4). Hạn mức câu hỏi theo user và trần toàn hệ thống cấu hình được, **mặc định tắt** (owner chốt 2026-10-20, FR-09, TECH-V2-ai-service §7.4).
- [ ] SSE stream; trả lời theo ngôn ngữ câu hỏi (VI/EN).
- [ ] Mỗi `[n]` ánh xạ `document_id`, `page`, đoạn trích; trích dẫn không ánh xạ được bị loại.
- [ ] Sửa 2026-10-21 (TECH-V2-ai-service §6.4a): ghép context small-to-big trong `retrieval/context.py` (hàm thuần, `eval/` import được): nhóm cùng `section_path` của chunk trúng, nhóm ≤ `section_max_tokens` lấy nguyên, lớn hơn lấy ±1 kèm đoạn dẫn của mục cho `PROCEDURE_STEP`/`TABLE`, gộp cửa sổ liền nhau, trần `context.max_tokens`; truy vấn chunk mở rộng đi qua bộ lọc quyền §6.1; `[n]` trỏ source, khoảng trích dẫn chỉ phủ chunk trúng; ghi `messages.context_sources`. `context.expand = false` giữ hành vi chỉ đưa chunk trúng.
- [ ] Ablation ghép context trên tập con cố định của harness: `expand` bật/tắt, báo cáo độ phủ bằng chứng (tỉ lệ gold span nằm trong context, không cần LLM, chạy trên toàn tập test), faithfulness, citation precision, số token prompt; tách riêng câu hỏi về điều kiện/ngoại lệ và câu nhiều passage. Mặc định `expand` giữ `true` trừ khi số đo cho thấy kém hơn.
- [ ] Dưới ngưỡng bằng chứng: trả lời "không tìm thấy" kèm tài liệu gần nhất, `refusal_reason = NO_EVIDENCE`, ghi vào danh sách chưa trả lời được. Sửa 2026-10-21: RQ3 mức câu trả lời báo cáo tách **cổng từ chối** (`NO_EVIDENCE`) khỏi **LLM tự từ chối** (`GENERATOR_NOT_FOUND`) ([HANDOFF-research-03](../../04-reports/HANDOFF-research-03-methods-and-models.md) §7.2).
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
| Unit | đầu vào (rỗng, > 1000 ký tự, không token có nghĩa), nối tiếp khi viết lại lỗi, PII, câu mở đầu cố định → `GENERATOR_NOT_FOUND`, kiểm số/ngày, fallback không chuyển sau `delta` đầu tiên; prompt không chứa lịch sử | `uv run pytest tests/unit` |
| Integration | câu hỏi trả lời được / không trả lời được trên DB thật, LLM mock | `uv run pytest tests/integration` |
| Nghiệm thu | phần tiếng Việt (ô gộp, mã tài liệu, hiệu lực, không dấu) đo bằng bộ kiểm `V2-28` sau khi có ticket đó; không chặn `done` của ticket này | — |
| Thủ công | một câu hỏi thật với provider thật, ghi model và kết quả | — |

### Owner đơn giản hóa chọn model 2026-11-04
Owner bỏ bake-off đầy đủ (4 tiêu chí so sánh Qwen 9B/4B trong ADR-006 §4.4). Chốt **Qwen3.5-9B FP8 trên L4** làm model sinh câu trả lời, chỉ chạy một lần kiểm nhanh khoảng 20 câu từ `sop-main` trước khi cam kết (đúng ngôn ngữ, `[n]` đúng nguồn, TTFT lạnh/nóng, kiểm `enable_thinking=false` có hiệu lực). Có bảng ứng viên thay thế theo triệu chứng (Qwen3-8B, Qwen3.5-4B, Gemma 4 E4B, Gemma 4 26B A4B) và ràng buộc đổi giám khảo nếu chuyển sang Gemma 4, ở ADR-006 §4.4. Giữ nguyên `LLMProvider` kiểu OpenAI-compatible để đổi model chỉ bằng cấu hình. Chưa có số đo tiếng Việt giữa các ứng viên; chưa kiểm điều khoản dùng hai tài khoản Modal.
