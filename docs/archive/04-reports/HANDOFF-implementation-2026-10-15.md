---
id: HANDOFF-IMPLEMENTATION-2026-10-15
title: "Bàn giao implementation — 2026-10-15"
type: handoff
status: final
created: 2026-10-15
updated: 2026-10-15
author: "Owner"
---

# Bàn giao implementation — 2026-10-15

> Cập nhật sau checkpoint: phần Google identity/roster admission trong NEXT-02 đã được triển khai trên nhánh fix riêng. Đọc [audit auth mới](AUDIT-google-admission-2026-10-15.md) và ADR-003 trước khi tiếp tục; các kết quả/checkpoint cũ bên dưới được giữ làm lịch sử.

## Trạng thái chốt

Checkpoint trên `feat/gateway-roster-routes`, xuất phát HEAD `386dda1`. Mục tiêu là lưu toàn bộ thay đổi đang có thành lịch sử Git và chuẩn bị đầu vào cho lần implement sau. **Sẵn sàng tiếp tục phát triển; chưa nghiệm thu M1 hoặc release.**

Đọc theo thứ tự: [PLAN-NEXT](../03-plans/PLAN-NEXT-implementation-readiness.md) → ticket được chọn → [PRD-M1](../01-requirements/PRD-M1-jit-onboarding.md)/[TECH-M1](../02-architecture/designs/TECH-M1-jit-onboarding.md) → handbook/context liên quan. Audit ngày 14/10 là snapshot lịch sử, không tự sửa kết quả cũ bằng các kiểm tra mới.

Tiến độ M1 đã hòa giải: M1-01/02 done, M1-03/04 review, M1-05 in-progress, M1-06 todo. Plan đếm `completed_tickets=2`, `implemented_tickets=4`, `review_tickets=2`; không xem code đã commit là ticket đã nghiệm thu. `docs/03-plans` là nguồn tiến độ hiện hành; tickets trong `docs/plans/tickets` được sync. Plan cũ chứa thiết kế lịch sử và có chỉ dẫn đến plan hiện hành.

## Những gì được lưu/chốt

- Toàn bộ UI/API/types/i18n/style đang có cho Google login, xử lý 403, roster và upload; bỏ một import unused trong modal mới.
- Cấu hình tên SOPilot, exchange/bucket, CI name, seed schema và Python lock đang có.
- Docker auth được truyền Google client ID, internal service token và URL `user-service`; frontend nhận public Google client ID ở build args/Dockerfile. Cần build lại khi đổi giá trị public.
- Bỏ default admin password trong Compose; bỏ default URL chứa password trong AI-QA settings, dùng biến môi trường bắt buộc như ingestion. `.env.example` chứa placeholder; không commit `.env` hoặc `.env.local`.
- Gateway không còn ghi body login vào debug log (F04 đã xử lý bằng source; gateway tests pass).
- Default bucket được chuyển thành additive migration `011`, giữ nguyên bootstrap `003` cũ và mọi tham chiếu document/object cũ. Migration chưa được thực thi.
- Pre-commit khởi tạo đúng biến scan debug/secret và quét added lines; chặn env thực. Convention check cho phép `.env.example`, nhận cả untracked files và bỏ qua deleted lines khi quét debug.
- Runner dùng Maven wrapper Windows phù hợp, không dùng integration profile không tồn tại; suite thiếu trả lỗi rõ. Pytest temp nằm trong workspace. Gateway validate lint không dùng `--fix`, tránh tự sửa code khi kiểm tra.
- Audit, handbook, templates và 6 ticket NEXT đã được đưa vào checkpoint. File context MinIO được track riêng để đi cùng migration; không mở rộng tracking toàn bộ `.agent` hoặc các dữ liệu local bị ignore.

## Verification trong ngày 15/10

| Gate | Kết quả |
|---|---|
| Frontend `node node_modules/next/dist/bin/next build` | PASS: compile/TypeScript/static generation 24 trang; dùng `.env.local` có sẵn, không đọc/commit nội dung file đó |
| Gateway `node node_modules/@nestjs/cli/bin/nest.js build` | PASS |
| Gateway `node node_modules/jest/bin/jest.js --runInBand` | PASS: 39 tests / 3 suites, 25,482s |
| Lint login, 2 roster components, Google/roster types | PASS không có error; warning import Badge đã được bỏ và kiểm tra lại trước commit |
| `docker compose --env-file .env.example config --quiet` | PASS exit 0; có warning không đọc được Docker user config; không chạy container |
| Parse 7 scripts PowerShell | PASS: 0 parse errors |
| Python `py_compile` 2 file settings thay đổi | PASS |
| Python pytest cả 2 service qua `.venv/Scripts/python.exe -m pytest` | Không chạy được: local venv thiếu module pytest; không tính là test pass/fail assertion |
| Java/full pre-commit/platform E2E | Chưa xác minh trong checkpoint; Maven wrapper lỗi ở audit trước, E2E M1-06 chưa có |
| Full frontend lint | Audit 14/10: 61 errors, 99 warnings; chưa chạy lại toàn bộ, chưa có baseline riêng để phân loại regression |

Hai build dùng entrypoint Node local vì pnpm bị sandbox EPERM ở audit trước. Build/test mock không xác nhận OAuth thật, upload CSV, broker delivery, ACL retrieval hoặc chất lượng RAG. Không tự cài dependencies, bật stack, reset DB, gọi external AI, push hay merge trong checkpoint.

## Bắt đầu lần sau

1. Chạy `git status --short` và kiểm tra nhánh; đọc ticket scope trước khi sửa. Dùng checkpoint này làm baseline, không trộn vào project cũ.
2. Có thể bắt đầu **NEXT-03 (CSV)** ngay theo PRD-M1; đồng thời **NEXT-06** khôi phục test environment/CI và phân loại baseline lint. Chỉ chạy test có state trên test stack cô lập.
3. **NEXT-01** chốt ma trận tính năng giữ/bỏ/nâng cấp và policy tài khoản kế thừa/admin. **NEXT-02** phụ thuộc quyết định đó; không tự cắt password flow hay chặn admin bootstrap.
4. **NEXT-04/05** thiết kế delivery audit và model/cache migration rồi tách ticket theo từng service. Không tự xóa cache, vector hay database để đổi tên.
5. Hoàn thiện và kiểm tra M1-05 bằng phiên admin/Google thật; sau đó chạy M1-06, lưu test/event/SQL evidence và mới xét nghiệm thu.

Các giới hạn cần nhớ: đổi PostgreSQL user/database trong Compose không đổi dữ liệu của volume cũ; đổi bucket default không di chuyển object cũ; public Google client ID phải cùng OAuth client với backend. `.agent/context/overview.md` vẫn có mô tả cũ mâu thuẫn schema; dùng AGENTS/DDL hiện tại và xác minh runtime, không làm theo lời khuyên đổi schema cũ. Ownership data plane và rebranding defaults ngoài Docker cần được xử lý ở backlog, không có chứng nhận tương thích toàn bộ môi trường.

Các ticket NEXT là đề xuất có acceptance và file scope, không phải PRD/ADR tự động approved. Mọi acceptance chưa có bằng chứng giữ unchecked.
