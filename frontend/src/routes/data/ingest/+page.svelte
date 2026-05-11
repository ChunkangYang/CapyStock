<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';

  const API = '/api/v1';

  interface WatchlistEntry { code: string; name: string; }
  interface PriceEntry { code: string; close: number | null; }

  // 全市場股票列表
  let allStocks: WatchlistEntry[] = [];
  let prices: Record<string, number | null> = {};
  let checkedCodes = new Set<string>();

  // 額外手填代碼
  let extraInput = '';

  // 資料種類
  let selectedKinds: string[] = ['margin'];
  const kindOptions = [
    { value: 'margin', label: '信用残' },
    { value: 'flow',   label: '投資部門別' },
  ];
  const kindLabel: Record<string, string> = { margin: '信用残', flow: '投資部門別' };

  // 抓取狀態
  let running = false;
  let jobId = '';
  let progress = 0;
  let total = 0;
  let results: any[] = [];
  let error = '';

  // 加入追蹤提示
  let watchlistPrompt: string[] = [];
  let watchlistAdding = false;
  let watchlistMsg = '';
  let watchlistDismissed = false;

  // 從 query param 預設 code，或預設全選市場股票
  onMount(async () => {
    const code = $page.url.searchParams.get('code');
    try {
      // 從資料管理頁讀全市場股票列表（同樣的 API）
      const r = await fetch(`${API}/data/overview`);
      if (r.ok) {
        allStocks = await r.json();
        if (code) {
          checkedCodes = new Set([code.toUpperCase()]);
        } else {
          // 預設全選整個市場
          checkedCodes = new Set(allStocks.map(s => s.code));
        }
        // 並行載入各股最新價格（靜默失敗）
        const priceResults = await Promise.allSettled(
          allStocks.map(s => fetch(`${API}/data/latest-price/${s.code}`).then(r => r.ok ? r.json() : null))
        );
        for (let i = 0; i < allStocks.length; i++) {
          const res = priceResults[i];
          prices[allStocks[i].code] = res.status === 'fulfilled' && res.value ? res.value.close : null;
        }
        prices = { ...prices };
      }
    } catch { /* ignore */ }
    if (code && !allStocks.find(s => s.code === code.toUpperCase())) {
      extraInput = code;
    }
  });

  function toggleCode(code: string) {
    const next = new Set(checkedCodes);
    next.has(code) ? next.delete(code) : next.add(code);
    checkedCodes = next;
  }

  function selectAll() { checkedCodes = new Set(allStocks.map(s => s.code)); }
  function selectNone() { checkedCodes = new Set(); }

  function toggleKind(kind: string) {
    selectedKinds = selectedKinds.includes(kind)
      ? selectedKinds.filter(k => k !== kind)
      : [...selectedKinds, kind];
  }

  $: allChecked = allStocks.length > 0 && checkedCodes.size === allStocks.length;
  $: someChecked = checkedCodes.size > 0 && checkedCodes.size < allStocks.length;

  $: allCodes = [
    ...checkedCodes,
    ...extraInput.split(/[\s,]+/).filter(c => c && !checkedCodes.has(c.toUpperCase())).map(c => c.toUpperCase()),
  ];

  async function startIngest() {
    if (!allCodes.length || !selectedKinds.length) {
      error = '請至少選一支股票和一種資料種類';
      return;
    }
    error = '';
    results = [];
    watchlistPrompt = [];
    watchlistMsg = '';
    watchlistDismissed = false;
    running = true;
    progress = 0;

    const res = await fetch(`${API}/data/batch-ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codes: allCodes, kinds: selectedKinds }),
    });
    if (!res.ok) {
      error = (await res.json()).detail || res.statusText;
      running = false;
      return;
    }
    const info = await res.json();
    jobId = info.job_id;
    total = info.total;

    const evtSource = new EventSource(`${API}/data/batch-ingest/${jobId}/stream`);
    evtSource.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      progress = data.done;
      total = data.total;
      if (data.status === 'completed') {
        evtSource.close();
        fetchResults();
        running = false;
      }
    };
    evtSource.onerror = () => {
      evtSource.close();
      running = false;
      fetchResults();
    };
  }

  async function fetchResults() {
    if (!jobId) return;
    const r = await fetch(`${API}/data/batch-ingest/${jobId}`);
    if (r.ok) {
      const job = await r.json();
      results = job.results || [];
      await checkWatchlistPrompt();
    }
  }

  async function checkWatchlistPrompt() {
    const successCodes = [...new Set(results.filter(r => r.ok).map(r => r.code))];
    if (!successCodes.length) return;
    try {
      const wlRes = await fetch(`${API}/watchlist`);
      if (wlRes.ok) {
        const wl: WatchlistEntry[] = await wlRes.json();
        const existing = new Set(wl.map(w => w.code));
        watchlistPrompt = successCodes.filter(c => !existing.has(c));
      }
    } catch { watchlistPrompt = successCodes; }
    watchlistDismissed = false;
    watchlistMsg = '';
  }

  async function getLatestPrice(code: string): Promise<number> {
    try {
      const r = await fetch(`${API}/data/latest-price/${code}`);
      if (r.ok) return (await r.json()).close ?? 0;
    } catch { /* fallback */ }
    return 0;
  }

  async function addToWatchlist() {
    watchlistAdding = true;
    let added = 0;
    for (const code of watchlistPrompt) {
      try {
        const start_price = await getLatestPrice(code);
        const r = await fetch(`${API}/watchlist`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, start_price }),
        });
        if (r.ok) added++;
      } catch { /* skip */ }
    }
    watchlistMsg = `✓ 已將 ${added} 支股票加入追蹤清單`;
    watchlistAdding = false;
    watchlistPrompt = [];
  }
</script>

<div class="page">
  <div class="page-header">
    <a href="/data" class="back-link">← 資料管理</a>
    <h1>批量抓取</h1>
  </div>

  <div class="card">
    <!-- 全市場股票選擇 -->
    <div class="field">
      <label>全市場股票（{checkedCodes.size} / {allStocks.length} 已選）</label>
      {#if allStocks.length === 0}
        <p class="empty-hint">載入中…</p>
      {:else}
        <table class="wl-table">
          <thead>
            <tr>
              <th class="col-check">
                <input type="checkbox"
                  checked={allChecked}
                  on:change={() => allChecked ? selectNone() : selectAll()}
                />
              </th>
              <th>代號</th>
              <th>名稱</th>
              <th class="col-price">現在價格</th>
            </tr>
          </thead>
          <tbody>
            {#each allStocks as s}
              <tr class:row-checked={checkedCodes.has(s.code)} on:click={() => toggleCode(s.code)}>
                <td class="col-check" on:click|stopPropagation>
                  <input type="checkbox"
                    checked={checkedCodes.has(s.code)}
                    on:change={() => toggleCode(s.code)}
                  />
                </td>
                <td class="col-code">{s.code}</td>
                <td class="col-name">{s.name || '—'}</td>
                <td class="col-price">
                  {#if prices[s.code] != null}
                    ¥{Number(prices[s.code]).toLocaleString()}
                  {:else}
                    <span class="no-price">—</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>

    <!-- 額外代碼 -->
    <div class="field">
      <label>額外代碼（不在追蹤清單，逗號或空白分隔）</label>
      <input class="inp" bind:value={extraInput} placeholder="e.g. 6367, 8035" />
    </div>

    <!-- 資料種類 -->
    <div class="field">
      <label>資料種類</label>
      <div class="checkbox-group">
        {#each kindOptions as opt}
          <label class="checkbox-label">
            <input type="checkbox" checked={selectedKinds.includes(opt.value)} on:change={() => toggleKind(opt.value)} />
            <span>{opt.label}</span>
          </label>
        {/each}
      </div>
    </div>

    <div class="run-row">
      <button class="btn-primary" on:click={startIngest} disabled={running || allCodes.length === 0}>
        {running ? '抓取中…' : `執行（${allCodes.length} 檔 × ${selectedKinds.length} 種類）`}
      </button>
    </div>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if running || total > 0}
    <div class="progress-block">
      <div class="progress-meta">
        <span>進度</span>
        <span>{progress} / {total}</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width: {total > 0 ? (progress / total * 100) : 0}%"></div>
      </div>
    </div>
  {/if}

  {#if watchlistPrompt.length > 0 && !watchlistDismissed}
    <div class="watchlist-prompt">
      <div class="wl-body">
        <span class="wl-icon">★</span>
        <div>
          <p class="wl-title">加入追蹤清單？</p>
          <p class="wl-codes">以下股票抓取成功：<strong>{watchlistPrompt.join('、')}</strong></p>
        </div>
      </div>
      <div class="wl-actions">
        <button class="btn-primary" on:click={addToWatchlist} disabled={watchlistAdding}>
          {watchlistAdding ? '加入中…' : '加入追蹤清單'}
        </button>
        <button class="btn-dismiss" on:click={() => (watchlistDismissed = true)}>略過</button>
      </div>
    </div>
  {/if}

  {#if watchlistMsg}
    <div class="watchlist-done">{watchlistMsg}</div>
  {/if}

  {#if results.length > 0}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>代碼</th><th>種類</th><th>來源</th>
            <th class="right">筆數</th><th class="center">狀態</th><th>錯誤</th>
          </tr>
        </thead>
        <tbody>
          {#each results as r}
            <tr>
              <td class="code">{r.code}</td>
              <td>{kindLabel[r.kind] ?? r.kind}</td>
              <td class="muted">{r.source}</td>
              <td class="right">{r.rows}</td>
              <td class="center">
                {#if r.ok}<span class="ok">✓</span>{:else}<span class="fail-icon">✗</span>{/if}
              </td>
              <td class="fail">{r.error || ''}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .page { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
  .page-header { display: flex; align-items: baseline; gap: 16px; }
  .back-link { color: #4ade80; text-decoration: none; font-size: 13px; }
  .back-link:hover { text-decoration: underline; }
  h1 { color: #4ade80; font-size: 28px; margin: 0; }

  .card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
  .field { display: flex; flex-direction: column; gap: 8px; }

  label { color: #a1a1a1; font-size: 13px; }

  .empty-hint { color: #4b5563; font-size: 13px; margin: 0; }

  .wl-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .wl-table thead tr { border-bottom: 1px solid #333; }
  .wl-table th { padding: 7px 12px; color: #6b7280; font-weight: 500; text-align: left; }
  .wl-table td { padding: 8px 12px; border-bottom: 1px solid #1e1e1e; color: #e5e7eb; }
  .wl-table tbody tr { cursor: pointer; transition: background 0.1s; }
  .wl-table tbody tr:hover { background: #222; }
  .wl-table tbody tr.row-checked { background: #0a2216; }
  .wl-table tbody tr.row-checked:hover { background: #0d2e1c; }
  .wl-table tr:last-child td { border-bottom: none; }
  .col-check { width: 36px; text-align: center; }
  .col-check input { accent-color: #4ade80; cursor: pointer; }
  .col-code { font-family: monospace; font-weight: 700; color: #4ade80; width: 70px; }
  .col-name { color: #a1a1a1; }
  .col-price { text-align: right; width: 110px; font-variant-numeric: tabular-nums; }
  .no-price { color: #4b5563; }

  .inp { background: #0f0f0f; border: 1px solid #333; border-radius: 4px; color: #e5e7eb; padding: 8px 12px; font-size: 14px; }
  .inp:focus { outline: none; border-color: #4ade80; }

  .checkbox-group { display: flex; gap: 20px; }
  .checkbox-label { display: flex; align-items: center; gap: 8px; cursor: pointer; color: #e5e7eb; font-size: 14px; }
  .checkbox-label input { accent-color: #4ade80; }

  .run-row { display: flex; }
  .btn-primary { background: #4ade80; color: #0f0f0f; border: none; border-radius: 4px; padding: 8px 20px; font-size: 14px; font-weight: 600; cursor: pointer; }
  .btn-primary:hover { background: #22c55e; }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

  .error-banner { background: #7f1d1d; border: 1px solid #ef4444; color: #fca5a5; border-radius: 6px; padding: 10px 14px; font-size: 13px; }

  .progress-block { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 16px; }
  .progress-meta { display: flex; justify-content: space-between; font-size: 13px; color: #a1a1a1; margin-bottom: 8px; }
  .progress-track { height: 6px; background: #2a2a2a; border-radius: 3px; overflow: hidden; }
  .progress-fill { height: 100%; background: #4ade80; border-radius: 3px; transition: width 0.3s ease; }

  .table-wrap { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; overflow: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 10px 14px; color: #6b7280; border-bottom: 1px solid #333; font-weight: 500; white-space: nowrap; }
  td { padding: 10px 14px; border-bottom: 1px solid #222; color: #e5e7eb; }
  tr:last-child td { border-bottom: none; }
  tbody tr:hover td { background: #222; }
  .code { font-family: monospace; font-weight: 700; }
  .muted { color: #6b7280; font-size: 12px; }
  .right { text-align: right; }
  .center { text-align: center; }
  .ok { color: #4ade80; font-weight: 700; }
  .fail-icon { color: #f87171; font-weight: 700; }
  .fail { color: #f87171; font-size: 12px; }

  .watchlist-prompt { background: #0a2a1a; border: 1px solid #4ade80; border-radius: 8px; padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
  .wl-body { display: flex; align-items: flex-start; gap: 12px; }
  .wl-icon { color: #4ade80; font-size: 20px; line-height: 1.4; flex-shrink: 0; }
  .wl-title { color: #4ade80; font-size: 14px; font-weight: 600; margin: 0 0 4px 0; }
  .wl-codes { color: #a1a1a1; font-size: 13px; margin: 0; }
  .wl-codes strong { color: #e5e7eb; }
  .wl-actions { display: flex; gap: 10px; flex-shrink: 0; }
  .btn-dismiss { background: transparent; color: #6b7280; border: 1px solid #3a3a3a; border-radius: 4px; padding: 7px 14px; font-size: 13px; cursor: pointer; }
  .btn-dismiss:hover { color: #a1a1a1; border-color: #555; }
  .watchlist-done { background: #064e3b; border: 1px solid #4ade80; color: #d1fae5; border-radius: 6px; padding: 10px 14px; font-size: 13px; }
</style>
