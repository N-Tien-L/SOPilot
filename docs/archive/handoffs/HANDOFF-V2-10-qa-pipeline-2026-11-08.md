---
id: HANDOFF-V2-10-QA-PIPELINE-2026-11-08
title: "Bàn giao triển khai V2-10: pipeline hỏi đáp và ba điều chỉnh owner chốt"
status: final
created: 2026-11-08
updated: 2026-11-08
type: handoff
scope: ai-qa
milestone: V2
author: "Owner"
refs:
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-10-ai-service-qa-pipeline.md
  - docs/architecture/components/ai-service.md
  - docs/04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-07-run-rq1-rq3-rq5.md
  - docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-27-semantic-router.md
---

# Handoff: V2-10 pipeline hỏi đáp (phase 2: triển khai)

Bạn làm việc trong repo SOPilot (`C:\Users\Tien\Workspace\Personal\SOPilot`). Nhiệm vụ: triển khai ticket **V2-10** (`docs/execution/initiatives/v2-sopilot-mvp/tickets/V2-10-ai-service-qa-pipeline.md`) trong `services/ai-service`, kèm 3 điều chỉnh owner đã chốt ở mục 2. Kiến trúc QA của V2 **giữ nguyên**; không thiết kế lại.

## 1. Đọc trước khi code (bắt buộc)

1. `CLAUDE.md` (ràng buộc kỹ thuật 1–13, lệnh, drift V2) và `.claude/rules/ai-service.md` (cấu trúc package, `tenant_tx`, `allowed_cte()`, cấu hình model, test). Nếu đụng schema: `.claude/rules/migrations.md`.
2. Skill `execute-ticket` (quy trình ticket), `testing` (viết và chọn bộ test), `flyway-migration` (chỉ khi cần migration). Review bằng agent `v2-reviewer` trước khi đề xuất commit.
3. Ticket V2-10 (toàn bộ tiêu chí hoàn thành) và `docs/architecture/components/ai-service.md`: §1.1 (cấu trúc package), §3.4 (bảng hội thoại, retrieval, guard), §4.2–4.3 (models.yaml, interface provider), §6.4–6.4a (cổng ngưỡng, ghép context), §7 (toàn bộ), §11a (D1–D11), §12, §12a.
4. Code đã có: `src/sopilot_ai/retrieval/` (`retriever.py`, `fusion.py`, `search.py`, `access_filter.py`), `src/sopilot_ai/providers/` (`registry.py`, `embedding.py`, `rerank.py`), `src/sopilot_ai/qa/doc_code.py`, `config/models.yaml`, `src/sopilot_ai/api/app.py`. Migration của các bảng `rag.messages`, `rag.guard_events`, `rag.message_citations`… đã có từ V2-09 trong `infrastructure/db/migrations/rag/`; bảng mô tả ở `.agent/context/database/tables/rag.md`. Kiểm cột thật trên đĩa trước khi dùng; code thắng tài liệu. Test giả có sẵn ở `tests/fakes.py`.
6. `docs/execution/initiatives/v2-sopilot-mvp/PLAN.md` dòng "Owner chốt 2026-11-01" và ADR-006 §4.4 (model sinh và giám khảo tự host trên Modal).
5. `docs/04-reports/AUDIT-eval-rq1-rq3-2026-11-04.md` §6 (vì sao cosine là cổng yếu) và V2-07 §6 (chốt 2026-11-07).

## 2. Quyết định của owner (không bàn lại)

**Giữ nguyên:** guard bằng luật hai mức + nhóm có hại; che PII; "bóc rồi xét"; router luật (semantic router là V2-27, chỉ để sẵn chỗ trong `qa/router.py`); tối đa 2 lần gọi LLM mỗi câu (viết lại chỉ khi có lịch sử, và sinh); ghép context small-to-big §6.4a; canary + giữ lại cuối stream; `refusal_reason`; kiểm số và ngày chỉ gắn cờ; SSE.

**Không làm:** LLM phân loại ý định; LLM trả lời kiến thức chung; regenerate; thao tác ghi tài liệu qua chat; tách câu nhiều ý (D9 vẫn hoãn); nhánh hỏi lại; bật rerank mặc định.

**Ba điều chỉnh mới, làm trong V2-10:**

1. **Pipeline là chuỗi bước.** `qa/pipeline.py` chạy một danh sách bước; mỗi bước nhận một context dùng chung và trả về `Decision` thuộc `continue | template | refuse | clarify`. `clarify` chỉ khai báo trong kiểu, chưa bước nào phát ra (dành cho ticket sau). Thứ tự bước theo TECH §7.1 (hạn mức → kiểm đầu vào → PII → guard → router luật → token có nghĩa → viết lại/nối tiếp → truy xuất + cổng → ghép context → prompt → sinh/stream + canary → hậu xử lý trích dẫn → nhận diện tự từ chối → kiểm số/ngày). Điểm gắn `OUT_OF_SCOPE` cho V2-27 nằm ở bước từ chối sau cổng.
2. **`qa/query_frame.py`:** hàm thuần dựng `QueryFrame` một lần sau bước PII, gom: ngôn ngữ (luật tỉ lệ ký tự có dấu, ghi đè được bằng `lang` của request), mã tài liệu (dùng lại `qa/doc_code.py`), ngày và số tiền, dấu hiệu nối tiếp (`qa/followup_rules.yaml`), dấu hiệu so sánh/nhiều ý (danh sách từ khóa trong YAML, ví dụ "so sánh", "khác nhau", "khác gì", "vs", "compare", "difference", hoặc ≥ 2 mã tài liệu), số token có nghĩa. Router, truy xuất và prompt đọc từ `QueryFrame`, không tự phát hiện lại. Dấu hiệu so sánh **chỉ ghi** vào `messages.route` (ví dụ `route.signals.comparison = true`), không rẽ nhánh.
3. **Cổng ngưỡng để lỏng, LLM tự từ chối.** Giữ ngưỡng giữ chỗ hiện có trong `config/models.yaml` (`hybrid: 0.45`, chỉ chặn khi điểm rất thấp; không hạ thêm, không đặt giá trị mới từ số RQ3). Câu qua cổng nhưng LLM mở đầu bằng câu cố định → `GENERATOR_NOT_FOUND` (D2). Luôn ghi `gate_score`, `threshold` và loại từ chối để hiệu chỉnh sau. Ghi rõ lý do trong TECH §7.1.

## 3. Mốc làm việc (dừng báo cáo owner sau mỗi mốc)

**Mốc 0: chuẩn bị.**
- `git status` trước. Ngày 2026-11-08, branch `feat/tests-v2-07-rq-eval` có nhiều thay đổi chưa commit của owner (chuyển `AGENTS.md`/`.agent/rules`/`.agent/skills` sang `CLAUDE.md` + `.claude/`, CI, scripts): không sửa, không stash, không reset. Hỏi owner trước khi tạo branch; theo `CLAUDE.md` mục 9 thì branch từ `develop`, đặt tên `{type}/{scope}-{name}` (ticket ghi `feat/ai-qa-v2-qa-pipeline`; hỏi owner có đổi scope sang `ai` không).
- Cập nhật tài liệu trước code: TECH-V2-ai-service §7.1 (chuỗi bước + `Decision`, `QueryFrame`, lý do để cổng lỏng) và thêm 3 tiêu chí tương ứng vào V2-10 (ghi "Sửa 2026-11-08 (owner chốt)"). Dùng skill `spec-docs`: tiếng Việt, frontmatter theo `docs/README.md`, cập nhật `updated:`.

**Mốc 1: phần tất định, không cần LLM thật.**
`qa/pii.py`, `qa/guard.py` + `qa/guard_rules.yaml`, `qa/router.py` + `qa/templates.yaml`, `qa/lexicon.yaml`, `qa/followup_rules.yaml`, `qa/query_frame.py`, `qa/checks.py`, `qa/citations.py`, `retrieval/context.py` (hàm thuần, `eval/` phải import được), bộ khung `qa/pipeline.py` với `Decision`. Unit test theo bảng §4 của ticket: các ca trùng khi bỏ dấu ("ngu" trong "nguồn", "cc"/"đm"), câu chỉ chửi → `TEMPLATE`, chửi kèm câu hỏi → RAG trên câu đã bóc, PII (`500.000.000` không bị che), đầu vào rỗng/> 1000 ký tự, câu mở đầu cố định VI/EN, kiểm số/ngày, ghép context (nhóm ≤ `section_max_tokens`, ±1 + đoạn dẫn, gộp cửa sổ, trần token, `expand=false`).

**Mốc 2: provider LLM và stream.**
`providers/llm.py` kiểu OpenAI-compatible, chọn bằng `config/models.yaml`, không gán cứng model ID, gọi `/models` lúc khởi động và cảnh báo khi model bị gỡ; giới hạn RPM/TPM; fallback chỉ trước `delta` đầu tiên; `context_max_tokens` theo model. `qa/prompt.py` (`<source>` có `code`/`rev`/`effective` từ `rag.extracted_documents`, escape, canary, "Hôm nay là …", không có lịch sử hội thoại; message `user` có `Câu hỏi:` và `Câu gốc:` khi khác nhau; `prompt_version`). Stream giữ lại `len(canary) + 32` ký tự cuối. Test bằng provider giả ghi lại prompt: đếm số lần gọi LLM ≤ 2, prompt không chứa lịch sử, không chuyển model sau `delta` đầu tiên.
Model: owner chốt 2026-11-01 (PLAN-V2, ADR-006 §4.4) bỏ Gemini và Groq `gpt-oss-120b` khỏi sinh và giám khảo, tự host trên Modal; V2-10 §"Owner đơn giản hóa chọn model 2026-11-04" chọn Qwen3.5-9B FP8 trên L4. Chuỗi gemini/groq trong `models.yaml` đã lỗi thời, không dựa vào nó. Việc sửa `models.yaml` sang endpoint Modal (OpenAI-compatible, URL và key qua biến môi trường có mục trong `.env.example` với giá trị giả) thuộc V2-10. Hỏi owner: URL endpoint, tên biến môi trường, có giữ provider dự phòng nào cho `generate`/`rewrite` không. Chưa có endpoint thì toàn bộ test dùng provider giả. Thêm dependency mới (ví dụ SDK `openai`) phải nêu lý do và hỏi owner trước (`CLAUDE.md` mục 12); ưu tiên `httpx` nếu đã có trong `pyproject.toml`.

**Mốc 3: API, lưu trữ, hội thoại.**
`POST /ai/v1/conversations/{conversationId}/messages` (SSE theo TECH §7.2), ghi `messages` (`route`, `rewrite_status`, `checks`, `refusal_reason`, `context_sources`), `message_citations`, `guard_events`, `retrieval_results`; hội thoại chỉ người tạo xem; ẩn trích dẫn tới tài liệu mất quyền khi mở lại; hạn mức câu hỏi cấu hình được, **mặc định tắt**; câu `TEMPLATE` không tính hạn mức. Mọi SQL chạy trong `tenant_tx` và có `workspace_id = :wid`; mọi truy vấn chunk (kể cả chunk mở rộng của §6.4a) đi qua `allowed_cte()` + `access_params(principal)`, không viết bộ lọc thứ hai. `tests/unit/test_architecture.py` phải còn xanh. Integration test trên DB thật với LLM giả: một câu trả lời được, một câu không trả lời được.

**Mốc 4: harness và bộ câu guard.**
`eval/sopilot_eval/answers.py` đo citation precision, tỉ lệ từ chối đúng (tách `NO_EVIDENCE` và `GENERATOR_NOT_FOUND`), faithfulness trên tập con cố định (`temperature=0`), ablation `context.expand` bật/tắt. Bộ câu guard 80–100 câu theo ticket: bạn soạn bản nháp, **owner duyệt** trước khi dùng làm nghiệm thu; không trùng `eval/provider_check/prompt_guard_cases.jsonl`.

## 4. Ràng buộc

- Tuân theo 13 ràng buộc kỹ thuật trong `CLAUDE.md`; hook `.claude/hooks/guard.py` chặn một phần, phần còn lại do bạn giữ.
- Không mở, in, grep hay diff `.env`/`.env.*`. Không hardcode key hay model ID (chỉ khai báo trong `config/models.yaml`). Không thêm `print(` (ruff `T20`); `TODO`/`FIXME` phải kèm `V2-NN`. Log bằng `structlog`, không log token, key hay nội dung tài liệu; thông báo lỗi trả cho client là câu cố định kèm mã.
- Chỉ sửa trong repo, không đụng V1 (`services/ai-qa-service` chỉ để tham khảo `prompt_builder.py`; không port intent classification hay `layer1_toxic_filter.py`). Hỏi trước khi sửa `docker-compose*.yml` hoặc `.github/workflows/**`.
- Migration mới (nếu thật sự cần cột chưa có) là file Flyway mới trong `infrastructure/db/migrations/rag/`, theo skill `flyway-migration`; không sửa migration đã commit; hỏi owner trước.
- Không commit hay push trừ khi owner bảo. Commit dạng `<type>(ai): <summary> (V2-10)`, **không** ghi Claude/AI là tác giả hay đồng tác giả, không `--no-verify`.
- Khi tài liệu và code mâu thuẫn, hoặc một tiêu chí của ticket không làm được như viết, dừng và hỏi owner; không tự đổi quyết định đã chốt.

## 5. Kiểm tra trước khi báo xong mỗi mốc

```powershell
./scripts/run-tests.ps1 -Scope ai-service -Type unit
./scripts/validate-build.ps1 -Scope ai
./scripts/run-tests.ps1 -Scope ai-service -Type integration   # từ mốc 3, cần Docker
cd eval; uv run pytest -q; cd ..                              # khi đụng retrieval/ hoặc thêm retrieval/context.py
./scripts/pre-commit-check.ps1                                # trước khi đề xuất commit
```
Integration test tự dựng Postgres pgvector dùng một lần với migration `rag` thật; không cần chạy `docker-compose.v2.yml`. Đặt timeout cho build và test. Xem lại `git diff` để loại thay đổi ngoài phạm vi, rồi chạy agent `v2-reviewer` trước khi đề xuất commit.

## 6. Báo cáo cuối mỗi mốc

File đã đổi; lệnh đã chạy kèm kết quả thật (lỗi thì dán output); việc chưa kiểm (ví dụ chưa gọi provider thật); tài liệu đã cập nhật; câu hỏi cần owner quyết. Đánh dấu tiêu chí `[x]` trong ticket chỉ khi có bằng chứng; ticket chuyển `review`, không tự chuyển `done`.
