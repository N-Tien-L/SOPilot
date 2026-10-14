---
ticket_id: NEXT-06
title: "Khôi phục baseline test/lint và đưa gates vào CI"
type: chore
scope: platform
priority: P1
size: L
status: todo
parent_plan: PLAN-NEXT
depends_on: []
---

# NEXT-06: Khôi phục baseline test/lint và đưa gates vào CI

## Context
Audit 2026-10-14: F08. Không đổi các quyết định sản phẩm chưa được chốt. Nguồn hiện hành là bản trong docs/03-plans; bản docs/plans được sync.

## Acceptance Criteria
- [ ] Có kết quả service tests với số pass/fail/skipped và lệnh tái chạy.
- [ ] CI chạy gateway tests; frontend test harness có test nghiệp vụ meaningful.
- [ ] Có baseline lint được phân loại và ticket khắc phục, không suppress rule để lấy PASS.
- [ ] Pre-commit kiểm tra đúng added lines và secret/env trước staged commit.

## Implementation Guide
Cài dependency dev Python theo lock/pyproject và xác minh Java wrapper trên môi trường phù hợp. Lập baseline lint hiện tại; tách ticket sửa từng nhóm thay vì sửa 61 lỗi trong một diff. Thêm gateway Jest vào CI và chọn test harness frontend cho M1-05/06. Giữ missing suite là lỗi rõ ràng, không thay test bằng build.

## Files / Scope
- `scripts/run-tests.ps1`
- `scripts/pre-commit-check.ps1`
- `.github/workflows/ci.yml`
- `frontend/web/package.json`
- `tests/README.md`

## Verification
`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/pre-commit-check.ps1`; mỗi suite được báo riêng, mock suite không thay platform E2E.

Dữ liệu runtime phải dùng môi trường test cô lập; không tự reset DB hoặc gửi tài liệu local ra AI bên ngoài.
