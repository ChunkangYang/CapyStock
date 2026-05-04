<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, ApiError } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  import type { SignalScanRow, SignalResult } from '$lib/types';

  const TABS = ['market', 'watchlist', 'favorites'] as const;
  type Tab = (typeof TABS)[number];

  let activeTab: Tab = 'market';
  let data: SignalScanRow[] = [];
  let loading = true;
  let error = '';
  let noSnapshot = false;

  // race condition guard：每次 loadData 產生新 id，async 完成後只有最新 id 才更新 state
  let _loadSeq = 0;

  onMount(async () => {
    await loadData();
  });

  async function loadData() {
    const seq = ++_loadSeq;
    loading = true;
    error = '';
    noSnapshot = false;

    try {
      let result: SignalScanRow[] = [];

      if (activeTab === 'market') {
        result = await api('/scan/signals');
      } else if (activeTab === 'watchlist') {
        // 批次呼叫 /signals（analyze_watchlist），避免 N+1
        const watchlistSignals: SignalResult[] = await api('/signals');
        result = watchlistSignals.map(r => toScanRow(r));
      } else if (activeTab === 'favorites') {
        const favorites = await api('/favorites?tag=speculative');
        const results: SignalResult[] = await Promise.all(
          favorites.map((f: { code: string }) => api(`/signals/${f.code}`))
        );
        result = results.map(r => toScanRow(r));
      }

      if (seq !== _loadSeq) return; // stale — discard
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
    // move focus to newly-active tab
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
    <h1>投機訊號</h1>
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
    <p class="loading">加載中...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if noSnapshot}
    <div class="empty-state">
      <p>尚無投機訊號掃描快照。請至 <a href="/data">資料管理</a> 或執行掃描排程後再回來。</p>
    </div>
  {:else}
    <DataTable {data} onRowClick={handleRowClick} />
  {/if}
</div>

<style>
  .signals-page {
    padding: 24px;
  }

  .header {
    margin-bottom: 24px;
  }

  .signals-page h1 {
    color: #4ade80;
    margin: 0 0 16px 0;
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

  .loading,
  .error {
    color: #a1a1a1;
    text-align: center;
    padding: 24px;
  }

  .error {
    color: #f87171;
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
