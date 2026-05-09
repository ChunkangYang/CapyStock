<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';

  const API = '/api/v1';

  let selectedCodes = '';
  let selectedKinds: string[] = ['margin'];
  let running = false;
  let jobId = '';
  let progress = 0;
  let total = 0;
  let status = '';
  let results: any[] = [];
  let error = '';

  // 追蹤清單提示
  let watchlistPrompt: string[] = [];   // 成功且不在清單的代碼
  let watchlistAdding = false;
  let watchlistMsg = '';
  let watchlistDismissed = false;

  const kindOptions = [
    { value: 'margin', label: '信用残' },
    { value: 'flow', label: '投資部門別' },
  ];

  const kindLabel: Record<string, string> = {
    margin: '信用残',
    flow: '投資部門別',
  };

  onMount(() => {
    const code = $page.url.searchParams.get('code');
    if (code) selectedCodes = code;
  });

  function toggleKind(kind: string) {
    if (selectedKinds.includes(kind)) {
      selectedKinds = selectedKinds.filter(k => k !== kind);
    } else {
      selectedKinds = [...selectedKinds, kind];
    }
  }

  async function startIngest() {
    error = '';
    results = [];
    const codes = selectedCodes.split(/[\s,]+/).filter(Boolean);
    if (!codes.length || !selectedKinds.length) {
      error = '請選擇代碼和資料種類';
      return;
    }

    running = true;
    progress = 0;

    const res = await fetch(`${API}/data/batch-ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codes, kinds: selectedKinds }),
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
      status = data.status;
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
    const res = await fetch(`${API}/data/batch-ingest/${jobId}`);
    if (res.ok) {
      const job = await res.json();
      results = job.results || [];
      await checkWatchlistPrompt();
    }
  }

  async function checkWatchlistPrompt() {
    // 收集成功的唯一代碼
    const successCodes = [...new Set(results.filter(r => r.ok).map(r => r.code))];
    if (!successCodes.length) return;
    // 查現有追蹤清單，過濾掉已在清單的
    try {
      const wlRes = await fetch(`${API}/watchlist`);
      if (wlRes.ok) {
        const wl: { code: string }[] = await wlRes.json();
        const existing = new Set(wl.map(w => w.code));
        watchlistPrompt = successCodes.filter(c => !existing.has(c));
      }
    } catch {
      watchlistPrompt = successCodes;
    }
    watchlistDismissed = false;
    watchlistMsg = '';
  }

  async function addToWatchlist() {
    watchlistAdding = true;
    let added = 0;
    for (const code of watchlistPrompt) {
      try {
        const r = await fetch(`${API}/watchlist`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, start_price: 0 }),
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
    <div class="field">
      <label>股票代碼（逗號或空白分隔）</label>
      <input
        bind:value={selectedCodes}
        class="inp"
        placeholder="7203, 9984, 6758"
      />
    </div>

    <div class="field">
      <label>資料種類</label>
      <div class="checkbox-group">
        {#each kindOptions as opt}
          <label class="checkbox-label">
            <input
              type="checkbox"
              checked={selectedKinds.includes(opt.value)}
              on:change={() => toggleKind(opt.value)}
            />
            <span>{opt.label}</span>
          </label>
        {/each}
      </div>
    </div>

    <button class="btn-primary" on:click={startIngest} disabled={running}>
      {running ? '抓取中…' : '執行'}
    </button>
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
      <div class="wl-prompt-body">
        <span class="wl-icon">★</span>
        <div>
          <p class="wl-title">加入追蹤清單？</p>
          <p class="wl-codes">以下股票抓取成功：<strong>{watchlistPrompt.join('、')}</strong></p>
        </div>
      </div>
      <div class="wl-prompt-actions">
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
            <th>代碼</th>
            <th>種類</th>
            <th>來源</th>
            <th class="right">筆數</th>
            <th class="center">狀態</th>
            <th>錯誤</th>
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
                {#if r.ok}
                  <span class="ok">✓</span>
                {:else}
                  <span class="fail">✗</span>
                {/if}
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

  .back-link {
    color: #4ade80;
    text-decoration: none;
    font-size: 13px;
  }
  .back-link:hover { text-decoration: underline; }

  h1 { color: #4ade80; font-size: 28px; margin: 0; }

  .card {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .field { display: flex; flex-direction: column; gap: 6px; }

  label { color: #a1a1a1; font-size: 13px; }

  .inp {
    background: #0f0f0f;
    border: 1px solid #333;
    border-radius: 4px;
    color: #e5e7eb;
    padding: 8px 12px;
    font-size: 14px;
    max-width: 400px;
  }
  .inp:focus { outline: none; border-color: #4ade80; }

  .checkbox-group { display: flex; gap: 20px; }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    color: #e5e7eb;
    font-size: 14px;
  }
  .checkbox-label input { accent-color: #4ade80; }

  .btn-primary {
    background: #4ade80;
    color: #0f0f0f;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    align-self: flex-start;
  }
  .btn-primary:hover { background: #22c55e; }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

  .error-banner {
    background: #7f1d1d;
    border: 1px solid #ef4444;
    color: #fca5a5;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 13px;
  }

  .progress-block {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 16px;
  }
  .progress-meta {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    color: #a1a1a1;
    margin-bottom: 8px;
  }
  .progress-track {
    height: 6px;
    background: #2a2a2a;
    border-radius: 3px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: #4ade80;
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  .table-wrap {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    overflow: auto;
  }

  table { width: 100%; border-collapse: collapse; font-size: 13px; }

  th {
    text-align: left;
    padding: 10px 14px;
    color: #6b7280;
    border-bottom: 1px solid #333;
    font-weight: 500;
    white-space: nowrap;
  }

  td {
    padding: 10px 14px;
    border-bottom: 1px solid #222;
    color: #e5e7eb;
  }

  tr:last-child td { border-bottom: none; }
  tbody tr:hover td { background: #222; }

  .code { font-family: monospace; font-weight: 700; }
  .muted { color: #6b7280; font-size: 12px; }
  .right { text-align: right; }
  .center { text-align: center; }
  .ok { color: #4ade80; font-weight: 700; }
  .fail { color: #f87171; font-size: 12px; }

  .watchlist-prompt {
    background: #0a2a1a;
    border: 1px solid #4ade80;
    border-radius: 8px;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
  }
  .wl-prompt-body { display: flex; align-items: flex-start; gap: 12px; }
  .wl-icon { color: #4ade80; font-size: 20px; line-height: 1.4; flex-shrink: 0; }
  .wl-title { color: #4ade80; font-size: 14px; font-weight: 600; margin: 0 0 4px 0; }
  .wl-codes { color: #a1a1a1; font-size: 13px; margin: 0; }
  .wl-codes strong { color: #e5e7eb; }
  .wl-prompt-actions { display: flex; gap: 10px; flex-shrink: 0; }
  .btn-dismiss {
    background: transparent;
    color: #6b7280;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 7px 14px;
    font-size: 13px;
    cursor: pointer;
  }
  .btn-dismiss:hover { color: #a1a1a1; border-color: #555; }

  .watchlist-done {
    background: #064e3b;
    border: 1px solid #4ade80;
    color: #d1fae5;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 13px;
  }
</style>
