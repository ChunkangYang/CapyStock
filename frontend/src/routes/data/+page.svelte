<script lang="ts">
  import { onMount } from 'svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  const API = '/api/v1';

  interface OverviewRow {
    code: string;
    name: string;
    price_age_days: number | null;
    margin_age_days: number | null;
    flow_age_days: number | null;
    fundamental_age_days: number | null;
  }

  let rows: OverviewRow[] = [];
  let loading = true;
  let error = '';
  let jpxLoading = false;
  let jpxMsg = '';
  let universeLoading = false;
  let universeMsg = '';
  let scanLoading = false;
  let scanMsg = '';
  let scanJobId = '';
  let scanProgress = 0;
  let scanProgressTotal = 0;

  onMount(async () => {
    // 檢查是否有進行中的掃描（localStorage 恢復）
    try {
      const savedScanState = localStorage.getItem('scan_state');
      if (savedScanState) {
        const state = JSON.parse(savedScanState);
        if (state.jobId && state.isRunning) {
          scanJobId = state.jobId;
          scanLoading = true;
          scanProgress = state.progress || 0;
          scanProgressTotal = state.progressTotal || 3747;
          // 恢復輪詢
          resumeScanPolling(state.jobId);
        }
      }
    } catch {
      localStorage.removeItem('scan_state');
    }

    // 載入資料
    try {
      const res = await fetch(`${API}/data/overview`);
      if (!res.ok) throw new Error(res.statusText);
      rows = await res.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  function resumeScanPolling(jobId: string) {
    let pollCount = 0;
    const pollInterval = setInterval(async () => {
      pollCount++;
      try {
        const statusRes = await fetch(`${API}/scan/jobs/${jobId}`);
        if (!statusRes.ok) {
          throw new Error(`查詢失敗 (${statusRes.status})`);
        }

        const status = await statusRes.json();
        scanProgress = status.progress_current || 0;
        scanProgressTotal = status.progress_total || 3747;

        // 保存狀態到 localStorage
        localStorage.setItem('scan_state', JSON.stringify({
          jobId,
          isRunning: status.status === 'running',
          progress: scanProgress,
          progressTotal: scanProgressTotal,
        }));

        if (status.status === 'completed') {
          clearInterval(pollInterval);
          localStorage.removeItem('scan_state');
          try {
            localStorage.removeItem('signals_list:market');
          } catch {}
          scanLoading = false;
          scanMsg = `✓ 掃描完成！已檢查 ${scanProgressTotal} 檔股票。進入「投機訊號」查看結果`;
        } else if (status.status === 'failed') {
          clearInterval(pollInterval);
          localStorage.removeItem('scan_state');
          scanLoading = false;
          scanMsg = `✗ 掃描失敗：${status.message || '未知錯誤。請檢查伺服器'}`;
        }
      } catch (e: any) {
        // 輪詢超過 3 分鐘還沒完成，停止輪詢
        if (pollCount > 90) {
          clearInterval(pollInterval);
          localStorage.removeItem('scan_state');
          scanLoading = false;
          scanMsg = `⚠️ 掃描逾時。請到「投機訊號」檢查是否有結果。如果沒有，請重試`;
        }
      }
    }, 2000);
  }

  function ageCellClass(days: number | null): string {
    if (days === null) return 'age-none';
    if (days > 30) return 'age-old';
    if (days > 7) return 'age-mid';
    return 'age-new';
  }

  function ageLabel(days: number | null): string {
    if (days === null) return '—';
    return `${days}d`;
  }

  async function updateJpxFlow() {
    jpxLoading = true;
    jpxMsg = '';
    try {
      const res = await fetch(`${API}/ingest/jpx-weekly`, { method: 'POST' });
      const body = await res.json();
      if (body.ok) {
        jpxMsg = `✓ 已更新市場 Flow（${body.rows_fetched} 週）`;
      } else {
        jpxMsg = `✗ ${body.error || '失敗'}`;
      }
    } catch (e: any) {
      jpxMsg = `✗ ${e.message}`;
    } finally {
      jpxLoading = false;
    }
  }

  async function updateUniverse() {
    universeLoading = true;
    universeMsg = '';
    try {
      const res = await fetch(`${API}/ingest/update-universe`, { method: 'POST' });
      const body = await res.json();
      if (body.ok) {
        universeMsg = `✓ 已更新股票清單（Prime ${body.prime} + Standard ${body.standard} + Growth ${body.growth} = ${body.total} 檔）`;
      } else {
        universeMsg = `✗ ${body.error || '失敗'}`;
      }
    } catch (e: any) {
      universeMsg = `✗ ${e.message}`;
    } finally {
      universeLoading = false;
    }
  }

  async function scanNow() {
    scanLoading = true;
    scanMsg = '';
    scanJobId = '';
    scanProgress = 0;
    scanProgressTotal = 0;

    try {
      // 觸發背景掃描
      const res = await fetch(`${API}/scan/run?async_mode=true`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'signals' })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const body = await res.json();
      scanJobId = body.job_id;
      scanProgressTotal = body.progress_total || 3747;

      // 保存掃描狀態到 localStorage（用於頁面切換時恢復）
      localStorage.setItem('scan_state', JSON.stringify({
        jobId: scanJobId,
        isRunning: true,
        progress: 0,
        progressTotal: scanProgressTotal,
      }));

      // 開始輪詢
      resumeScanPolling(scanJobId);

    } catch (e: any) {
      scanLoading = false;
      scanMsg = `✗ 無法啟動掃描：${e.message}`;
    }
  }
</script>

<div class="data-page">
  <div class="page-header">
    <h1>資料管理</h1>
    <div class="actions">
      <button class="btn-primary" on:click={scanNow} disabled={scanLoading} title="掃描全部股票，耗時 5-10 分鐘">
        {#if scanLoading}
          掃描中 ({scanProgress}/{scanProgressTotal})
        {:else}
          ⚡ 立即掃描全市場
        {/if}
      </button>
      <button class="btn-ghost" on:click={updateUniverse} disabled={universeLoading}>
        {universeLoading ? '更新中…' : '↻ 股票清單'}
      </button>
      <button class="btn-ghost" on:click={updateJpxFlow} disabled={jpxLoading}>
        {jpxLoading ? '更新中…' : '↻ 市場 Flow'}
      </button>
      <a href="/data/ingest" class="btn-secondary">批量抓取</a>
      <a href="/data/upload" class="btn-secondary">上傳資料</a>
    </div>
  </div>
  {#if scanLoading && scanProgressTotal > 0}
    <div class="progress-bar">
      <div class="progress-fill" style="width: {(scanProgress / scanProgressTotal) * 100}%"></div>
      <div class="progress-text">{scanProgress} / {scanProgressTotal}</div>
    </div>
  {/if}
  {#if scanMsg}
    <div class="scan-msg" class:ok={scanMsg.startsWith('✓')} class:err={scanMsg.startsWith('✗')}>
      {scanMsg}
    </div>
  {/if}
  {#if universeMsg}
    <div class="universe-msg" class:ok={universeMsg.startsWith('✓')} class:err={universeMsg.startsWith('✗')}>
      {universeMsg}
    </div>
  {/if}
  {#if jpxMsg}
    <div class="jpx-msg" class:ok={jpxMsg.startsWith('✓')} class:err={jpxMsg.startsWith('✗')}>
      {jpxMsg}
    </div>
  {/if}

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <div class="error-banner">{error}</div>
  {:else}
    <div class="legend">
      <span class="legend-item"><span class="dot dot-new"></span>最新（≤7日）</span>
      <span class="legend-item"><span class="dot dot-mid"></span>偏舊（7-30日）</span>
      <span class="legend-item"><span class="dot dot-old"></span>過舊（>30日）</span>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>代碼</th>
            <th>名稱</th>
            <th class="center">股價</th>
            <th class="center">信用残</th>
            <th class="center">投資部門別</th>
            <th class="center">基本面</th>
            <th class="center">操作</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row}
            <tr>
              <td class="code">{row.code}</td>
              <td class="name">{row.name}</td>
              <td class="center {ageCellClass(row.price_age_days)}">{ageLabel(row.price_age_days)}</td>
              <td class="center {ageCellClass(row.margin_age_days)}">{ageLabel(row.margin_age_days)}</td>
              <td class="center {ageCellClass(row.flow_age_days)}">{ageLabel(row.flow_age_days)}</td>
              <td class="center {ageCellClass(row.fundamental_age_days)}">{ageLabel(row.fundamental_age_days)}</td>
              <td class="center ops">
                <a href="/data/ingest?code={row.code}" class="op-link blue">重抓</a>
                <a href="/data/upload?code={row.code}" class="op-link green">上傳</a>
              </td>
            </tr>
          {/each}
          {#if rows.length === 0}
            <tr><td colspan="7" class="empty">追蹤清單為空</td></tr>
          {/if}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .data-page {
    max-width: 900px;
    margin: 0 auto;
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
  }

  h1 {
    font-size: 28px;
    color: #4ade80;
    margin: 0;
  }

  .actions {
    display: flex;
    gap: 10px;
  }

  .btn-primary {
    background: #4ade80;
    color: #0f0f0f;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 14px;
    text-decoration: none;
    cursor: pointer;
  }

  .btn-primary:hover {
    background: #22c55e;
  }

  .btn-secondary {
    background: transparent;
    color: #4ade80;
    border: 1px solid #4ade80;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 14px;
    text-decoration: none;
    cursor: pointer;
  }

  .btn-secondary:hover {
    background: #052e16;
  }

  .btn-ghost {
    background: transparent;
    color: #a1a1a1;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 8px 14px;
    font-size: 14px;
    cursor: pointer;
  }
  .btn-ghost:hover:not(:disabled) { color: #e5e7eb; border-color: #555; }
  .btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }

  .progress-bar {
    position: relative;
    height: 24px;
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 4px;
    margin-bottom: 16px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #4ade80, #22c55e);
    transition: width 0.3s ease;
  }

  .progress-text {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    z-index: 1;
  }

  .scan-msg, .universe-msg, .jpx-msg {
    font-size: 13px;
    padding: 8px 12px;
    border-radius: 4px;
    margin-bottom: 12px;
  }
  .scan-msg.ok, .universe-msg.ok, .jpx-msg.ok { background: #064e3b; color: #d1fae5; border: 1px solid #4ade80; }
  .scan-msg.err, .universe-msg.err, .jpx-msg.err { background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; }

  .error-banner {
    background: #1f1a1a;
    border: 1px solid #7f1d1d;
    color: #f87171;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 14px;
  }

  .legend {
    display: flex;
    gap: 20px;
    margin-bottom: 16px;
    font-size: 13px;
    color: #a1a1a1;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    display: inline-block;
  }

  .dot-new  { background: #166534; }
  .dot-mid  { background: #854d0e; }
  .dot-old  { background: #7f1d1d; }

  .table-wrap {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    overflow: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }

  .data-table th {
    text-align: left;
    padding: 10px 14px;
    color: #6b7280;
    border-bottom: 1px solid #333;
    font-weight: 500;
    white-space: nowrap;
  }

  .data-table td {
    padding: 10px 14px;
    border-bottom: 1px solid #222;
    color: #e5e7eb;
  }

  .data-table tr:last-child td {
    border-bottom: none;
  }

  .data-table tbody tr:hover td {
    background: #222;
  }

  .center { text-align: center; }

  .code {
    font-family: monospace;
    font-weight: 700;
    color: #fff;
  }

  .name { color: #a1a1a1; }

  .empty {
    text-align: center;
    padding: 40px;
    color: #6b7280;
  }

  /* age badge colours — 用 td. 提高 specificity 蓋過 .data-table td */
  .data-table td.age-new  { color: #4ade80; }
  .data-table td.age-mid  { color: #facc15; }
  .data-table td.age-old  { color: #f87171; font-weight: 600; }
  .data-table td.age-none { color: #4b5563; }

  .ops { white-space: nowrap; }

  .op-link {
    font-size: 12px;
    text-decoration: none;
    margin: 0 4px;
  }

  .op-link.blue  { color: #4ade80; }
  .op-link.blue:hover  { color: #86efac; }
  .op-link.green { color: #4ade80; }
  .op-link.green:hover { color: #86efac; }
</style>
