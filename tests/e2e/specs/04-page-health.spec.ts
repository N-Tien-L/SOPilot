import { expect, test } from '@playwright/test';
import { signInAs } from '../support/session';
import { loadWorld, PERSONA_KEYS, type World } from '../support/world';

// Every screen for every kind of person, at a desktop and a phone width: no script errors, no failed
// requests, nothing wider than the screen. A broad net for what a person would notice at once.

let world: World;
test.beforeAll(() => {
  world = loadWorld();
});

const PAGES = ['/chat', '/documents', '/members', '/departments', '/settings'];
const SIZES = [
  { name: 'desktop', width: 1280, height: 800 },
  { name: 'phone', width: 390, height: 844 },
];
const PERSONAS = PERSONA_KEYS.filter((k) => ['owner', 'admin', 'alphaPub', 'betaMember'].includes(k));

for (const key of PERSONAS) {
  for (const size of SIZES) {
    test(`${key} sees clean pages on a ${size.name}`, async ({ page }) => {
      const problems: string[] = [];
      page.on('pageerror', (e) => problems.push(`script error: ${e.message}`));
      page.on('console', (m) => {
        if (m.type() === 'error') problems.push(`console error: ${m.text()}`);
      });
      page.on('response', (r) => {
        if (r.status() >= 500) problems.push(`HTTP ${r.status()} ${r.url()}`);
      });
      await page.setViewportSize({ width: size.width, height: size.height });
      await signInAs(page, world.personas[key], world, '/documents');
      for (const path of PAGES) {
        await page.goto(path);
        await expect(page.getByRole('main').or(page.locator('main, [role="main"], body')).first()).toBeVisible();
        await page.waitForLoadState('networkidle');
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(overflow, `${path} is wider than the ${size.name} screen`).toBeLessThanOrEqual(1);
      }
      expect(problems).toEqual([]);
    });
  }
}
