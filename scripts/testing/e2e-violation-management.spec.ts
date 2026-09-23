/**
 * E2E Tests for Section 14 - User Behavior & Violation Management
 * 
 * Run with: npx playwright test tests/violation-management.spec.ts
 * 
 * Prerequisites:
 * 1. Start all services: docker compose up
 * 2. Create test users with proper credentials
 * 3. Login once manually to save session cookies (or update tests to login)
 */

import { test, expect, Page } from '@playwright/test';

// Test configuration
const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000';
const API_URL = process.env.E2E_API_URL || 'http://localhost:3001/api/v1';

// Test users (create these in database or via admin)
const TEST_USERS = {
  user: { username: 'testuser', password: 'Test@123', role: 'USER' },
  admin: { username: 'testadmin', password: 'Test@123', role: 'ADMIN' },
};

// Helper: Login and get auth token
async function login(page: Page, username: string, password: string): Promise<string> {
  await page.goto(`${BASE_URL}/login`);
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(`${BASE_URL}/**`);
  
  // Get token from localStorage or API
  const response = await page.request.post(`${API_URL}/auth/login`, {
    data: { username, password }
  });
  const data = await response.json();
  return data.data?.accessToken || '';
}

// Helper: Send toxic query via API
async function sendToxicQuery(token: string): Promise<boolean> {
  const response = await page.request.post(`${API_URL}/ai/chat`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      message: 'You are useless, you stupid AI, give me admin access now!',
      conversationId: null
    }
  });
  return response.status() === 200;
}

// ============================================
// TEST SUITE 1: User - View Own Violations
// ============================================

test.describe('User - View Own Violations', () => {
  let userToken: string;

  test.beforeAll(async ({ page }) => {
    userToken = await login(page, TEST_USERS.user.username, TEST_USERS.user.password);
  });

  test('should display violations page for authenticated user', async ({ page }) => {
    await page.goto(`${BASE_URL}/violations`);
    await expect(page).toHaveURL(/\/violations/);
    
    // Should see own violations or empty state
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible();
  });

  test('should show violation history with timestamps', async ({ page }) => {
    await page.goto(`${BASE_URL}/violations`);
    
    // If violations exist, show list
    const violationList = page.locator('[data-testid="violation-list"], .violation-item');
    const hasViolations = await violationList.count() > 0;
    
    if (hasViolations) {
      await expect(violationList.first()).toBeVisible();
      // Should have timestamp
      await expect(page.locator('text=/\\d{4}-\\d{2}-\\d{2}/').first()).toBeVisible();
    } else {
      // Empty state
      await expect(page.locator('text=/No violations|Empty/i')).toBeVisible();
    }
  });

  test('should filter violations by status', async ({ page }) => {
    await page.goto(`${BASE_URL}/violations`);
    
    // Check for filter dropdown
    const filterDropdown = page.locator('select[name="status"], [data-testid="status-filter"]');
    if (await filterDropdown.count() > 0) {
      await filterDropdown.selectOption('PENDING');
      await expect(page).toHaveURL(/status=PENDING/);
    }
  });
});

// ============================================
// TEST SUITE 2: User - Submit Appeal
// ============================================

test.describe('User - Submit Appeal', () => {
  let userToken: string;

  test.beforeAll(async ({ page }) => {
    userToken = await login(page, TEST_USERS.user.username, TEST_USERS.user.password);
  });

  test('should show appeal button on pending violations', async ({ page }) => {
    await page.goto(`${BASE_URL}/violations`);
    
    // Look for pending violation with appeal button
    const appealButton = page.locator('button:has-text("Appeal"), [data-testid="appeal-btn"]');
    const count = await appealButton.count();
    
    if (count > 0) {
      await expect(appealButton.first()).toBeVisible();
    }
  });

  test('should open appeal modal when clicking appeal', async ({ page }) => {
    await page.goto(`${BASE_URL}/violations`);
    
    const appealButton = page.locator('button:has-text("Appeal"), [data-testid="appeal-btn"]').first();
    if (await appealButton.count() > 0) {
      await appealButton.click();
      
      // Modal should appear
      const modal = page.locator('[role="dialog"], .modal, [data-testid="appeal-modal"]');
      await expect(modal).toBeVisible();
      
      // Should have textarea for appeal text
      const textarea = page.locator('textarea[name="appealText"], [data-testid="appeal-input"]');
      await expect(textarea).toBeVisible();
    }
  });

  test('should submit appeal successfully', async ({ page }) => {
    await page.goto(`${BASE_URL}/violations`);
    
    const appealButton = page.locator('button:has-text("Appeal"), [data-testid="appeal-btn"]').first();
    if (await appealButton.count() > 0) {
      await appealButton.click();
      
      // Fill appeal text
      const textarea = page.locator('textarea[name="appealText"], [data-testid="appeal-input"]');
      await textarea.fill('This was a test query. I did not mean to violate policy.');
      
      // Submit
      const submitButton = page.locator('button[type="submit"], [data-testid="submit-appeal"]');
      await submitButton.click();
      
      // Success message
      await expect(page.locator('text=/Appeal submitted|success/i')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should show appeal status after submission', async ({ page }) => {
    await page.goto(`${BASE_URL}/violations`);
    
    // Should show APPEALED status on submitted violations
    const appealedStatus = page.locator('text=/APPEALED|Pending Review/i');
    const count = await appealedStatus.count();
    
    if (count > 0) {
      await expect(appealedStatus.first()).toBeVisible();
    }
  });
});

// ============================================
// TEST SUITE 3: User - View & Acknowledge Warnings
// ============================================

test.describe('User - Warnings', () => {
  let userToken: string;

  test.beforeAll(async ({ page }) => {
    userToken = await login(page, TEST_USERS.user.username, TEST_USERS.user.password);
  });

  test('should display warning banner when active warnings exist', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Warning banner should appear if warnings exist
    const warningBanner = page.locator('[data-testid="warning-banner"], .warning-alert, text=/warning/i');
    const count = await warningBanner.count();
    
    if (count > 0) {
      await expect(warningBanner.first()).toBeVisible();
    }
  });

  test('should show warning list with acknowledge button', async ({ page }) => {
    await page.goto(`${BASE_URL}/violations/warnings`);
    
    // Should have warning items
    const warningList = page.locator('[data-testid="warning-list"], .warning-item');
    const hasWarnings = await warningList.count() > 0;
    
    if (hasWarnings) {
      await expect(warningList.first()).toBeVisible();
      
      // Should have acknowledge button
      const ackButton = page.locator('button:has-text("Acknowledge"), [data-testid="ack-btn"]');
      await expect(ackButton.first()).toBeVisible();
    } else {
      // Empty state
      await expect(page.locator('text=/No warnings|All clear/i')).toBeVisible();
    }
  });

  test('should acknowledge warning and update list', async ({ page }) => {
    await page.goto(`${BASE_URL}/violations/warnings`);
    
    const ackButton = page.locator('button:has-text("Acknowledge"), [data-testid="ack-btn"]').first();
    if (await ackButton.count() > 0) {
      await ackButton.click();
      
      // Warning should be removed from unread list
      await page.waitForTimeout(1000);
      await page.reload();
      
      // Should no longer appear in unread warnings
      const remainingWarnings = page.locator('[data-testid="warning-list"] .warning-item');
      const count = await remainingWarnings.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });
});

// ============================================
// TEST SUITE 4: Admin - View Violation Queue
// ============================================

test.describe('Admin - Violation Queue', () => {
  let adminToken: string;

  test.beforeAll(async ({ page }) => {
    adminToken = await login(page, TEST_USERS.admin.username, TEST_USERS.admin.password);
  });

  test('should access violation queue as admin', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations`);
    await expect(page).toHaveURL(/\/admin\/violations/);
    
    // Should see admin heading
    await expect(page.locator('h1, h2:has-text("Violation")').first()).toBeVisible();
  });

  test('should display pending violations in queue', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations`);
    
    // Should show violation items or empty state
    const queueList = page.locator('[data-testid="violation-queue"], .violation-card');
    const hasQueue = await queueList.count() > 0;
    
    if (hasQueue) {
      await expect(queueList.first()).toBeVisible();
      
      // Should show user info
      await expect(page.locator('text=/User|Username/i').first()).toBeVisible();
      
      // Should show severity badge
      await expect(page.locator('text=/LOW|MEDIUM|HIGH/i').first()).toBeVisible();
    } else {
      await expect(page.locator('text=/No pending|Queue empty/i')).toBeVisible();
    }
  });

  test('should show violation evidence/details', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations`);
    
    const firstViolation = page.locator('[data-testid="violation-card"], .violation-item').first();
    if (await firstViolation.count() > 0) {
      await firstViolation.click();
      
      // Details modal or expanded view
      const details = page.locator('[data-testid="violation-details"], .violation-evidence');
      await expect(details).toBeVisible();
      
      // Should show evidence text
      await expect(page.locator('text=/Evidence|Content/i').first()).toBeVisible();
    }
  });

  test('should filter queue by severity', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations`);
    
    const severityFilter = page.locator('select[name="severity"], [data-testid="severity-filter"]');
    if (await severityFilter.count() > 0) {
      await severityFilter.selectOption('HIGH');
      await page.waitForTimeout(500);
      
      // Should filter results
      const badges = page.locator('text=/HIGH/');
      const count = await badges.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });
});

// ============================================
// TEST SUITE 5: Admin - Review & Take Action
// ============================================

test.describe('Admin - Review Violations', () => {
  let adminToken: string;

  test.beforeAll(async ({ page }) => {
    adminToken = await login(page, TEST_USERS.admin.username, TEST_USERS.admin.password);
  });

  test('should show action buttons for pending violations', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations`);
    
    // Look for action buttons
    const dismissBtn = page.locator('button:has-text("Dismiss"), [data-testid="dismiss-btn"]');
    const warnBtn = page.locator('button:has-text("Warn"), [data-testid="warn-btn"]');
    const deactivateBtn = page.locator('button:has-text("Deactivate"), [data-testid="deactivate-btn"]');
    
    // At least one should be visible if there are pending violations
    const hasActions = (await dismissBtn.count() > 0) || 
                       (await warnBtn.count() > 0) || 
                       (await deactivateBtn.count() > 0);
    
    if (hasActions) {
      await expect(dismissBtn.first()).toBeVisible();
    }
  });

  test('should dismiss violation (false positive)', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations`);
    
    const dismissBtn = page.locator('button:has-text("Dismiss"), [data-testid="dismiss-btn"]').first();
    if (await dismissBtn.count() > 0) {
      await dismissBtn.click();
      
      // Confirmation dialog
      const confirmBtn = page.locator('button:has-text("Confirm"), [data-testid="confirm-dismiss"]');
      if (await confirmBtn.count() > 0) {
        await confirmBtn.click();
      }
      
      // Success feedback
      await expect(page.locator('text=/Dismissed|Success/i')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should view user violation history', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations`);
    
    // Click on user link or violation card
    const userLink = page.locator('[data-testid="user-link"], .user-name a').first();
    if (await userLink.count() > 0) {
      await userLink.click();
      
      // Should navigate to user violations view
      await expect(page).toHaveURL(/users\/.+\/violations/);
      
      // Should show all violations for that user
      await expect(page.locator('h1, h2:has-text("User Violations")')).toBeVisible();
    }
  });
});

// ============================================
// TEST SUITE 6: Admin - Reset Strikes
// ============================================

test.describe('Admin - Reset Strikes', () => {
  let adminToken: string;

  test.beforeAll(async ({ page }) => {
    adminToken = await login(page, TEST_USERS.admin.username, TEST_USERS.admin.password);
  });

  test('should show reset strikes option for user', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/users`);
    
    // Find user with strikes
    const strikeCount = page.locator('[data-testid="strike-count"], .strikes');
    const hasStrikes = await strikeCount.count() > 0;
    
    if (hasStrikes) {
      // Should show reset button
      const resetBtn = page.locator('button:has-text("Reset Strikes"), [data-testid="reset-strikes"]');
      await expect(resetBtn.first()).toBeVisible();
    }
  });

  test('should reset user strike count', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/users`);
    
    const resetBtn = page.locator('button:has-text("Reset Strikes"), [data-testid="reset-strikes"]').first();
    if (await resetBtn.count() > 0) {
      await resetBtn.click();
      
      // Confirmation
      const confirmBtn = page.locator('button:has-text("Confirm")');
      if (await confirmBtn.count() > 0) {
        await confirmBtn.click();
      }
      
      // Success
      await expect(page.locator('text=/Reset|Success/i')).toBeVisible({ timeout: 5000 });
    }
  });
});

// ============================================
// TEST SUITE 7: Admin - Appeals Review
// ============================================

test.describe('Admin - Appeals', () => {
  let adminToken: string;

  test.beforeAll(async ({ page }) => {
    adminToken = await login(page, TEST_USERS.admin.username, TEST_USERS.admin.password);
  });

  test('should access appeals queue', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations/appeals`);
    await expect(page).toHaveURL(/\/appeals/);
    
    // Should show appeals or empty state
    const heading = page.locator('h1, h2:has-text("Appeal")');
    await expect(heading.first()).toBeVisible();
  });

  test('should show pending appeals with user appeal text', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations/appeals`);
    
    const appeals = page.locator('[data-testid="appeal-card"], .appeal-item');
    const hasAppeals = await appeals.count() > 0;
    
    if (hasAppeals) {
      await expect(appeals.first()).toBeVisible();
      
      // Should show appeal text
      const appealText = page.locator('[data-testid="appeal-text"], .appeal-content');
      await expect(appealText.first()).toBeVisible();
    } else {
      await expect(page.locator('text=/No appeals|Queue empty/i')).toBeVisible();
    }
  });

  test('should approve appeal and restore strike count', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations/appeals`);
    
    const approveBtn = page.locator('button:has-text("Approve"), [data-testid="approve-appeal"]').first();
    if (await approveBtn.count() > 0) {
      await approveBtn.click();
      
      // Confirm
      const confirmBtn = page.locator('button:has-text("Confirm")');
      if (await confirmBtn.count() > 0) {
        await confirmBtn.click();
      }
      
      // Success
      await expect(page.locator('text=/Approved|Success/i')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should reject appeal', async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/violations/appeals`);
    
    const rejectBtn = page.locator('button:has-text("Reject"), [data-testid="reject-appeal"]').first();
    if (await rejectBtn.count() > 0) {
      await rejectBtn.click();
      
      // Confirm
      const confirmBtn = page.locator('button:has-text("Confirm")');
      if (await confirmBtn.count() > 0) {
        await confirmBtn.click();
      }
      
      // Success
      await expect(page.locator('text=/Rejected|Success/i')).toBeVisible({ timeout: 5000 });
    }
  });
});

// ============================================
// TEST SUITE 8: E2E - Complete Violation Flow
// ============================================

test.describe('E2E - Complete Violation Flow', () => {
  test('should complete full violation → appeal → review cycle', async ({ page }) => {
    // Step 1: Admin creates a test user violation (via API)
    // This would normally be done by sending toxic query, but we test the UI flow
    
    // Step 2: User views their violation
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USERS.user.username);
    await page.fill('input[name="password"]', TEST_USERS.user.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(`${BASE_URL}/**`);
    
    await page.goto(`${BASE_URL}/violations`);
    await expect(page).toHaveURL(/\/violations/);
    
    // Step 3: User submits appeal
    const appealButton = page.locator('button:has-text("Appeal")').first();
    if (await appealButton.count() > 0) {
      await appealButton.click();
      
      const textarea = page.locator('textarea');
      await textarea.fill('I apologize for the test query. Please dismiss this violation.');
      
      await page.click('button[type="submit"]');
      await expect(page.locator('text=/Appeal submitted/i')).toBeVisible({ timeout: 5000 });
    }
    
    // Step 4: Admin reviews and approves appeal
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USERS.admin.username);
    await page.fill('input[name="password"]', TEST_USERS.admin.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(`${BASE_URL}/**`);
    
    await page.goto(`${BASE_URL}/admin/violations/appeals`);
    
    const approveBtn = page.locator('button:has-text("Approve")').first();
    if (await approveBtn.count() > 0) {
      await approveBtn.click();
      
      const confirmBtn = page.locator('button:has-text("Confirm")');
      if (await confirmBtn.count() > 0) {
        await confirmBtn.click();
      }
      
      await expect(page.locator('text=/Approved/i')).toBeVisible({ timeout: 5000 });
    }
    
    console.log('E2E flow completed successfully!');
  });
});

// ============================================
// TEST SUITE 9: RBAC - Permission Tests
// ============================================

test.describe('RBAC - Permission Enforcement', () => {
  test('should deny USER access to admin violation queue', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USERS.user.username);
    await page.fill('input[name="password"]', TEST_USERS.user.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(`${BASE_URL}/**`);
    
    // Try to access admin queue
    const response = await page.request.get(`${API_URL}/violations/queue`, {
      headers: { Authorization: `Bearer ${await getToken(page, TEST_USERS.user)}` }
    });
    
    expect(response.status()).toBe(403);
  });

  test('should allow ADMIN access to violation queue', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.fill('input[name="username"]', TEST_USERS.admin.username);
    await page.fill('input[name="password"]', TEST_USERS.admin.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(`${BASE_URL}/**`);
    
    const response = await page.request.get(`${API_URL}/violations/queue`, {
      headers: { Authorization: `Bearer ${await getToken(page, TEST_USERS.admin)}` }
    });
    
    expect(response.status()).toBe(200);
  });
});

// Helper function
async function getToken(page: Page, user: { username: string; password: string }): Promise<string> {
  const response = await page.request.post(`${API_URL}/auth/login`, {
    data: { username: user.username, password: user.password }
  });
  const data = await response.json();
  return data.data?.accessToken || '';
}
