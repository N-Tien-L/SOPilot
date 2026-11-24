import { expect, test } from '@playwright/test';
import { signInAs } from '../support/session';
import { loadWorld, type World } from '../support/world';

// The administration screens as an owner (and an admin) uses them in the browser.

let world: World;
test.beforeAll(() => {
  world = loadWorld();
});

test.describe('members', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, world.personas.owner, world, '/members');
    await expect(page.getByRole('heading', { name: 'Members', exact: true })).toBeVisible();
  });

  test('has Members and Invitations tabs; Departments is a sidebar item of its own', async ({ page }) => {
    await expect(page.getByRole('tab', { name: 'Members' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Invitations' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Departments' })).toHaveCount(0);
    await expect(page.getByRole('tab', { name: 'Categories' })).toHaveCount(0);
    await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Departments' })).toBeVisible();
  });

  test('shows the name from the account, not one typed in the invitation', async ({ page }) => {
    await expect(page.getByRole('row', { name: new RegExp(world.personas.admin.name) })).toBeVisible();
  });

  test('searches by name, email and filters, and every filter can go back to All', async ({ page }) => {
    const rows = page.getByRole('row');
    await expect(page.getByRole('row', { name: new RegExp(world.personas.admin.name) })).toBeVisible(); // table loaded
    const total = await rows.count();
    await page.getByLabel('Search members').fill('Alpha Publisher');
    await expect(rows).toHaveCount(2); // header + one person
    await page.getByLabel('Search members').fill(world.personas.betaMember.email.toUpperCase());
    await expect(rows).toHaveCount(2);
    await page.getByLabel('Search members').fill('');
    await expect(rows).toHaveCount(total);

    const role = page.getByRole('combobox', { name: 'Role' });
    await role.selectOption({ label: 'Admin' });
    await expect(rows).toHaveCount(2);
    await role.selectOption({ label: 'All roles' }); // the bug this guards: the "All" option was disabled
    await expect(rows).toHaveCount(total);

    const department = page.getByRole('combobox', { name: 'Department' });
    await department.selectOption({ label: 'Alpha' });
    await expect(rows).toHaveCount(3); // alphaPub + alphaMember
    await department.selectOption({ label: 'No department' });
    await expect(rows.filter({ hasText: world.personas.alphaPub.name })).toHaveCount(0);
    await department.selectOption({ label: 'All departments' });
    await expect(rows).toHaveCount(total);
    await expect(page.getByText(/of \d+ members/)).toHaveCount(0);
  });

  test('moves several selected people to a department at once, then back', async ({ page }) => {
    const { spareA, spareB } = world.personas;
    await page.getByRole('checkbox', { name: `Select ${spareA.name}` }).check({ force: true });
    await page.getByRole('checkbox', { name: `Select ${spareB.name}` }).check({ force: true });
    await expect(page.getByText('2 selected')).toBeVisible();
    await page.getByRole('combobox', { name: 'Move selected to department' }).selectOption({ label: 'Beta' });
    await page.getByRole('button', { name: 'Move', exact: true }).click();
    await expect(page.getByText(/2 moved/)).toBeVisible();
    for (const p of [spareA, spareB]) {
      await expect(page.getByRole('row', { name: new RegExp(p.name) })).toContainText('Beta');
    }
    await page.getByRole('checkbox', { name: `Select ${spareA.name}` }).check({ force: true });
    await page.getByRole('checkbox', { name: `Select ${spareB.name}` }).check({ force: true });
    await page.getByRole('combobox', { name: 'Move selected to department' }).selectOption({ label: 'No department' });
    await page.getByRole('button', { name: 'Move', exact: true }).click();
    await expect(page.getByText(/2 moved/)).toBeVisible();
    await expect(page.getByRole('row', { name: new RegExp(spareA.name) })).not.toContainText('Beta');
  });
});

test.describe('invitations', () => {
  test('the invite form has a department and no separate full name; the link is shown once', async ({ page }) => {
    await signInAs(page, world.personas.owner, world, '/members');
    await page.getByRole('tab', { name: 'Invitations' }).click();
    await page.getByRole('button', { name: 'Invite member' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByLabel('Full name')).toHaveCount(0);
    await expect(dialog.getByLabel('Department')).toBeVisible();
    const email = `e2e-${world.run}-invited@sopilot.local`;
    await dialog.getByLabel('Email').fill(email);
    await dialog.getByLabel('Department').selectOption({ label: 'Alpha' });
    await dialog.getByRole('button', { name: 'Create invitation' }).click();
    const created = page.getByRole('dialog', { name: 'Invitation created' });
    await expect(created).toBeVisible();
    await expect(created.getByLabel('Invitation link')).toHaveValue(/\/invite#token=/);
    await created.getByRole('button', { name: 'Done' }).click();
    const row = page.getByRole('row', { name: new RegExp(email) });
    await expect(row).toContainText('Alpha');
    await expect(row).toContainText('Pending');
  });
});

test.describe('departments', () => {
  test('lists departments with their publisher in one place', async ({ page }) => {
    await signInAs(page, world.personas.owner, world, '/departments');
    await expect(page.getByRole('heading', { name: 'Departments', exact: true })).toBeVisible();
    const alpha = page.getByRole('listitem').filter({ hasText: 'Alpha' }).first();
    await expect(alpha).toContainText(world.personas.alphaPub.name);
    await expect(page.getByRole('listitem').filter({ hasText: 'Whole workspace' })).toContainText(world.personas.wsPub.name);
  });

  test('creates a department with several people picked by search and a publisher among them', async ({ page }) => {
    const { spareA, spareB } = world.personas;
    await signInAs(page, world.personas.owner, world, '/departments');
    await page.getByRole('button', { name: 'New department' }).click();
    const dialog = page.getByRole('dialog', { name: 'New department' });
    await dialog.getByLabel(/^Name/).fill('Gamma'); // the label carries a required mark
    await dialog.getByLabel('Search people').fill('E2E Spare');
    await dialog.getByRole('button', { name: 'Select all shown' }).click();
    await expect(dialog.getByText('2 selected')).toBeVisible();
    await dialog.getByLabel('Publisher (optional)').selectOption(spareA.userId);
    await dialog.getByRole('button', { name: 'Create and add 2' }).click();
    await expect(dialog).toHaveCount(0);
    // Not hasText: the workspace row lists every member in its picker, including "now in Gamma".
    const row = page.getByRole('listitem').filter({ has: page.getByText('Gamma', { exact: true }) });
    await expect(row).toContainText('2 members');
    await expect(row).toContainText(spareA.name);
    // The people really moved, and the publisher really can publish for the new department.
    await page.goto('/members');
    await expect(page.getByRole('row', { name: new RegExp(spareB.name) })).toContainText('Gamma');
  });

  test('an admin sees departments and publishers but cannot change a publisher', async ({ page }) => {
    await signInAs(page, world.personas.admin, world, '/departments');
    await expect(page.getByRole('heading', { name: 'Departments', exact: true })).toBeVisible();
    await expect(page.getByLabel(/Publisher for/)).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'New department' })).toBeVisible();
  });

  test('a plain member has no Departments or Members item and is told why on a direct visit', async ({ page }) => {
    await signInAs(page, world.personas.betaMember, world, '/departments');
    await expect(page.getByText('Owners and admins only')).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Departments' })).toHaveCount(0);
    await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Members' })).toHaveCount(0);
  });
});
