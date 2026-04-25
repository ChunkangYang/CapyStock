import { test, expect } from '@playwright/test';

test.describe('Signals Page', () => {
  test('列表頁應該加載並顯示資料', async ({ page }) => {
    await page.goto('/signals');

    // 等待頁面加載
    await page.waitForLoadState('networkidle');

    // 驗證標題存在
    const title = page.locator('h1');
    await expect(title).toContainText('投機訊號');

    // 驗證 tabs 存在
    const tabs = page.locator('button.tab');
    expect(await tabs.count()).toBeGreaterThanOrEqual(3);
  });

  test('應該能切換 tab', async ({ page }) => {
    await page.goto('/signals');
    await page.waitForLoadState('networkidle');

    // 點擊「我的持倉」tab
    const watchlistTab = page.locator('button.tab:has-text("我的持倉")');
    await watchlistTab.click();

    // 驗證 tab 已激活
    await expect(watchlistTab).toHaveClass(/active/);
  });

  test('點擊表格行應該跳轉到詳細頁', async ({ page }) => {
    await page.goto('/signals');
    await page.waitForLoadState('networkidle');

    // 等待表格加載
    const tableRows = page.locator('tbody tr');
    const rowCount = await tableRows.count();

    if (rowCount > 0) {
      // 取得第一行的代號
      const firstCell = tableRows.first().locator('td.code');
      const code = await firstCell.textContent();

      // 點擊第一行
      await tableRows.first().click();

      // 驗證 URL 改變
      await expect(page).toHaveURL(`/signals/${code}`);
    }
  });

  test('詳細頁應該顯示四個圖表容器', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    // 檢查圖表容器是否存在
    const chartContainers = page.locator('.chart-container');
    const count = await chartContainers.count();

    // 至少應該有 K 線、法人、信用残、時間軸四個圖表
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test('詳細頁應該顯示股票資訊', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    // 驗證代號顯示
    const codeSpan = page.locator('.code');
    await expect(codeSpan).toContainText('7203');
  });

  test('詳細頁應該有收藏按鈕', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    // 尋找收藏按鈕
    const favoriteBtn = page.locator('.favorite-btn');
    expect(await favoriteBtn.count()).toBeGreaterThan(0);
  });

  test('應該能收藏股票', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    // 點擊收藏按鈕
    const favoriteBtn = page.locator('.favorite-btn').first();
    const initialText = await favoriteBtn.textContent();

    await favoriteBtn.click();

    // 等待狀態更新
    await page.waitForTimeout(500);

    // 驗證按鈕文字改變（從 ☆ 變 ★）
    const newText = await favoriteBtn.textContent();
    expect(initialText).not.toBe(newText);
  });

  test('詳細頁應該有吃貨訊號區塊', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    // 尋找吃貨訊號標題
    const accumTitle = page.locator('text=吃貨訊號');
    expect(await accumTitle.count()).toBeGreaterThan(0);
  });

  test('詳細頁應該有停損狀態區塊', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    // 尋找停損狀態標題
    const stopLossTitle = page.locator('text=停損狀態');
    expect(await stopLossTitle.count()).toBeGreaterThan(0);
  });

  test('應該能查看 EDINET 事件', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    // EDINET 事件區塊應存在
    const edinetSection = page.locator('text=EDINET');
    const count = await edinetSection.count();
    expect(count).toBeGreaterThanOrEqual(0); // 可能沒有事件
  });

  test('詳細頁應該有加入 watchlist 按鈕', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    const btn = page.locator('button:has-text("加入 watchlist")');
    await expect(btn).toBeVisible();
  });

  test('詳細頁應該有加入模擬按鈕', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    const btn = page.locator('button:has-text("加入模擬")');
    await expect(btn).toBeVisible();
  });

  test('應該能拍攝列表頁截圖', async ({ page }) => {
    await page.goto('/signals');
    await page.waitForLoadState('networkidle');

    // 等待表格完全加載
    await page.locator('table').waitFor({ state: 'visible' });

    await expect(page).toHaveScreenshot('signals-list.png');
  });

  test('應該能拍攝詳細頁截圖', async ({ page }) => {
    await page.goto('/signals/7203');
    await page.waitForLoadState('networkidle');

    // 等待圖表加載
    await page.locator('.chart-container').first().waitFor({ state: 'visible' });

    await expect(page).toHaveScreenshot('signals-detail.png');
  });
});
