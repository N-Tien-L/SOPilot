---
id: NEXT-05
title: "Thiết kế model identity và kế hoạch cache/vector migration"
type: docs
status: todo
created: 2026-10-15
updated: 2026-10-15
scope: ingestion
priority: P1
size: M
parent_plan: PLAN-NEXT
depends_on: []
---

# NEXT-05: Thiết kế model identity và kế hoạch cache/vector migration

## Context
Audit 2026-10-14: F06. Không đổi các quyết định sản phẩm chưa được chốt. Nguồn hiện hành là bản trong docs/03-plans; bản docs/plans được sync.

## Acceptance Criteria
- [ ] Cache key phân biệt provider/model/version/task/dimension có ý nghĩa.
- [ ] Document/query vectors cùng không gian được mô tả và kiểm tra bằng fixture.
- [ ] Kế hoạch chuyển dữ liệu cũ không xóa hoặc đổi provenance giả; tạo ticket triển khai theo scope.

## Implementation Guide
Kiểm tra model/task/dimension đang dùng và cách tạo cache key. Đề xuất model identity có version và migration enum/cache additive; tách triển khai infra/ingestion/AI-QA. Kiểm kê dữ liệu và kế hoạch reindex cô lập có rollback; không tự chạy clear_db/reingest hay gửi tài liệu ra dịch vụ AI.

## Files / Scope
- `services/ingestion-service/src/services/embedding_service.py`
- `services/ingestion-service/src/services/pipeline.py`
- `services/ai-qa-service/src/services/retrieval/hybrid_search.py`
- `infrastructure/init-db/003_knowledge.sql (chỉ đọc; dùng migration mới)`
- `docs/02-architecture/designs/TECH-embedding-migration.md (tạo)`

## Verification
Đối chiếu schema/repo/payload bằng source; integration với DB test và provider chỉ sau khi được phép gửi dữ liệu.

Dữ liệu runtime phải dùng môi trường test cô lập; không tự reset DB hoặc gửi tài liệu local ra AI bên ngoài.
