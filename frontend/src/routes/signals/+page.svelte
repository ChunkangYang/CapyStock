<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, ApiError } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
  import { cacheGet, cacheSet, cacheClear, cacheTimestamp, clearAllSignalsCache, formatCacheAge } from '$lib/utils/signalsCache';
  import type { SignalScanRow, SignalResult } from '$lib/types';

  const TABS = ['market', 'watchlist', 'favorites'] as const;
  type Tab = (typeof TABS)[number];

  let activeTab: Tab = 'market';
  let data: SignalScanRow[] = [];
  let loading = true;
  let refreshingAll = false;
  let refreshingCodes = new Set<string>();
  let error = '';
  let noSnapshot = false;
  let cacheTs: number | null = null;

  let _loadSeq = 0;

  function listCacheKey(tab: Tab) {
    return `signals_list:${tab}`;
  }

  onMount(async () => {
    await loadData();
  });

  async function loadData(forceRefresh = false) {
    const seq = ++_loadSeq;
    loading = true;
    error = '';
    noSnapshot = false;

    const key = listCacheKey(activeTab);

    if (!forceRefresh) {
      const cached = cacheGet<SignalScanRow[]>(key);
      if (cached) {
        if (seq !== _loadSeq) return;
        data = cached;
        cacheTs = cacheTimestamp(key);
        loading = false;
        return;
      }
    } else {
      cacheClear(key);
    }

    try {
      let result: SignalScanRow[] = [];

      if (activeTab === 'market') {
        result = await api('/scan/signals');
      } else if (activeTab === 'watchlist') {
        const watchlistSignals: SignalResult[] = await api('/signals');
        result = watchlistSignals.map(r => toScanRow(r));
      } else if (activeTab === 'favorites') {
        const favorites = await api('/favorites?tag=speculative');
        const results: SignalResult[] = await Promise.all(
          favorites.map((f: { code: string }) => api(`/signals/${f.code}`))
        );
        result = results.map(r => toScanRow(r));
      }

      if (seq !== _loadSeq) return;
      cacheSet(key, result);
      cacheTs = cacheTimestamp(key);
      data = result;
    } catch (e) {
      if (seq !== _loadSeq) return;
      if (e instanceof ApiError && e.status === 404 && activeTab === 'market') {
        noSnapshot = true;
      } else {
        error = e instanceof Error ? e.message : '讀取資料失敗';
      }
    } finally {
      if (seq === _loadSeq) loading = false;
    }
  }

  async function refreshAll() {
    refreshingAll = true;
    clearAllSignalsCache();
    await loadData(true);
    refreshingAll = false;
  }

  async function refreshRow(code: string) {
    refreshingCodes = new Set([...refreshingCodes, code]);
    // 清除個股快取（detail 頁面會重新抓）
    cacheClear(`signals_detail:${code}`);
    try {
      const result: SignalResult = await api(`/signals/${code}`);
      const updated = toScanRow(result);
      data = data.map(row => row.code === code ? updated : row);
      // 更新 list 快取
      cacheSet(listCacheKey(activeTab), data);
      cacheTs = cacheTimestamp(listCacheKey(activeTab));
    } catch {}
    refreshingCodes = new Set([...refreshingCodes].filter(c => c !== code));
  }

  function toScanRow(r: SignalResult): SignalScanRow {
    return {
      code: r.code,
      name: r.name,
      latest_price: r.latest_price ?? 0,
      has_accumulation: r.accumulation_signal,
      has_exit: (r.alerts ?? []).some(a => a.alert_type === 'exit'),
      has_stop_loss: r.stop_loss_triggered,
      edinet_recent_count: 0,
      score: r.technical_score ?? 0,
      generated_at: new Date().toISOString(),
    };
  }

  function handleTabChange(tab: Tab) {
    if (tab === activeTab) return;
    activeTab = tab;
    loadData();
  }

  function handleTabKeydown(e: KeyboardEvent, idx: number) {
    let next = idx;
    if (e.key === 'ArrowRight') next = (idx + 1) % TABS.length;
    else if (e.key === 'ArrowLeft') next = (idx - 1 + TABS.length) % TABS.length;
    else return;
    e.preventDefault();
    handleTabChange(TABS[next]);
    const tabEls = document.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    tabEls[next]?.focus();
  }

  function handleRowClick(code: string) {
    goto(`/signals/${code}`);
  }

  const TAB_LABELS: Record<Tab, string> = {
    market: '全市場訊號',
    watchlist: '我的持倉',
    favorites: '我的最愛',
  };
</script>

<div class="signals-page">
  <div class="header">
    <div class="title-row">
      <h1>投機訊號</h1>
      <div class="header-actions">
        {#if cacheTs !== null}
          <span class="cache-age">上次更新：{formatCacheAge(cacheTs)}</span>
        {/if}
        <button
          class="btn-refresh"
          class:spinning={refreshingAll}
          disabled={refreshingAll || loading}
          title="清除快取，重新抓取全部資料"
          on:click={refreshAll}
        >
          ↻ 全部更新
        </button>
      </div>
    </div>
    <div class="tabs" role="tablist" aria-label="訊號分類">
      {#each TABS as tab, i}
        <button
          role="tab"
          class="tab"
          class:active={activeTab === tab}
          aria-selected={activeTab === tab}
          tabindex={activeTab === tab ? 0 : -1}
          on:click={() => handleTabChange(tab)}
          on:keydown={e => handleTabKeydown(e, i)}
        >
          {TAB_LABELS[tab]}
        </button>
      {/each}
    </div>
  </div>

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <p class="error">{error}</p>
  {:else if noSnapshot}
    <div class="empty-state">
      <p>尚無投機訊號掃描快照。請至 <a href="/data">資料管理</a> 或執行掃描排程後再回來。</p>
    </div>
  {:else}
    <DataTable
      {data}
      onRowClick={handleRowClick}
      onRefreshRow={refreshRow}
      {refreshingCodes}
    />
  {/if}
</div>

<style>
  .signals-page {
    padding: 24px;
  }

  .header {
    margin-bottom: 24px;
  }

  .title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .signals-page h1 {
    color: #4ade80;
    margin: 0;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .cache-age {
    font-size: 12px;
    color: #666;
  }

  .btn-refresh {
    background: #1a1a1a;
    border: 1px solid #444;
    color: #ccc;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: color 0.2s, border-color 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .btn-refresh:hover:not(:disabled) {
    color: #4ade80;
    border-color: #4ade80;
  }

  .btn-refresh:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-refresh.spinning {
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .tabs {
    display: flex;
    gap: 8px;
    border-bottom: 1px solid #333;
  }

  .tab {
    background: none;
    border: none;
    padding: 8px 16px;
    color: #a1a1a1;
    cursor: pointer;
    font-size: 14px;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
  }

  .tab:hover {
    color: #fff;
  }

  .tab:focus-visible {
    outline: 2px solid #4ade80;
    outline-offset: 2px;
    border-radius: 2px;
  }

  .tab.active {
    color: #4ade80;
    border-bottom-color: #4ade80;
  }

  .error {
    color: #f87171;
    text-align: center;
    padding: 24px;
  }

  .empty-state {
    text-align: center;
    color: #aaa;
    padding: 60px 20px;
    background: #1d1d1d;
    border: 1px dashed #333;
    border-radius: 8px;
  }

  .empty-state a {
    color: #4ade80;
  }
</style>
