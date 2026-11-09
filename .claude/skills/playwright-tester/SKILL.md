---
name: playwright-tester
description: >
  Automated UI and E2E testing for SOPilot using Playwright's native test runner. Writes persistent .spec.ts
  test files in tests/e2e/, runs them via pnpm/npx playwright test against frontend/web, and fixes failures automatically.
  Use when testing the web frontend, verifying user flows, validating form submissions, testing authentication
  redirects, checking UI components, or testing responsive layouts.
---

# Playwright Tester (SOPilot V2)

Automated E2E and UI testing for SOPilot using Playwright with persistent test files, native parallel execution, and automated triage loops.

> [!IMPORTANT]
> **SOPilot Project Constraints & Conventions**:
> - **Package Manager**: Always use **`pnpm`**, never `npm` or `yarn`. Frontend dependencies belong to `frontend/web/package.json`.
> - **Dependency Policy (Constraint #12)**: Check if `@playwright/test` is already installed before installing. Do not install new dependencies without confirming with the user or having an explicit ticket task.
> - **Directory Structure**:
>   - Test specs: `tests/e2e/*.spec.ts` (per `tests/README.md`).
>   - App source: `frontend/web/` (Next.js 16 App Router, React 19, Tailwind 4).
>   - Configuration: `playwright.config.ts` located at repository root.
> - **Language**: User-facing copy in SOPilot is **Vietnamese** (`vi-VN`). When writing selectors with `getByRole`, `getByLabel`, `getByText`, match Vietnamese copy (e.g., `Đăng nhập`, `Tải lên`, `Tài liệu`, `Không tìm thấy`).
> - **Backend & Auth Awareness**: SOPilot V2 requires backend services (`core-api`, `ai-service`) and RS256 JWT tokens. For pure UI/client-side tests, use Playwright's `page.route()` to mock API responses, or ensure local V2 infra (`docker compose -f docker-compose.v2.yml up -d`) is running for full integration.

---

## Prerequisites & Setup

### 1. Verify Installation
Check if Playwright is already installed in `frontend/web/package.json`:
```powershell
Get-Content frontend/web/package.json | ConvertFrom-Json | Select-Object -ExpandProperty devDependencies
```

If not installed and user agrees to add it:
```powershell
pnpm --dir frontend/web add -D @playwright/test
pnpm --dir frontend/web exec playwright install chromium
```

### 2. Verify / Create `playwright.config.ts`
Ensure `playwright.config.ts` exists at repo root. If missing, create it:

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'line',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'pnpm --dir frontend/web dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
```

---

## Workflow

### Phase 1: Assess
1. Inspect the target route or UI component in `frontend/web/app/` or `frontend/web/components/`.
2. Check existing specs in `tests/e2e/`.
3. Determine if the test requires:
   - **Static UI / Unauthenticated**: Login page, 404 page, theme toggle, public docs.
   - **Mocked API**: Form validations, upload modal interactions, search filters with `page.route()`.
   - **Full Integration**: Requires running Docker V2 infra and backend services.

### Phase 2: Author Tests
Write `.spec.ts` files inside `tests/e2e/`:

```
tests/e2e/
  ├── auth-flows.spec.ts         # Login UI, Google redirect button, invalid state
  ├── document-viewer.spec.ts    # Document viewer, citation side-panel, preview modal
  ├── responsive-layout.spec.ts  # Mobile viewport, sidebar collapse, navigation
  └── upload-modal.spec.ts       # Upload dropzone validation, file types
```

**Writing robust SOPilot tests:**
- Prefer user-facing locators matching Vietnamese text:
  ```typescript
  await page.getByRole('button', { name: /đăng nhập/i }).click();
  await expect(page.getByText('Vui lòng chọn tệp')).toBeVisible();
  ```
- Use `page.route()` to mock backend endpoints when running lightweight UI tests:
  ```typescript
  await page.route('/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
  });
  ```
- Keep tests isolated: use `test.beforeEach()` for page navigation and reset.

### Phase 3: Execute
Run the test runner from the repository root in PowerShell:

```powershell
pnpm --dir frontend/web exec playwright test tests/e2e/<file-name>.spec.ts --reporter=line
```
Or for full suite:
```powershell
pnpm --dir frontend/web exec playwright test --reporter=line
```

Key flags:
- `--project=chromium` — Fast single-browser execution.
- `--headed` — Use only if the user specifically asks to watch the browser.
- `--trace on` — Record trace for debugging difficult failures.

### Phase 4: Fix Loop (Max 3 attempts)
When tests fail:
1. **Read failure output**: Locate the exact selector, timeout, or assertion mismatch.
2. **Classify**:
   - **Test bug**: Wrong selector, missing `await`, timing issue (missing `waitForLoadState` or locator wait), unhandled locale string.
   - **App bug**: Broken UI rendering, unhandled error state, unexpected redirect.
3. **Fix & Rerun**:
   - Update either the test or the frontend component.
   - Re-run the specific test file to verify.
4. **Stop after 3 attempts**: If it still fails, report the root cause and ask user for guidance.

### Phase 5: Report
Summarize:
- Total tests passed, failed, skipped.
- Any application bugs found and fixed.
- How authentication / mock APIs were handled.
- Screenshot or trace artifact locations if any failures occurred.
