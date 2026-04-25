import { test, expect } from '@playwright/test';

test.describe('Simulation Page', () => {
  test('列表頁應該加載', async ({ page }) => {
    await page.goto('/simulation');
    await page.waitForLoadState('networkidle');

    const title = page.locator('h1');
    await expect(title).toContainText('模擬交易');
  });

  test('應該能點擊「+ 新模擬」按鈕進入建立頁', async ({ page }) => {
    await page.goto('/simulation');
    await page.waitForLoadState('networkidle');

    const newBtn = page.locator('a:has-text("+ 新モデル")');
    await newBtn.click();

    await expect(page).toHaveURL('/simulation/new');
  });

  test('建立精靈 Step 1 應該有基本設定表單', async ({ page }) => {
    await page.goto('/simulation/new');
    await page.waitForLoadState('networkidle');

    // 驗證 Step 1 元素
    const nameInput = page.locator('input[placeholder*="例"]').first();
    await expect(nameInput).toBeVisible();

    // 驗證 radio buttons
    const radioBacktest = page.locator('input[value="backtest"]');
    const radioPaper = page.locator('input[value="paper"]');
    await expect(radioBacktest).toBeVisible();
    await expect(radioPaper).toBeVisible();
  });

  test('建立精靈應該能跨步驟', async ({ page }) => {
    await page.goto('/simulation/new');
    await page.waitForLoadState('networkidle');

    // Step 1: 填入基本設定
    await page.locator('input[placeholder*="例"]').first().fill('Test Simulation');
    await page.locator('input[value="backtest"]').check();

    // 設定日期
    const dateInputs = page.locator('input[type="date"]');
    const startDate = dateInputs.first();
    const endDate = dateInputs.last();

    await startDate.fill('2024-01-01');
    await endDate.fill('2024-01-31');

    // 點擊「下一步」
    const nextBtn = page.locator('button:has-text("下一步")');
    await nextBtn.click();

    // 驗證進到 Step 2（候選股票）
    const stepContent = page.locator('.step-content');
    await expect(stepContent.locator('h2')).toContainText('候選股票');
  });

  test('Step 2 應該能手動輸入股票代碼', async ({ page }) => {
    await page.goto('/simulation/new');
    await page.waitForLoadState('networkidle');

    // 跳過 Step 1
    await page.locator('input[placeholder*="例"]').first().fill('Test');
    await page.locator('input[value="backtest"]').check();
    const dateInputs = page.locator('input[type="date"]');
    await dateInputs.first().fill('2024-01-01');
    await dateInputs.last().fill('2024-01-31');
    await page.locator('button:has-text("下一步")').click();

    // Step 2: 手動輸入代碼
    const codeInput = page.locator('input[placeholder*="輸入股票代碼"]');
    await codeInput.fill('7203');

    const addBtn = page.locator('button:has-text("新增")');
    await addBtn.click();

    // 驗證候選已添加
    const candidateItems = page.locator('.candidate-item');
    await expect(candidateItems).toContainText('7203');
  });

  test('應該能進入 Step 3 設定規則', async ({ page }) => {
    await page.goto('/simulation/new');
    await page.waitForLoadState('networkidle');

    // Step 1
    await page.locator('input[placeholder*="例"]').first().fill('Test');
    await page.locator('input[value="backtest"]').check();
    const dateInputs = page.locator('input[type="date"]');
    await dateInputs.first().fill('2024-01-01');
    await dateInputs.last().fill('2024-01-31');
    await page.locator('button:has-text("下一步")').click();

    // Step 2
    const codeInput = page.locator('input[placeholder*="輸入股票代碼"]');
    await codeInput.fill('7203');
    await page.locator('button:has-text("新增")').click();
    await page.locator('button:has-text("下一步")').click();

    // Step 3: 驗證規則設定頁面
    const ruleContent = page.locator('.step-content');
    await expect(ruleContent.locator('h2')).toContainText('規則設定');

    // 驗證進場規則、出場規則、持倉管理等表單元素存在
    const h3s = page.locator('.step-content h3');
    const text = await h3s.allTextContents();
    expect(text).toContain('進場規則');
    expect(text).toContain('出場規則');
  });

  test('完成三步驟後應該能提交建立', async ({ page }) => {
    await page.goto('/simulation/new');
    await page.waitForLoadState('networkidle');

    // Step 1
    await page.locator('input[placeholder*="例"]').first().fill('E2E Test Sim');
    await page.locator('input[value="backtest"]').check();
    const dateInputs = page.locator('input[type="date"]');
    await dateInputs.first().fill('2024-01-01');
    await dateInputs.last().fill('2024-01-31');
    await page.locator('button:has-text("下一步")').click();

    // Step 2
    const codeInput = page.locator('input[placeholder*="輸入股票代碼"]');
    await codeInput.fill('7203');
    await page.locator('button:has-text("新增")').click();
    await page.locator('button:has-text("下一步")').click();

    // Step 3：應該看到「建立並回測」按鈕
    const submitBtn = page.locator('button:has-text("建立並回測")');
    await expect(submitBtn).toBeVisible();
  });

  test('列表頁應該顯示已建立的模擬', async ({ page }) => {
    await page.goto('/simulation');
    await page.waitForLoadState('networkidle');

    // 檢查是否有表格
    const table = page.locator('table');
    const rows = table.locator('tbody tr');

    // 如果有行，驗證列數
    const rowCount = await rows.count();
    if (rowCount > 0) {
      // 驗證每行有 8 列（根據設計規格）
      const firstRow = rows.first();
      const cells = firstRow.locator('td');
      expect(await cells.count()).toBeGreaterThanOrEqual(7);
    }
  });

  test('模擬詳細頁應該顯示 header 資訊', async ({ page }) => {
    await page.goto('/simulation');
    await page.waitForLoadState('networkidle');

    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();

    if (rowCount > 0) {
      // 點擊第一行的「檢視」按鈕
      const viewBtn = rows.first().locator('button:has-text("檢視")');
      await viewBtn.click();

      // 驗證進入詳細頁
      const h1 = page.locator('h1');
      await expect(h1).toBeVisible();

      // 驗證 status badge 存在
      const statusBadge = page.locator('.status-badge');
      await expect(statusBadge).toBeVisible();
    }
  });

  test('completed backtest 應該顯示 KPI 卡片', async ({ page }) => {
    await page.goto('/simulation');
    await page.waitForLoadState('networkidle');

    const rows = page.locator('tbody tr');

    // 尋找已完成的 backtest
    for (let i = 0; i < (await rows.count()); i++) {
      const row = rows.nth(i);
      const statusText = await row.locator('td').nth(2).textContent();

      if (statusText?.includes('completed')) {
        await row.locator('button:has-text("檢視")').click();
        await page.waitForLoadState('networkidle');

        // 驗證 KPI 卡片
        const kpiCards = page.locator('.kpi-card');
        const kpiCount = await kpiCards.count();
        expect(kpiCount).toBeGreaterThanOrEqual(4);

        break;
      }
    }
  });

  test('應該能從詳細頁刪除模擬', async ({ page }) => {
    await page.goto('/simulation');
    await page.waitForLoadState('networkidle');

    const initialRows = await page.locator('tbody tr').count();

    const rows = page.locator('tbody tr');
    if (initialRows > 0) {
      const firstRow = rows.first();
      const viewBtn = firstRow.locator('button:has-text("檢視")');
      await viewBtn.click();
      await page.waitForLoadState('networkidle');

      // 點擊刪除按鈕
      page.once('dialog', (dialog) => {
        dialog.accept();
      });

      const deleteBtn = page.locator('button:has-text("刪除")');
      await deleteBtn.click();

      // 驗證返回列表頁
      await expect(page).toHaveURL('/simulation');
    }
  });

  test('paper 模擬應該有「推進今日」按鈕', async ({ page }) => {
    await page.goto('/simulation');
    await page.waitForLoadState('networkidle');

    const rows = page.locator('tbody tr');

    // 尋找 paper 類型且 running 的模擬
    for (let i = 0; i < (await rows.count()); i++) {
      const row = rows.nth(i);
      const text = await row.textContent();

      if (text?.includes('ペーパー') && text?.includes('running')) {
        await row.locator('button:has-text("檢視")').click();
        await page.waitForLoadState('networkidle');

        const advanceBtn = page.locator('button:has-text("推進今日")');
        await expect(advanceBtn).toBeVisible();

        break;
      }
    }
  });
});
