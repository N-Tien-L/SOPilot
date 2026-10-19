---
name: run-test
description: Executing, debugging, and orchestrating test suites across all SOPilot services and infrastructure.
version: 1.0.0
author: SOPilot Team
---

# Run Test Skill

This skill guides the AI Agent in executing, filtering, and troubleshooting test suites across the SOPilot polyglot architecture.

---

## When to use this skill
- When verifying code changes immediately after editing.
- When validating a completed ticket before moving to review.
- When checking service health or running pre-commit verification.

---

## 1. Centralized Test Runner (Recommended)

Run tests directly from repository root using the unified runner:

```powershell
# Chạy tất cả tests của một service
./scripts/run-tests.ps1 -Scope <service-name> -Type all

# Chỉ chạy unit tests
./scripts/run-tests.ps1 -Scope <service-name> -Type unit

# Chỉ chạy integration tests (chỉ ai-qa-service có tests/integration)
./scripts/run-tests.ps1 -Scope ai-qa-service -Type integration
```

### Bảng Scope hợp lệ:
| Scope Argument | Target Service | Công nghệ thực thi |
|---|---|---|
| `auth-service` | Authentication Service | Maven Wrapper (`all` = `mvnw verify`, `unit` = `mvnw test`; không hỗ trợ `integration`) |
| `user-service` | User & Roster Service | như trên |
| `knowledge-service` | Document Service | như trên |
| `metadata-service` | Metadata & Tags Service | như trên |
| `feedback-service` | Analytics Service | như trên |
| `ai-qa-service` | AI RAG Pipeline | `uv run pytest tests/<unit|integration>` hoặc `tests/` |
| `ingestion-service` | Ingestion Worker | Chỉ `-Type all` (`tests/ingestion_tests`) |
| `api-gateway` | API Gateway | `pnpm test`; `integration` lỗi vì chưa có `test/jest-e2e.json` |
| `frontend` | Next.js Web App | Chưa hỗ trợ: không có script `test`. Dùng `./scripts/validate-build.ps1 -Scope web` |

---

## 2. Targeted Single-Test Execution (Fast Iteration)

Trong quá trình debug nhanh, không nên chạy toàn bộ test suite. Hãy chạy chính xác file hoặc method cần kiểm tra:

### Spring Boot (Java)
```bash
cd services/<service-name>
# Chạy 1 class test cụ thể
./mvnw test -Dtest=RosterServiceTest

# Chạy đúng 1 method test cụ thể
./mvnw test -Dtest=RosterServiceTest#claimRoster_ShouldSucceed_WhenValid
```

### FastAPI (Python)
```bash
cd services/<service-name>
# Chạy 1 file test
uv run pytest tests/unit/test_retrieval.py -v

# Chạy theo tên hàm test (filter -k)
uv run pytest -k "test_hybrid_search" -v
```

### NestJS (Gateway)
```bash
cd services/api-gateway
pnpm test -- src/auth/jwt-auth.guard.spec.ts
```

### Next.js (Frontend)
```bash
cd frontend/web
pnpm test -- components/auth/google-sign-in.test.tsx
```

---

## 3. Platform Smoke & Pre-Commit Verification

### Kiểm tra tình trạng hoạt động toàn bộ hệ thống:
```powershell
./scripts/check-services.ps1
# hoặc
./tests/smoke/smoke-check.ps1
```

### Tự động chạy toàn bộ quy trình kiểm thử trước khi commit:
```powershell
./scripts/pre-commit-check.ps1
```
Script sẽ tự động:
1. Dò tìm các file thay đổi trong git.
2. Quét debug statements (`console.log`, `print`, `System.out.println`).
3. Quét secrets và `.env` lọt vào diff.
4. Tự động chạy test của tất cả services bị ảnh hưởng.
5. Kiểm tra tính hợp lệ của `docker-compose.yml`.

---

## 4. Xử lý sự cố khi chạy Test (Troubleshooting)
- **Lỗi thiếu DB Connection:** Đảm bảo container postgres đang chạy (`docker compose up -d postgres`) hoặc test được cấu hình mock / in-memory.
- **Lỗi JAVA_HOME:** Đảm bảo cài đặt JDK 17+ và biến môi trường `JAVA_HOME` trỏ tới thư mục cài đặt JDK.
- **Lỗi Python venv:** Chạy `uv sync --extra dev` trong thư mục service trước khi chạy pytest.
