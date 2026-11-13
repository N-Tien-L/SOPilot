---
id: V2-01
title: "Duyệt PRD-V2, ADR-004/005/006/007 và chốt câu hỏi mở"
type: docs
status: done
created: 2026-10-17
updated: 2026-10-20
author: "Owner"
scope: docs
priority: P0
size: S
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: []
blocks: [V2-03, V2-04, V2-08]
branch: "docs/docs-approve-v2"
assignee: owner
---

# TICKET V2-01: Duyệt PRD-V2, ADR-004/005/006

## 1. Bối cảnh & Mục tiêu
Theo `AGENTS.md`, không lập PLAN khi PRD chưa `approved`. Ticket này chuyển bốn tài liệu `draft` sang `approved` (hoặc sửa theo ý owner) và chốt các câu hỏi mở của PRD §8.

## 2. Tiêu chí Hoàn thành
- [x] Owner quyết định từng câu hỏi mở PRD §8, ghi kết quả vào PRD: Java 17 hay 21; provider LLM; object storage khi chạy local; có workspace demo công khai hay không.
- [x] Vì phạm vi hiện tại là local-only: ghi rõ B1/B2 (deploy) là ngoài phạm vi, B3 là tùy chọn.
- [x] PRD-V2, ADR-004, ADR-005, ADR-006, ADR-007 có `status: approved`; ADR-001, ADR-002, ADR-003 và PRD-M1 chuyển `superseded`.
- [x] PLAN-V2 chuyển `approved`.

## 3. Hướng dẫn
- **File:** `docs/product/prd-v2-sopilot-mvp.md`, `docs/02-architecture/adr/ADR-00{1,2,3,4,5,6,7}-*.md`, `docs/03-plans/PLAN-V2-sopilot-mvp.md`
- **Action:** MODIFY. Cập nhật frontmatter `status`/`updated`, mục §8 của PRD, và liên kết `superseded_by`.
- Đây là việc của owner; agent chỉ chuẩn bị bản so sánh lựa chọn.

## 4. Kiểm thử
Không có. Kiểm bằng cách đọc lại frontmatter các file trên.

## 5. Diễn biến (2026-10-19)
- Owner chốt câu hỏi mở 1–6 của PRD-V2 §8 theo đề xuất (Java 21; chỉ chạy local; MinIO ghim bản; LLM Gemini Flash-Lite + Groq `gpt-oss-*` có điều kiện V2-02; không có workspace demo công khai). Bổ sung FR-08 và giới hạn corpus theo AUDIT-ingestion-sop-data; thêm `V2-19` đến `V2-22`.
- Cùng ngày, owner mở lại phạm vi để giữ hồ sơ thành viên, phòng ban phẳng, category/metadata, gợi ý metadata và quyền tài liệu theo phòng ban (ADR-007, `V2-23` đến `V2-26`), và chốt PRD §8 mục 7–9 theo đề xuất. Toàn bộ bộ tài liệu quay về `draft` chờ duyệt lại.
- 2026-10-20: owner duyệt PRD-V2, ADR-004/005/006/007 và PLAN-V2 sau khi chạy V2-02 (Groq đạt; Prompt Guard bị loại, guard chuyển sang bốn lớp không gọi LLM; Gemini 3.1 Flash Lite còn phải thử lại vì 503). ADR-001/002/003 và PRD-M1 chuyển `superseded`.
