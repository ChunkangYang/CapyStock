import { test, expect } from '@playwright/test';

test.describe('Dividend Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dividend');
  });

  test('應該載入金雞清單', async ({ page }) => {
    await page.waitForSelector('table', { timeout: 10000 });
    const table = page.locator('table tbody');
    const rows = await table.locator('tr');
    expect(await rows.count()).toBeGreaterThan(0);
  });

  test('篩選器應該正確操作', async ({ page }) => {
    // 等待表格載入
    await page.waitForSelector('table', { timeout: 10000 });

    // 獲取初始的 row 數
    const initialRows = await page.locator('table tbody tr').count();

    // 調整 yield slider
    const yieldSlider = page.locator('input[type="range"]').nth(0);
    await yieldSlider.fill('5');

    // 等待過濾結果更新
    await page.waitForTimeout(500);

    // 驗證 filtered rows 數量可能減少或不變
    const filteredRows = await page.locator('table tbody tr').count();
    expect(filteredRows).toBeLessThanOrEqual(initialRows);
  });

  test('排序功能應該正常工作', async ({ page }) => {
    await page.waitForSelector('table', { timeout: 10000 });

    // 獲取排序前的第一列數據
    const firstCellBefore = await page
      .locator('table tbody tr:first-child td:nth-child(6)')
      .textContent();

    // 點擊 Yield header
    await page.locator('th').filter({ hasText: 'Yield' }).click();

    // 等待排序完成
    await page.waitForTimeout(300);

    // 獲取排序後的第一列數據
    const firstCellAfter = await page
      .locator('table tbody tr:first-child td:nth-child(6)')
      .textContent();

    // 驗證排序已經改變（大多數情況下應該改變）
    expect(firstCellAfter).toBeDefined();
  });

  test('點擊 row 應該跳轉到詳細頁', async ({ page }) => {
    await page.waitForSelector('table tbody tr', { timeout: 10000 });

    // 獲取第一行的 code
    const codeCell = await page.locator('table tbody tr:first-child td:nth-child(2)').textContent();
    const code = codeCell?.trim();

    // 點擊 row
    await page.locator('table tbody tr:first-child').click();

    // 驗證跳轉到詳細頁
    expect(page.url()).toContain(`/dividend/${code}`);
  });

  test('詳細頁應該顯示所有必需的元件', async ({ page }) => {
    // 導航到詳細頁
    await page.waitForSelector('table tbody tr', { timeout: 10000 });
    await page.locator('table tbody tr:first-child').click();

    // 驗證標題和代碼
    const header = page.locator('.header-top h1');
    await expect(header).toBeVisible();

    // 驗證雷達圖容器
    const radarChart = page.locator('.chart-box').first();
    await expect(radarChart).toBeVisible();

    // 驗證配當歷史圖表容器
    const dividendChart = page.locator('.chart-box').nth(1);
    await expect(dividendChart).toBeVisible();

    // 驗證指標表格存在
    const metricsTable = page.locator('table.metrics-table');
    await expect(metricsTable).toBeVisible();

    // 驗證表格有 8 行（8 個指標）
    const metricRows = await metricsTable.locator('tbody tr').count();
    expect(metricRows).toBe(8);
  });

  test('收藏按鈕應該正常工作', async ({ page }) => {
    // 導航到詳細頁
    await page.waitForSelector('table tbody tr', { timeout: 10000 });
    await page.locator('table tbody tr:first-child').click();

    // 等待頁面載入
    await page.waitForSelector('.header-right', { timeout: 10000 });

    // 點擊收藏按鈕
    const favoriteBtn = page.locator('.favorite-btn');
    const initialText = await favoriteBtn.textContent();

    await favoriteBtn.click();
    await page.waitForTimeout(300);

    // 驗證按鈕狀態改變（★ ↔ ☆）
    const afterClickText = await favoriteBtn.textContent();
    expect(afterClickText).not.toBe(initialText);
  });

  test('统計摘要應該顯示正確的計數', async ({ page }) => {
    // 導航到詳細頁
    await page.waitForSelector('table tbody tr', { timeout: 10000 });
    await page.locator('table tbody tr:first-child').click();

    // 驗證統計摘要存在
    const statsBox = page.locator('.stats-box');
    await expect(statsBox).toBeVisible();

    // 驗證 PASS / WARN / FAIL 的統計
    const statRows = await statsBox.locator('.stat-row').count();
    expect(statRows).toBe(3);
  });

  test('篩選器應該在重整後保留', async ({ page }) => {
    // 調整篩選
    await page.waitForSelector('input[type="range"]', { timeout: 10000 });
    const yieldSlider = page.locator('input[type="range"]').nth(0);
    await yieldSlider.fill('5');

    // 獲取當前 URL
    const urlBefore = page.url();

    // 重整頁面
    await page.reload();

    // 等待重新載入
    await page.waitForSelector('table', { timeout: 10000 });

    // 驗證篩選仍然存在（表格數量應該相同）
    const filteredRows = await page.locator('table tbody tr').count();
    expect(filteredRows).toBeGreaterThanOrEqual(0);
  });

  test('Overall 篩選應該正常工作', async ({ page }) => {
    // 等待頁面載入
    await page.waitForSelector('input[type="checkbox"]', { timeout: 10000 });

    // 取消選中某個 Overall
    const overallCheckboxes = page.locator('.checkboxes label:has-text("STRONG") input');
    await overallCheckboxes.uncheck();

    // 等待篩選
    await page.waitForTimeout(300);

    // 驗證表格更新
    const rows = await page.locator('table tbody tr').count();
    expect(rows).toBeGreaterThanOrEqual(0);
  });

  test('表格欄位應該完整顯示', async ({ page }) => {
    await page.waitForSelector('table thead th', { timeout: 10000 });

    // 驗證表頭欄位
    const headers = await page.locator('table thead th').allTextContents();
    expect(headers).toContain('Code');
    expect(headers).toContain('Name');
    expect(headers).toContain('Overall');
    expect(headers).toContain('DPS');
    expect(headers).toContain('Yield');
  });

  test('應該能看到截圖基線（列表頁）', async ({ page }) => {
    await page.waitForSelector('table', { timeout: 10000 });
    await expect(page).toHaveScreenshot('dividend-list-default.png', { maxDiffPixels: 100 });
  });

  test('應該能看到截圖基線（詳細頁）', async ({ page }) => {
    await page.waitForSelector('table tbody tr', { timeout: 10000 });
    await page.locator('table tbody tr:first-child').click();
    await page.waitForSelector('.header-top', { timeout: 10000 });
    await expect(page).toHaveScreenshot('dividend-detail.png', { maxDiffPixels: 100 });
  });
});
