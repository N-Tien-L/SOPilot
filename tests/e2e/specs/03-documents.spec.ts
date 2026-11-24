import { expect, test, type Page } from '@playwright/test';
import { sopMarkdown } from '../support/fixtures';
import { signInAs } from '../support/session';
import { loadWorld, type World } from '../support/world';

// The Documents screen for each kind of person: which tabs they get, what they can do, what they must not see.

let world: World;
test.beforeAll(() => {
  world = loadWorld();
});

const heading = (page: Page) => expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible();

test.describe('tabs by role', () => {
  test('a plain member only reads: one list, no Upload, no Edit, nothing of another department', async ({ page }) => {
    await signInAs(page, world.personas.betaMember, world);
    await heading(page);
    await expect(page.getByRole('tab')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Upload' })).toHaveCount(0);
    await expect(page.getByText(world.docs.company.title)).toBeVisible();
    await expect(page.getByText(world.docs.alpha.title)).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0);
  });

  test('a department publisher gets Manage for the department and a read-only tab for everything', async ({ page }) => {
    await signInAs(page, world.personas.alphaPub, world);
    await heading(page);
    await expect(page.getByRole('tab', { name: 'Manage: Alpha' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('button', { name: 'Upload' })).toBeVisible();
    await expect(page.getByText(world.docs.alpha.title)).toBeVisible();
    await expect(page.getByText(world.docs.company.title)).toHaveCount(0); // not a department document

    await page.getByRole('tab', { name: 'All documents' }).click();
    await expect(page.getByText(world.docs.company.title)).toBeVisible();
    await expect(page.getByText(world.docs.alpha.title)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Upload' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0);
  });

  test('the workspace publisher has one Manage tab and publishes for the whole workspace only', async ({ page }) => {
    await signInAs(page, world.personas.wsPub, world);
    await heading(page);
    await expect(page.getByRole('tab', { name: 'All documents' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Upload' }).click();
    const dialog = page.getByRole('dialog', { name: 'Upload documents' });
    await expect(dialog.getByText('Whole workspace (everyone can read)')).toBeVisible();
    await expect(dialog.getByRole('radio')).toHaveCount(0); // one choice, so no picker
    await expect(dialog.getByLabel('Prepared by (optional)')).toBeVisible();
  });

  test('an owner who is not a publisher manages everything, filters by department and cannot upload', async ({ page }) => {
    await signInAs(page, world.personas.owner, world);
    await heading(page);
    await expect(page.getByRole('tab', { name: 'Manage' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Categories' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'All documents' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Upload' })).toHaveCount(0);
    await expect(page.getByText(world.docs.alpha.title)).toBeVisible();
    await expect(page.getByText(world.docs.company.title)).toBeVisible();

    const department = page.getByRole('combobox', { name: 'Department' });
    await department.selectOption({ label: 'Alpha' });
    await expect(page.getByText(world.docs.alpha.title)).toBeVisible();
    await expect(page.getByText(world.docs.company.title)).toHaveCount(0);
    await department.selectOption({ label: 'Whole workspace' });
    await expect(page.getByText(world.docs.company.title)).toBeVisible();
    await expect(page.getByText(world.docs.alpha.title)).toHaveCount(0);
    await department.selectOption({ label: 'All departments' });
    await expect(page.getByText(world.docs.alpha.title)).toBeVisible();
  });

  test('an admin who is not a publisher reads, and manages categories', async ({ page }) => {
    await signInAs(page, world.personas.admin, world);
    await heading(page);
    await expect(page.getByRole('tab', { name: 'Documents' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Categories' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Upload' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0);
  });
});

test.describe('filters', () => {
  test('every filter can be set and then cleared back to All', async ({ page }) => {
    await signInAs(page, world.personas.owner, world);
    await heading(page);
    const status = page.getByRole('combobox', { name: 'Status' });
    await status.selectOption({ label: 'Failed' });
    await expect(page.getByText('No documents')).toBeVisible();
    await status.selectOption({ label: 'All statuses' });
    await expect(page.getByText(world.docs.alpha.title)).toBeVisible();
    await expect(page.getByLabel('Tag')).toHaveCount(0); // tags are gone
    await page.getByLabel('Search title').fill('zzz-no-such-title');
    await expect(page.getByText('No documents')).toBeVisible();
    await page.getByLabel('Search title').fill('');
    await expect(page.getByText(world.docs.alpha.title)).toBeVisible();
  });

  test('a category created in the Categories tab shows up as a filter', async ({ page }) => {
    await signInAs(page, world.personas.owner, world);
    await page.getByRole('tab', { name: 'Categories' }).click();
    await page.getByRole('button', { name: 'New category' }).click();
    await page.getByRole('dialog').getByLabel('Name').fill('E2E Policies');
    await page.getByRole('dialog').getByRole('button', { name: 'Create' }).click();
    await expect(page.getByText('E2E Policies')).toBeVisible();
    await page.getByRole('tab', { name: 'Manage' }).click();
    await expect(page.getByRole('combobox', { name: 'Category' }).getByRole('option', { name: 'E2E Policies' })).toHaveCount(1);
  });
});

test.describe('publishing as a department publisher', () => {
  test('uploads into the department, shows who prepared it, and the details save without a tag', async ({ page }) => {
    await signInAs(page, world.personas.alphaPub, world);
    await page.getByRole('button', { name: 'Upload' }).click();
    const dialog = page.getByRole('dialog', { name: 'Upload documents' });
    await expect(dialog.getByText('Alpha only (its members can read)')).toBeVisible();
    await expect(dialog.getByRole('radio')).toHaveCount(0);
    await expect(dialog.getByLabel('Prepared by (optional)')).toHaveAttribute('placeholder', 'Alpha');

    const name = `e2e-ui-${world.run}`;
    await dialog.getByLabel('Files to upload').setInputFiles({ name: `${name}.md`, mimeType: 'text/markdown', buffer: sopMarkdown(name, `${world.run}ui`) });
    await expect(dialog.getByText(`${name}.md`)).toBeVisible();
    await dialog.getByRole('button', { name: 'Close', exact: true }).click();

    const row = page.getByRole('row', { name: new RegExp(name) });
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row).toContainText('Alpha'); // prepared by, defaulted to the department
    await expect(row).toContainText('Departments: Alpha');
    await expect(row).toContainText(world.personas.alphaPub.name); // published by

    await row.getByRole('button', { name: 'Edit' }).click();
    const edit = page.getByRole('dialog', { name: 'Document details' });
    await expect(edit.getByLabel('Tags')).toHaveCount(0);
    await edit.getByLabel('Description').fill('E2E description');
    // A category is required once the workspace has one (the filters spec created it).
    await edit.getByLabel('Category').selectOption({ label: 'E2E Policies' });
    await edit.getByLabel('Prepared by').fill('Alpha QA team');
    await edit.getByRole('button', { name: 'Save details' }).click();
    await expect(edit).toHaveCount(0);
    await expect(page.getByRole('row', { name: new RegExp(name) })).toContainText('Alpha QA team');
  });

  test('the document just published is invisible to another department', async ({ page }) => {
    await signInAs(page, world.personas.betaMember, world);
    await expect(page.getByText(`e2e-ui-${world.run}`)).toHaveCount(0);
  });
});
