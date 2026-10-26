---
id: V2-21
title: "ai-service: tách phần khung, trích metadata SOP và cảnh báo trích xuất"
type: feat
status: review
created: 2026-10-19
updated: 2026-10-26
scope: ai-qa
priority: P0
size: M
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-20]
blocks: [V2-09, V2-16, V2-25, V2-28]
branch: "feat/ai-qa-boilerplate-metadata"
assignee: pair
---

# TICKET V2-21: Tách khung, giữ ruột

## 1. Bối cảnh & Mục tiêu
[AUDIT-ingestion-sop-data](../../04-reports/AUDIT-ingestion-sop-data-2026-10-19.md) bước 4 và 8, PRD-V2 FR-08. Phần khung (header/footer lặp, quốc hiệu/tiêu ngữ, chữ ký, nơi nhận, bảng phê duyệt, bảng sửa đổi) đang bị embed như nội dung. Bỏ chúng khỏi index nhưng giữ thông tin hữu ích làm metadata.

## 2. Tiêu chí Hoàn thành
- [x] Phát hiện header/footer lặp qua các trang PDF (DOCX hoãn sau MVP theo FR-06); loại khỏi nội dung. Sửa 2026-10-21 (audit theo loại query, owner chốt P0-4, TECH-V2-ai-service §5.3): luật "≥ 60% số trang" chỉ áp dụng khi PDF có ít nhất `SOPILOT_HEADER_FOOTER_MIN_PAGES` trang (mặc định 3, chốt trên corpus V2-19) và phần tử `heading` đầu tiên không bao giờ bị đánh `header`; thêm fixture PDF 1 trang và 2 trang, chỉ số "nội dung bị xóa nhầm" phải bằng 0 trên chúng. *Xong 2026-10-26: `docproc/clean/boilerplate.py`, test `test_clean.py` (kể cả PDF 1–2 trang không mất nội dung, heading đầu không bị đánh `header`) và PDF thật `framed_procedure` trong `test_pdf.py`.*
- [x] Nhận diện khối quốc hiệu/tiêu ngữ, số/ký hiệu, nơi nhận, khối chữ ký, bảng Soạn thảo/Soát xét/Phê duyệt, bảng theo dõi sửa đổi; loại khỏi nội dung được chunk. *Xong 2026-10-26 (luật VI/EN, test synthetic).*
- [ ] Trích metadata khi có: mã số, lần ban hành, ngày ban hành/hiệu lực, người phê duyệt; lưu theo version tài liệu. *Xong một phần 2026-10-26: `clean/metadata.py` trả `docCode`, `revisionLabel`, `issueDate`, `effectiveDate`, `approvedBy`; chưa lưu theo version vì bảng `rag` thuộc V2-09 nên để mở.*
- [ ] Khối đã loại lưu trong `extracted_documents.boilerplate` dạng `{kind, page, text}`; không xuất hiện trong Markdown chuẩn, chunk hay index (test trên fixture có header/footer lặp và bảng phê duyệt); màn xem FR-31 liệt kê được chúng. *Xong một phần 2026-10-26: `CleanResult.boilerplate` có `{kind, page, text}` và test khối khung không vào Markdown; cột DB và màn FR-31 thuộc V2-09/V2-16 nên để mở.*
- [x] Cảnh báo theo TECH-V2-ai-service §5.3a (`PAGES_WITHOUT_TEXT`, `UNMAPPED_GLYPHS`, `NO_HEADINGS_DETECTED`, `BOILERPLATE_REMOVED`, `CONVERTER_WARNING` nếu thư viện có): mỗi mã có fixture sinh ra nó và fixture sạch không sinh ra nó; không có điểm tin cậy tổng hợp; cảnh báo không làm `FAILED`. *Xong 2026-10-26: `clean/warnings.py`; mỗi mã có fixture sinh ra và fixture sạch không sinh mã nào.*
- [ ] Không xóa nội dung thật: trên corpus V2-19, tỷ lệ khung lọt vào nội dung và tỷ lệ nội dung bị xóa nhầm đều được báo cáo; owner chốt ngưỡng. *Chưa làm: chờ corpus V2-19 có nhãn owner duyệt; chưa đo tỷ lệ khung lọt và nội dung bị xóa nhầm trên dữ liệu thật, ngưỡng do owner chốt.*

## 3. Hướng dẫn
- Bước xử lý trên cấu trúc của V2-20, trước bước chunk của V2-22.
- Schema metadata theo TECH-V2; nếu thêm cột thì migration trong `infrastructure/db/migrations/` và cập nhật `.agent/context/database/`.

## 4. Kiểm thử
| Loại | Nội dung | Lệnh |
|---|---|---|
| Unit | Header/footer lặp; khối quốc hiệu; bảng phê duyệt; trích mã số và lần ban hành | `uv run pytest tests/unit` |
| Eval | Chấm trên corpus V2-19 | theo V2-19 |

### Ghi chú triển khai 2026-10-26
Code: `services/ai-service/src/sopilot_ai/docproc/clean/` (`clean_document` đánh `role`, không xóa phần tử; `render` bỏ phần tử không phải nội dung). Cấu hình qua `CleanConfig` (`SOPILOT_HEADER_FOOTER_MIN_PAGES`=3, `SOPILOT_PAGE_MIN_CHARS`=20 là giá trị khởi đầu, chưa hiệu chỉnh trên corpus thật). Luật khung viết cho văn bản VI/EN và chỉ kiểm bằng fixture tự tạo; chưa chạy trên tài liệu thật. Giữ `review` vì còn ba tiêu chí chưa có bằng chứng ở trên.
