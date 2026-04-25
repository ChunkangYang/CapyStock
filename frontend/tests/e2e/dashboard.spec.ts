import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('should load dashboard with navigation links', async ({ page }) => {
    await page.goto('/');

    // Check logo
    await expect(page.getByText('CapyStock')).toBeVisible();

    // Check nav links exist
    await expect(page.getByRole('link', { name: /Dashboard/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /投機訊號/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /金雞高股息/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /我的最愛/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /模擬交易/ })).toBeVisible();

    // Check main content
    await expect(page.getByRole('heading', { name: /Dashboard/ })).toBeVisible();
  });

  test('should navigate to signals page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /投機訊號/ }).click();
    await expect(page).toHaveURL('/signals');
    await expect(page.getByRole('heading', { name: /投機訊號/ })).toBeVisible();
  });

  test('should navigate to dividend page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /金雞高股息/ }).click();
    await expect(page).toHaveURL('/dividend');
    await expect(
      page.getByRole('heading', { name: /金雞高股息/ }),
    ).toBeVisible();
  });

  test('should navigate to favorites page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /我的最愛/ }).click();
    await expect(page).toHaveURL('/favorites');
    await expect(page.getByRole('heading', { name: /我的最愛/ })).toBeVisible();
  });

  test('should navigate to simulation page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /模擬交易/ }).click();
    await expect(page).toHaveURL('/simulation');
    await expect(
      page.getByRole('heading', { name: /模擬交易/ }),
    ).toBeVisible();
  });

  test('should have dashboard cards on home', async ({ page }) => {
    await page.goto('/');

    // Check for card headings
    await expect(page.getByRole('heading', { name: /持倉狀態/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /今日訊號/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /金雞 Top/ })).toBeVisible();
  });

  test('should take screenshot of dashboard', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveScreenshot('dashboard-default.png');
  });
});
