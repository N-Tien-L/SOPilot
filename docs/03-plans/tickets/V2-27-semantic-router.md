---
id: V2-27
title: "ai-service: semantic router (luật + embedding) và đo so với chỉ luật"
type: feat
status: todo
created: 2026-10-20
updated: 2026-11-11
author: "Owner"
scope: ai-qa
priority: P1
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-05, V2-10]
blocks: [V2-18, V2-37]
branch: "feat/ai-qa-semantic-router"
assignee: pair
---

# TICKET V2-27: Semantic router và đo định tuyến

## 1. Bối cảnh & Mục tiêu
`V2-10` định tuyến bằng luật (từ điển thô tục VI/EN, "bóc rồi xét"). Luật bỏ sót những cách diễn đạt không lường trước ("ê mày làm được gì vậy", câu chửi mỉa mai). Owner chốt 2026-10-20: dùng **luật + semantic router**, bỏ phương án LLM classifier cho vùng xám (thêm độ trễ, tốn quota, không ổn định, bị prompt injection). PRD-V2 FR-13 và ADR-006 §4.4 đã sửa theo quyết định này.

Semantic router không gọi LLM: so embedding câu hỏi với câu mẫu của từng intent, chỉ rẽ nhánh khi chắc chắn, còn lại đi RAG như cũ. Ticket gồm phần runtime và phần đo (a: chỉ luật, b: luật + router) để chỉnh ngưỡng và có số liệu cho báo cáo.

## 2. Tiêu chí Hoàn thành
- [ ] Router chạy sau luật `V2-10`, chỉ với câu luật chưa quyết. Intent được rẽ nhánh: `greeting`, `thanks`, `about_bot`, `abuse_only` → câu mẫu, `outcome = TEMPLATE`, không gọi LLM, không tính hạn mức. Nhóm có hại thật vẫn chỉ do luật chặn; router không chặn câu nào.
- [ ] Sửa 2026-10-21 (audit đầu-cuối theo loại query, owner chốt D1; TECH-V2-ai-service §7.1): router mở rộng, **không dùng LLM classifier**. (a) `off_topic` **không** rẽ trước truy xuất vì router không biết kho chứa gì: chỉ khi cổng ngưỡng đã từ chối **và** điểm `off_topic` vượt ngưỡng của intent (và `margin` so với `sop_question`) thì gán `refusal_reason = OUT_OF_SCOPE`: cùng câu từ chối, không kèm tài liệu gần nhất, không vào danh sách khoảng trống; router không bao giờ đổi quyết định "cho qua" của cổng. (b) `action_request`, `personal_data`, `legal_medical` (luật cộng router): vẫn chạy RAG, chỉ phát thêm câu miễn trừ cố định theo ngôn ngữ (`qa/templates.yaml`) trước `citations`, ghi `messages.checks.disclaimers`. (c) `about_source` (chỉ khi có lịch sử): câu mẫu liệt kê lại trích dẫn của lượt trước từ `message_citations`, không gọi LLM. (d) `feedback_in_chat`: chỉ rẽ khi phần còn lại sau "bóc" rỗng; câu mẫu hướng dẫn bấm 👎. Quyết định của router ghi vào `messages.route` (`layer`, `intent`, `score`, `margin`).
- [ ] Điều kiện rẽ nhánh: điểm cosine cao nhất ≥ ngưỡng riêng của intent **và** cao hơn câu mẫu `sop_question` gần nhất ít nhất `margin`. Không thỏa → đi RAG. Ngưỡng và `margin` cấu hình trong file, không trong code.
- [ ] Embed câu hỏi gốc (chưa viết lại). Hội thoại chưa có lịch sử thì dùng lại vector đó cho dense retrieval; có lịch sử thì retrieval embed câu đã viết lại như cũ (thêm một lần embed local, không tốn quota).
- [ ] Câu mẫu nạp lúc khởi động, embed qua `rag.embedding_cache`; đổi model embedding đang hoạt động thì câu mẫu được embed lại, không so vector của hai model.
- [ ] Bật/tắt bằng `SOPILOT_SEMANTIC_ROUTER_ENABLED`; tắt thì hành vi đúng như `V2-10`. Bật mặc định sau khi ngưỡng được chỉnh trên `dev`.
- [ ] Bộ dữ liệu định tuyến có nhãn 300–500 câu VI/EN, owner duyệt, tách `dev`/`test`. Nhãn: `greeting`, `thanks`, `about_bot`, `abuse_only`, `abuse_with_question`, `harmful`, `followup` (kèm lượt trước), `sop_question`, `off_topic`; sửa 2026-10-21 thêm `action_request`, `personal_data`, `legal_medical`, `about_source` (kèm lượt trước), `feedback_in_chat`. Không trùng bộ câu guard của `V2-10` hay câu mẫu của router. Gồm teencode, không dấu, mỉa mai và các ca dễ chặn nhầm khi bỏ dấu.
- [ ] Harness so (a) chỉ luật với (b) luật + router trên `test`, theo từng nhãn: precision/recall; tỉ lệ câu `sop_question` bị rẽ nhầm sang câu mẫu; tỉ lệ `followup` bị đưa vào retrieval rồi từ chối; độ trễ thêm của router p50/p95; sửa 2026-10-21 thêm **tỉ lệ câu ngoài phạm vi (`off_topic`) lọt vào danh sách khoảng trống** (mục tiêu: các câu `off_topic` bị cổng từ chối nhận `OUT_OF_SCOPE`, không vào danh sách) và tỉ lệ câu `sop_question` bị gán nhầm `OUT_OF_SCOPE`. Lỗi được xếp **sai đắt** (rẽ nhầm câu nghiệp vụ, `followup` bị từ chối) hoặc **sai rẻ** (câu thô tục lọt vào RAG rồi bị từ chối, câu chào nhận câu "không tìm thấy").
- [ ] Nghiệm thu: (b) rẽ nhầm câu `sop_question` ≤ 2% trên `test` và không tăng sai đắt so với (a). Không đạt thì để `SOPILOT_SEMANTIC_ROUTER_ENABLED=false` mặc định và ghi lý do.
- [ ] Báo cáo `docs/04-reports/AUDIT-routing-guard-eval-<ngày>.md`: model embedding và revision, ngưỡng đã chọn, số liệu (a) và (b), quyết định bật/tắt mặc định.
- [ ] Cập nhật TECH-V2-ai-service §7.1 bước 3 (vị trí router, cấu hình, dùng lại vector).
- [ ] (Chuyển từ V2-10, owner chốt 2026-11-09; [V2-10](V2-10-ai-service-qa-pipeline.md) mốc 5 C) Xét hai điểm thấy khi chạy nhóm `probe` với model thật: 4/8 câu tấn công diễn đạt lại vượt cổng ngưỡng lỏng (0,456–0,504 so với 0,45), và câu trả lời mã hóa (base64) không khớp câu mở đầu cố định nên ra `ANSWERED` không có trích dẫn. Chạy lại 8 câu `probe` qua router (b) và ghi kết quả.

## 3. Hướng dẫn
- **File runtime:** `services/ai-service/src/qa/router.py` (thêm tầng embedding sau tầng luật), `qa/router_exemplars.yaml` (câu mẫu theo intent, gồm cả `sop_question` làm lớp đối chứng), `qa/router_thresholds.yaml`.
- **File eval:** `eval/sopilot_eval/routing.py`, `eval/configs/routing-{rules,rules-router}.yaml`, bộ dữ liệu trong `eval/datasets/routing/`. Harness gọi trực tiếp `qa/router.py`, không chép luật hay câu mẫu sang harness.
- Câu mẫu có thể do LLM sinh, nhưng owner duyệt trước khi dùng. Câu `sop_question` trong câu mẫu và bộ dữ liệu lấy từ bộ câu hỏi `V2-06` nếu đã có; chưa có thì tự viết và owner duyệt.
- `followup` chỉ được đo, không rẽ nhánh: bước viết lại câu hỏi đã xử lý câu hỏi tiếp. Nếu tỉ lệ `followup` bị từ chối cao, ghi vào báo cáo để mở ticket riêng. Sửa 2026-10-21 (audit theo loại query): chỉ số "`followup` bị đưa vào truy xuất rồi bị từ chối" **không đo được chỉ bằng `qa/router.py`** vì cần viết lại bằng LLM cộng truy xuất trên corpus gắn với lượt trước. Mỗi câu `followup` trong bộ dữ liệu có `previous_turn` và `corpus`/`evidence` trỏ tới corpus V2-06; phần đo này chạy qua `qa/pipeline.py` (LLM viết lại thật hoặc cố định, truy xuất trên corpus đó) và ghi riêng ba kết quả: truy xuất đúng, bị từ chối, và trả câu mẫu hỏi lại do luật nối tiếp (TECH-V2-ai-service §7.1 bước 4). Các chỉ số còn lại vẫn chạy trực tiếp trên `qa/router.py`.
- Câu `abuse_only` do router nhận diện ghi `guard_events(INPUT_FLAG)` với `rule_id = router.abuse`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | điều kiện ngưỡng + `margin`, tắt router thì giống `V2-10`, dùng lại vector khi chưa có lịch sử, câu mẫu embed lại khi đổi model | `uv run pytest tests/unit` trong `services/ai-service/` |
| Unit | metric theo nhãn, xếp sai đắt/sai rẻ | `uv run pytest` trong `eval/` |
| Thủ công | chạy (a) và (b) trên `test`, đính kèm `report.md` vào báo cáo | `python -m sopilot_eval.routing --config eval/configs/routing-rules-router.yaml` |
