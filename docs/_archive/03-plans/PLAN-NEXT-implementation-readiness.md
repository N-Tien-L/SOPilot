---
id: PLAN-NEXT
title: "Backlog tiếp tục implementation"
status: superseded
created: 2026-10-15
updated: 2026-10-20
total_tickets: 6
completed_tickets: 0
implemented_tickets: 1
review_tickets: 1
---

> **Đóng 2026-10-20 (V2-04):** `superseded` bởi [PLAN-V2](PLAN-V2-sopilot-mvp.md). NEXT-01, 03, 04, 05, 06 `superseded` (ghi chú ánh xạ trong từng ticket); NEXT-02 giữ `review` làm lịch sử, port sang V2-11.

# Backlog tiếp tục implementation

Đây là backlog đề xuất từ audit, không tự thay PRD đã duyệt hoặc chứng nhận release. Nguồn: [audit](../04-reports/AUDIT-project-progress-2026-10-14.md), [bàn giao](../04-reports/HANDOFF-implementation-2026-10-15.md). Ticket triển khai phải đọc handbook/context và giữ scope.

| Ticket | Nội dung | Scope | Phụ thuộc |
|---|---|---|---|
| [NEXT-01](tickets/NEXT-01-product-scope-and-legacy-policy.md) | Chốt phạm vi sản phẩm và chính sách tài khoản kế thừa | docs | Không |
| [NEXT-02](tickets/NEXT-02-google-roster-admission.md) | Áp dụng chính sách roster cho đăng nhập Google của tài khoản cũ | auth | NEXT-01 |
| [NEXT-03](tickets/NEXT-03-roster-csv-import.md) | Hoàn thiện import CSV theo PRD-M1 | user | Không |
| [NEXT-04](tickets/NEXT-04-jit-audit-delivery-design.md) | Chốt contract và cơ chế delivery audit JIT | user | Không |
| [NEXT-05](tickets/NEXT-05-embedding-provenance-migration.md) | Thiết kế model identity và kế hoạch cache/vector migration | ingestion | Không |
| [NEXT-06](tickets/NEXT-06-verification-baseline-and-ci.md) | Khôi phục baseline test/lint và đưa gates vào CI | platform | Không |

NEXT-03 và NEXT-06 có thể bắt đầu với PRD/source hiện tại. NEXT-01 cần quyết định sản phẩm; NEXT-02 chỉ triển khai sau quyết định đó. NEXT-04/05 tạo thiết kế và ticket thực thi, không tự coi giải pháp đề xuất đã approved.

Sau các sửa lỗi/thiết kế được duyệt: hoàn thiện M1-05 rồi thực hiện M1-06. Cần test import → Google verify → atomic claim → chatbot, outsider 403, audit SQL/event, concurrent claim, ACL retrieval và upload/ingestion/citation/delete. Không mark done bằng build hoặc số commit.
