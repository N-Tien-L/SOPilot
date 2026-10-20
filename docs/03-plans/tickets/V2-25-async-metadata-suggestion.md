---
id: V2-25
title: "ai-service: gợi ý metadata chạy nền và đo độ trễ"
type: feat
status: todo
created: 2026-10-19
updated: 2026-10-21
scope: ai-qa
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-09, V2-21, V2-24]
blocks: [V2-15]
branch: "feat/ai-qa-async-metadata-suggestion"
assignee: pair
---

# TICKET V2-25: Gợi ý metadata chạy nền

## 1. Bối cảnh & Mục tiêu
PRD-V2 FR-28 và NFR hiệu năng. Code cũ gọi gợi ý **đồng bộ trong request upload** (`knowledge-service` `DocumentController` → ingestion `/metadata/suggest`, timeout 30 s), tải và parse lại file bằng `preview_extractor.py`, gọi Groq `llama-3.3-70b-versatile` (đã bị tắt theo CLAUDE.md) với `timeout=10`, `max_retries=2`.

## 2. Tiêu chí Hoàn thành
- [ ] Job gợi ý chạy sau trích xuất, không nằm trên đường tới `READY`; upload trả về ngay.
- [ ] Dùng lại `extracted_documents` (cấu trúc và Markdown chuẩn sau làm sạch, V2-20/V2-21); không tải hay parse lại file (test: job gợi ý chạy được khi object S3 đã bị xóa).
- [ ] Luật trước: tiêu đề (heading đầu hoặc tên file), ngôn ngữ, mã số/lần ban hành/ngày hiệu lực (V2-21).
- [ ] Một lần gọi LLM structured output cho mô tả, category (chỉ từ danh sách category hiện có của workspace, hoặc rỗng kèm tên đề xuất), tags (ưu tiên tags đã có). Đầu vào: tiêu đề, dàn ý heading, tối đa vài đoạn đại diện với trần token cấu hình được.
- [ ] Timeout cấu hình được, tối đa một lần thử lại; provider lỗi thì lưu kết quả luật và đánh dấu `fallback`.
- [ ] Cache theo `(workspace_id, sha256 nội dung, prompt_version, model, hash danh sách category)`; không dùng chung giữa workspace.
- [ ] Gợi ý lưu riêng; chỉ áp dụng vào trường có nguồn khác `USER`; không bao giờ đổi phạm vi hiển thị hay phòng ban.
- [ ] Ghi số đo theo job: `t_upload_ack`, `t_ready`, `t_suggest`, độ trễ LLM, token vào/ra, `fallback`; báo cáo p50/p95 trên corpus V2-19 trước khi đặt mục tiêu.

## 3. Hướng dẫn
- Phương án nâng cấp (chỉ khi số đo cho thấy cần): phân loại category bằng embedding gần nhất thay cho LLM, hoặc model nhỏ hơn. Ghi lựa chọn và số đo vào báo cáo.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Luật trích tiêu đề/ngôn ngữ/mã số; ràng buộc category trong danh sách; không ghi đè trường `USER`; fallback khi timeout | `uv run pytest tests/unit` |
| Integration | Upload → `READY` không chờ LLM (LLM mock chậm); cache không trúng chéo workspace | `uv run pytest tests/integration` |
