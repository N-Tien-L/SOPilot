---
id: V2-22
title: "ai-service: nhận diện loại tài liệu, bảng quy trình và chunk theo cấu trúc"
type: feat
status: todo
created: 2026-10-19
updated: 2026-10-24
scope: ai-qa
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20]
blocks: [V2-07, V2-09, V2-28]
branch: "feat/ai-qa-structure-chunking"
assignee: pair
---

# TICKET V2-22: Chunk theo cấu trúc

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 5, 6 và 7, PRD-V2 FR-08. Standardizer cũ chỉ nhận Chương/Điều/Khoản, làm mất tiêu đề, cộng dồn sai `section_path`, tách nhầm câu bị ngắt dòng, và chunker đếm token bằng `cl100k`.

## 2. Tiêu chí Hoàn thành
- [ ] Nhận diện họ tài liệu (quy trình ISO, Chương/Điều/Khoản, Markdown/wiki, văn xuôi không chuẩn) từ cấu trúc của V2-20; ưu tiên heading Markdown (`#`), sau đó mẫu đánh số (`1.`, `5.1`, `I.`, `Điều n`), cuối cùng mới tới heuristic (dòng in hoa, chữ đậm).
- [ ] Tiêu đề section giữ đầy đủ chữ (không chỉ số); `section_path` là chuỗi tổ tiên, không phải các section anh em.
- [ ] Bảng quy trình (Trách nhiệm / Bước / Mô tả / Biểu mẫu): mỗi hàng là một đơn vị nội dung kèm tiêu đề cột; bảng dài lặp tiêu đề cột khi bị cắt. Sửa 2026-10-21 (audit theo loại query, owner chốt P0-3, TECH-V2-ai-service §5.2, §5.4): ô gộp dọc (`DocElement.cell_spans`) được **lặp xuống từng hàng** mà nó phủ khi dựng `content` của chunk `PROCEDURE_STEP`, để bước 3–4 dưới một ô "Trách nhiệm" gộp vẫn có người phụ trách; offset và `row_spans` không đổi. Không có `cell_spans` thì không đoán. Test: fixture bảng có ô gộp (V2-19) cho `content` đúng ở từng hàng.
- [ ] Chunk mang đường dẫn tiêu đề (tên tài liệu › mục › bước) trong nội dung được embed và index BM25. Sửa 2026-10-21 (TECH-V2-ai-service §5.4): chunker nhận `title` và `doc_code` (tùy chọn) làm tham số; `index_text` = `"{title} [{doc_code}] › …"` khi có mã, `"{title} › …"` khi không; không đưa lần ban hành hay ngày hiệu lực vào `index_text`. Test cả hai dạng.
- [ ] Đếm token bằng tokenizer của model embedding qua `docproc.tokens.Tokenizer` truyền vào chunker; triển khai `HFTokenizer` (nạp `AutoTokenizer` theo `model`/`revision` của embedding đang hoạt động, không nạp model embedding) để `V2-09` và `eval/` dùng lại (TECH-V2-ai-service §1.1). Chunker không import `providers`. Chunk không vượt giới hạn của model; gộp section quá nhỏ cùng cha; không cắt giữa ký tự.
- [ ] Văn xuôi không chuẩn: chia theo đoạn/câu, không cắt cứng theo số token.
- [ ] Chunk làm việc trên `StructuredDocument` đã làm sạch và mang `char_start/char_end` trên Markdown chuẩn của V2-20 (owner chốt 2026-10-21): chunk thường là chuỗi con đúng của `markdown` tại offset đó; chunk `PROCEDURE_STEP` lấy offset từ `row_spans[i]` và trang từ `row_pages[i]` của hàng nguồn; chunk bảng cắt theo hàng lấy offset từ hàng đầu tới hàng cuối của phần đó; `page_start ≤ page_end` và khớp trang của các phần tử nguồn; chunk phủ bảng nhiều trang có `page_end > page_start`. Kiểm bằng property test trên fixture và corpus V2-19.

## 3. Hướng dẫn
- Thay `services/ingestion-service/src/services/{standardizer,chunker}.py`; không port nguyên trạng.
- Kích thước chunk khớp cấu hình eval V2-07 để kết quả RQ áp dụng được.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Các ca trong AUDIT §2.3 (tiêu đề chỉ là số, path cộng dồn, "Điều 5" giữa câu, `1. MỤC ĐÍCH`, `5.1`); bảng quy trình; ký tự tiếng Việt ở mép chunk | `uv run pytest tests/unit` |
| Eval | Heading và bảng trên corpus V2-19 | theo V2-19 |
