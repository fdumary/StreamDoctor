import { test, expect } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

const demo = resolve(process.env.STREAMDOCTOR_DEMO_DIR || '../.local/demo');
const accounts = JSON.parse(readFileSync(resolve(demo, 'credentials.json'), 'utf8'));

async function login(page, account) {
  await page.getByLabel('Email', { exact: true }).fill(account.email);
  await page.getByLabel('Password', { exact: true }).fill(account.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'How is your stream feeling today?' })).toBeVisible();
}

test('volunteer photo, AI decisions, submission, independent review and FHIR', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await login(page, accounts.find(account => account.role === 'volunteer'));
  await expect(page.locator('.question')).toHaveCount(6);
  await expect(page.locator('.health-top')).toContainText('GREEN');
  await page.getByRole('switch', { name: 'Trust Lens' }).click();
  await expect(page.locator('.health-top')).toContainText('RED');
  for (const [index, choice] of ['Clear', 'None', 'Moderate', 'None', 'Plants', 'Colorless'].entries()) {
    await page.locator('.question').nth(index).getByRole('button', { name: choice, exact: true }).click();
  }
  const uniquePng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=', 'base64');
  const photo = readdirSync(resolve(demo, 'photos'), { recursive: true }).find(name => String(name).endsWith('.png'));
  await page.locator('input[type=file]').setInputFiles(photo ? resolve(demo, 'photos', String(photo)) : { name: 'synthetic.png', mimeType: 'image/png', buffer: uniquePng });
  await page.getByLabel('Allow this photo').check();
  await page.getByRole('button', { name: 'Analyze photo', exact: true }).click();
  await expect(page.locator('.suggestion')).toHaveCount(2);
  await expect(page.locator('.confidence-badge')).toContainText('SIMULATED');
  await page.locator('.suggestion').nth(0).getByRole('button', { name: 'Accept', exact: true }).click();
  await page.locator('.suggestion').nth(1).getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByLabel('Your foam', { exact: true }).selectOption('none');
  await page.getByRole('button', { name: 'Save AI decisions', exact: true }).click();
  await expect(page.getByText('Your AI decisions are saved.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Submit check-up', exact: true }).click();
  await expect(page.getByText('Check-up submitted. Its trust assessment is ready.', { exact: true })).toBeVisible();
  await expect(page.locator('.score-ring strong')).not.toHaveText('—');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'How is your stream feeling today?' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await login(page, accounts.find(account => account.role === 'reviewer'));
  await page.getByRole('button', { name: 'Inspect report', exact: true }).first().click();
  await page.getByLabel('Review reason', { exact: true }).fill('Synthetic integration fixture reviewed independently.');
  await page.getByRole('button', { name: 'Approve report', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Download FHIR', exact: true })).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download FHIR', exact: true }).click();
  const download = await downloadPromise;
  expect(JSON.parse(readFileSync(await download.path(), 'utf8')).resourceType).toBe('Bundle');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Toggle navigation', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
