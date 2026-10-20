---
id: V2-03
title: "Viết TECH-V2-core-api và TECH-V2-ai-service"
type: docs
status: todo
created: 2026-10-17
updated: 2026-10-19
scope: docs
priority: P0
size: L
parent_plan: PLAN-V2-SOPILOT-MVP
depends_on: [V2-01]
blocks: [V2-09, V2-11, V2-20]
branch: "docs/docs-tech-v2"
assignee: pair
---

# TICKET V2-03: TECH-V2

## 1. Bối cảnh & Mục tiêu
Đặc tả DDL (kèm RLS), API, sequence và event cho hai service mới, đưa vào các phát hiện R1–R5, A1–A9 và AUDIT §4.2. Skill: `.agent/skills/design-architecture/SKILL.md`.

## 2. Tiêu chí Hoàn thành
- [ ] `TECH-V2-core-api.md`: DDL các bảng workspace, membership, invitation, document, outbox, audit, quota, feedback; API REST có versioning; luồng Google login và refresh.
- [ ] `TECH-V2-ai-service.md`: DDL chunk (có `workspace_id`, `embedding_provider/model/dim/revision`, 4 cột điểm); interface `EmbeddingProvider`, `RerankProvider`, `LLMProvider`; `models.yaml`; pipeline 2 lần gọi LLM; schema SSE và trích dẫn; contract outbox từ core-api.
- [ ] `TECH-V2-ai-service.md` có mục ingestion theo FR-08 mở rộng: cấu trúc tài liệu trung gian (đầu ra V2-20), bước tách khung và metadata (V2-21), nhận diện loại tài liệu và chunk (V2-22), vị trí package để V2-09 import.
- [ ] Theo ADR-007: DDL membership có hồ sơ, `departments`, `document_departments`, `documents.visibility`, `categories`, `tags`, nguồn trường metadata; claim `wdept`; API phòng ban/hồ sơ/metadata; contract cập nhật `rag.document_access` từ core-api; job gợi ý metadata (V2-25).
- [ ] Chính sách RLS: `SET LOCAL app.workspace_id` mỗi transaction, role DB không phải owner bảng.
- [ ] Rerank chạy trước ngưỡng; mỗi chế độ có ngưỡng riêng cấu hình được.
- [ ] Không port nguyên `EMBEDDING_MODEL_NAME = "BGE_M3"` hay cắt 512 token bằng `tiktoken`.
- [ ] Frontmatter đúng `docs/README.md`, trạng thái `draft` chờ owner duyệt.

## 3. Hướng dẫn
- **File:** `docs/02-architecture/designs/TECH-V2-core-api.md`, `TECH-V2-ai-service.md` (CREATE), theo `templates/tech-design-template.md`.

## 4. Kiểm thử
Không có. Review chéo với PRD §3 để mỗi FR có chỗ trong thiết kế.
