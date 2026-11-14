---
id: AUDIT-GOOGLE-ADMISSION-2026-10-15
title: "Google identity và roster admission"
type: audit
status: final
created: 2026-10-15
updated: 2026-10-15
author: "Owner"
scope: [auth-service, user-service, api-gateway]
verdict: PASSED_WITH_WARNINGS
---

# Google identity và roster admission

Nhánh `fix/auth-google-roster-admission`, xuất phát checkpoint `b5ff67b`. Phạm vi được người dùng yêu cầu: liên kết `(issuer, sub)`, kiểm tra roster cho tài khoản cũ và mới, bổ sung kiểm thử đăng nhập/vòng đời phiên. Không hoàn tất thay cho toàn bộ M1-06.

## Thay đổi

- Migration additive `012_google_identities.sql`; auth-service sở hữu bảng identity và hai ràng buộc uniqueness. Không tự backfill/link dữ liệu cũ bằng email.
- Google issuer alias được chuẩn hóa; token phải có subject hợp lệ. Email chỉ phục vụ enrollment ban đầu. Với email không do Google kiểm soát, tự enrollment bị từ chối; identity đã liên kết vẫn theo subject khi email thay đổi.
- `POST /internal/v1/roster/google-admission` kiểm tra roster mỗi Google login. Admission của roster CLAIMED có tính idempotent, không tạo user/event trùng khi retry. Tài khoản cũ phải có roster và khớp role/phòng ban; mismatch 409 yêu cầu HR xử lý.
- Admin không có ngoại lệ Google; bootstrap/password vẫn dùng được. Gateway bỏ đăng ký legacy Google code-exchange controller để auth-service là nơi duy nhất phát credential cho luồng này.
- Sửa lỗi startup được test HTTP tái hiện: GoogleTokenVerifierService có hai constructor nhưng thiếu annotation chọn constructor injection. Bổ sung `@Autowired` cho constructor production.
- Sửa lỗi refresh replay được tái hiện trên PostgreSQL: API trả 401 “all sessions revoked” nhưng revocation rollback, còn 5 refresh sessions active. `RefreshTokenRejectedException` giữ commit cho các nhánh thu hồi do expired/replay tại cả hai transaction boundary; lỗi khác vẫn rollback bình thường.

## Verification

Kết quả cuối được cập nhật sau khi script kiểm thử kết thúc. Các lượt lỗi trước không được tính là PASS: lỗi constructor và lỗi rollback đã được tái hiện, sửa và giữ regression check.

Lệnh tái chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test-google-auth.ps1
```

Runner dùng Maven offline và plugin build-classpath 3.6.1 có sẵn, rồi chạy `tests/integration/google-auth-flow.mjs`. PostgreSQL mới có tên/label UUID riêng, bind loopback, không mount volume ứng dụng; chỉ container có đúng label của lượt test mới được dọn. Hai backend dùng port/config riêng và token RSA/JWKS local. Không dùng Google credentials thật, không gửi tài liệu lên dịch vụ ngoài.

Packaging auth-service offline ban đầu thiếu dependency của spring-boot repackage plugin. Test runner dùng compiled classes/runtime classpath thay vì bỏ test hoặc đổi phiên bản framework. Vì vậy kết quả HTTP không chứng nhận Docker image đã build hoặc triển khai thành công.

## Giới hạn

- Chưa tự động hóa màn hình Google hosted, frontend roster import, chatbot navigation hoặc broker/audit delivery. M1-05/06 giữ trạng thái chưa nghiệm thu toàn bộ.
- Roster removal chặn Google login mới; phiên đã phát vẫn theo account/session policy. Khi cần thu hồi phiên của nhân viên, sử dụng cơ chế vô hiệu hóa tài khoản/thu hồi session; không coi thao tác xóa roster là instant revocation mọi access token.
- Không sửa CSV, embedding/cache, toàn bộ lint hay cắt các module legacy ngoài đường auth liên quan.
- Không áp dụng migration vào DB SOPilot hiện hữu; không commit/push/deploy trong lần triển khai này.

## Chạy bản mới trên môi trường dev

Sau khi xác nhận đúng DB dev `sopilot`, áp dụng migration trước khi rebuild backend:

```powershell
docker compose exec -T postgres psql -U sopilot -d sopilot -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/012_google_identities.sql
docker compose up -d --build auth-service user-service api-gateway
```

Không reset volume. Test Google thật bằng email trong roster; tài khoản legacy cần khớp role/phòng ban. Xem [ADR-003](../../architecture/decisions/adr-003-google-identity-and-roster-admission.md) và [contract](../02-architecture/designs/TECH-google-admission.md).
