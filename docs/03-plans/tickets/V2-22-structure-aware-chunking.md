---
id: V2-22
title: "ai-service: nhận diện loại tài liệu, bảng quy trình và chunk theo cấu trúc"
type: feat
status: todo
created: 2026-10-19
updated: 2026-10-19
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20]
blocks: [V2-09]
branch: "feat/ai-qa-structure-chunking"
assignee: pair
---

# TICKET V2-22: Chunk theo cấu trúc

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 5, 6 và 7, PRD-V2 FR-08. Standardizer cũ chỉ nhận Chương/Điều/Khoản, làm mất tiêu đề, cộng dồn sai `section_path`, tách nhầm câu bị ngắt dòng, và chunker đếm token bằng `cl100k`.

## 2. Tiêu chí Hoàn thành
- [ ] Nhận diện họ tài liệu (quy trình ISO, Chương/Điều/Khoản, Markdown/wiki, văn xuôi không chuẩn) từ cấu trúc của V2-20; ưu tiên heading thật (style, `#`), sau đó mẫu đánh số (`1.`, `5.1`, `I.`, `Điều n`), cuối cùng mới tới heuristic (dòng in hoa, chữ đậm).
- [ ] Tiêu đề section giữ đầy đủ chữ (không chỉ số); `section_path` là chuỗi tổ tiên, không phải các section anh em.
- [ ] Bảng quy trình (Trách nhiệm / Bước / Mô tả / Biểu mẫu): mỗi hàng là một đơn vị nội dung kèm tiêu đề cột; bảng dài lặp tiêu đề cột khi bị cắt.
- [ ] Chunk mang đường dẫn tiêu đề (tên tài liệu › mục › bước) trong nội dung được embed và index BM25.
- [ ] Đếm token bằng tokenizer của model embedding; chunk không vượt giới hạn của model; gộp section quá nhỏ cùng cha; không cắt giữa ký tự.
- [ ] Văn xuôi không chuẩn: chia theo đoạn/câu, không cắt cứng theo số token.

## 3. Hướng dẫn
- Thay `services/ingestion-service/src/services/{standardizer,chunker}.py`; không port nguyên trạng.
- Kích thước chunk khớp cấu hình eval V2-07 để kết quả RQ áp dụng được.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Các ca trong AUDIT §2.3 (tiêu đề chỉ là số, path cộng dồn, "Điều 5" giữa câu, `1. MỤC ĐÍCH`, `5.1`); bảng quy trình; ký tự tiếng Việt ở mép chunk | `uv run pytest tests/unit` |
| Eval | Heading và bảng trên corpus V2-19 | theo V2-19 |
