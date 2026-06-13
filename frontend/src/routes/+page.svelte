<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { cachedFetch, cacheClear, cacheTimestamp, formatCacheAge } from '$lib/utils/signalsCache';
  import type { WatchlistEntry, SignalScanRow, PortfolioEntry } from '$lib/types';

  const CACHE_KEY = 'page_dashboard';

  let watchlist: WatchlistEntry[] = [];
  let portfolioEntries: PortfolioEntry[] = [];
  let recentSignals: SignalScanRow[] = [];
  let topDividends: any[] = [];
  let loading = true;
  let refreshing = false;
  let error: string | null = null;
  let noSnapshot = false;
  let cacheTs: number | null = null;

  let syncing = false;
  let syncResult: { ok: boolean; msg: string } | null = null;

  async function handleSync() {
    syncing = true;
    syncResult = null;
    try {
      const res = await api<any>('/data/cloud-sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pull: true, rescan_after_sync: true }),
      });
      const files = res.copied_count ?? 0;
      const scanRows = res.rescan?.rows ?? '?';
      syncResult = { ok: true, msg: `已同步 ${files} 個檔案，重算 ${scanRows} 筆訊號` };
      cacheClear(CACHE_KEY);
      await loadData(true);
    } catch (e) {
      syncResult = { ok: false, msg: e instanceof Error ? e.message : '同步失敗' };
    } finally {
      syncing = false;
    }
  }

  async function loadOptional<T>(path: string, fallback: T): Promise<T> {
    try {
      return (await api<T>(path)) ?? fallback;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes('404') || /No snapshot/i.test(msg)) {
        noSnapshot = true;
        return fallback;
      }
      throw e;
    }
  }

  async function loadData(forceRefresh = false) {
    if (forceRefresh) refreshing = true; else loading = true;
    error = null;
    try {
      const { data, ts } = await cachedFetch(CACHE_KEY, async () => {
        const [wl, pf] = await Promise.all([
          api<WatchlistEntry[]>('/watchlist'),
          loadOptional<PortfolioEntry[]>('/portfolio?open_only=true', []),
        ]);
        const signalsResp = await loadOptional<{ data: SignalScanRow[] }>('/scan/signals', { data: [] });
        const top = (await loadOptional<any[]>('/scan/dividend?order_by=est_yield&desc=true&limit=5', [])).slice(0, 5);
        return {
          watchlist: wl,
          portfolioEntries: pf,
          recentSignals: [...(signalsResp.data || [])].sort((a, b) => b.score - a.score).slice(0, 5),
          topDividends: top,
        };
      }, forceRefresh);
      watchlist = data.watchlist;
      portfolioEntries = data.portfolioEntries;
      recentSignals = data.recentSignals;
      topDividends = data.topDividends;
      cacheTs = ts;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load data';
      console.error(error);
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function handleRefresh() {
    cacheClear(CACHE_KEY);
    await loadData(true);
  }

  onMount(() => loadData());

  $: totalOpenLots = portfolioEntries.reduce((s, e) => s + e.lots.length, 0);
  $: totalPnl = portfolioEntries.reduce(
    (s, e) => s + (e.total_unrealized_pnl ?? 0),
    0,
  );
</script>

<div class="dashboard">
  <div class="title-row">
    <h1>Dashboard</h1>
    <div class="header-actions">
      {#if cacheTs}<span class="cache-age">上次更新：{formatCacheAge(cacheTs)}</span>{/if}
      <button class="btn-refresh" disabled={refreshing || loading} on:click={handleRefresh}>
        <span class:spinning={refreshing}>↻</span> 更新
      </button>
      <button class="btn-sync" disabled={syncing} on:click={handleSync}>
        <span class:spinning={syncing}>⬇</span> {syncing ? '同步中...' : '雲端同步'}
      </button>
    </div>
  </div>

  {#if syncResult}
    <div class="sync-banner" class:sync-ok={syncResult.ok} class:sync-err={!syncResult.ok}>
      {syncResult.ok ? '✅' : '❌'} {syncResult.msg}
    </div>
  {/if}

  {#if error}
    <div class="error-banner">{error}</div>
  {:else if noSnapshot}
    <div class="info-banner">
      尚無快照，請至資料管理執行掃描或等待 daily_pipeline 排程。
    </div>
  {/if}

  <div class="cards-grid">
    <!-- 持倉狀態（Portfolio） -->
    <div class="card">
      <h2>持倉狀態 <span class="count-badge">{totalOpenLots}</span></h2>
      <div class="card-content">
        {#if portfolioEntries.length === 0}
          <p class="empty">尚無持倉。請至 <a href="/portfolio">持倉管理</a> 新增買入記錄。</p>
        {:else}
          <div class="watchlist-list">
            {#each portfolioEntries.slice(0, 4) as entry}
              <div class="watchlist-item">
                <span class="wl-code">{entry.code}</span>
                <span class="wl-name">{entry.name || '—'}</span>
                {#if entry.total_unrealized_pnl !== null}
                  <span class="wl-pnl" class:pos={entry.total_unrealized_pnl >= 0}
                    class:neg={entry.total_unrealized_pnl < 0}>
                    {entry.total_unrealized_pnl >= 0 ? '+' : ''}{entry.total_unrealized_pnl.toLocaleString()}
                  </span>
                {:else}
                  <span class="wl-price">¥{entry.total_cost.toLocaleString()}</span>
                {/if}
              </div>
            {/each}
          </div>
          {#if totalOpenLots > 0}
            <div class="pnl-summary" class:pos={totalPnl >= 0} class:neg={totalPnl < 0}>
              總未實現損益 {totalPnl >= 0 ? '+' : ''}¥{totalPnl.toLocaleString()}
            </div>
          {/if}
        {/if}
      </div>
      <a href="/portfolio" class="link">管理持倉</a>
    </div>

    <!-- 追蹤清單（Watchlist） -->
    <div class="card">
      <h2>追蹤清單 <span class="count-badge">{watchlist.length}</span></h2>
      <div class="card-content">
        {#if watchlist.length === 0}
          <p class="empty">追蹤清單為空。請至 <a href="/watchlist">追蹤清單</a> 新增關注股票。</p>
        {:else}
          <div class="watchlist-list">
            {#each watchlist.slice(0, 5) as entry}
              <div class="watchlist-item">
                <span class="wl-code">{entry.code}</span>
                <span class="wl-name">{entry.name || '—'}</span>
                <span class="wl-price">¥{entry.start_price.toLocaleString()}</span>
              </div>
            {/each}
            {#if watchlist.length > 5}
              <p class="more-hint">…還有 {watchlist.length - 5} 檔</p>
            {/if}
          </div>
        {/if}
      </div>
      <a href="/signals" class="link">查看訊號</a>
    </div>

    <!-- 今日訊號 -->
    <div class="card">
      <h2>今日訊號</h2>
      <div class="card-content">
        {#if recentSignals.length > 0}
          <div class="signal-list">
            {#each recentSignals.slice(0, 3) as signal}
              <div class="signal-item">
                <span class="code">{signal.code}</span>
                <span class="score" class:positive={signal.score > 0}>+{signal.score}</span>
              </div>
            {/each}
          </div>
        {:else}
          <p class="empty">暫無訊號</p>
        {/if}
      </div>
      <a href="/signals" class="link">查看全部</a>
    </div>

    <!-- 金雞 Top -->
    <div class="card">
      <h2>金雞 Top</h2>
      <div class="card-content">
        {#if topDividends.length > 0}
          <div class="dividend-list">
            {#each topDividends.slice(0, 3) as div}
              <div class="dividend-item">
                <span class="code">{div.code}</span>
                <span class="yield">{((div.est_yield || 0) * 100).toFixed(2)}%</span>
              </div>
            {/each}
          </div>
        {:else}
          <p class="empty">暫無資料</p>
        {/if}
      </div>
      <a href="/dividend" class="link">查看全部</a>
    </div>
  </div>
</div>

<style>
  .dashboard {
    max-width: 1200px;
    margin: 0 auto;
  }

  h1 {
    font-size: 28px;
    margin: 0 0 30px 0;
    color: #4ade80;
  }

  .error-banner {
    background-color: #7f1d1d;
    border: 1px solid #991b1b;
    color: #fecaca;
    padding: 12px 16px;
    border-radius: 4px;
    margin-bottom: 20px;
  }

  .info-banner {
    background-color: #1e293b;
    border: 1px solid #334155;
    color: #cbd5e1;
    padding: 12px 16px;
    border-radius: 4px;
    margin-bottom: 20px;
    font-size: 14px;
  }

  .info-banner code {
    background-color: #0f172a;
    padding: 2px 6px;
    border-radius: 3px;
    color: #93c5fd;
  }

  .title-row {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;
  }
  .header-actions { display: flex; align-items: center; gap: 12px; }
  .cache-age { font-size: 12px; color: #666; }
  .btn-refresh {
    background: #1a1a1a; border: 1px solid #444; color: #ccc;
    padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px;
    display: inline-flex; align-items: center; gap: 6px;
  }
  .btn-refresh:hover:not(:disabled) { color: #4ade80; border-color: #4ade80; }
  .btn-refresh:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-sync {
    background: #052e16; border: 1px solid #4ade80; color: #4ade80;
    padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px;
    display: inline-flex; align-items: center; gap: 6px; font-weight: 600;
  }
  .btn-sync:hover:not(:disabled) { background: #14532d; }
  .btn-sync:disabled { opacity: 0.5; cursor: not-allowed; }
  .sync-banner {
    padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 14px;
  }
  .sync-ok { background: #052e16; border: 1px solid #4ade80; color: #86efac; }
  .sync-err { background: #7f1d1d; border: 1px solid #991b1b; color: #fecaca; }
  .spinning { animation: spin 0.7s linear infinite; display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
  }

  .card {
    background-color: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 20px;
    transition: border-color 0.3s ease;
  }

  .card:hover {
    border-color: #4ade80;
  }

  .card h2 {
    margin: 0 0 15px 0;
    font-size: 18px;
    color: #e5e7eb;
  }

  .card-content {
    margin-bottom: 15px;
    min-height: 80px;
  }

  .stat {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #333;
  }

  .stat:last-child {
    border-bottom: none;
  }

  .label {
    color: #a1a1a1;
    font-size: 14px;
  }

  .value {
    color: #4ade80;
    font-weight: bold;
    font-size: 16px;
  }

  .signal-list,
  .dividend-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .signal-item,
  .dividend-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
  }

  .code {
    font-weight: 600;
    color: #e5e7eb;
  }

  .score {
    color: #f87171;
    font-size: 14px;
    font-weight: 500;
  }

  .score.positive {
    color: #4ade80;
  }

  .yield {
    color: #fbbf24;
    font-weight: 600;
  }

  .empty {
    color: #6b7280;
    text-align: center;
    padding: 20px;
    margin: 0;
  }

  .empty a {
    color: #4ade80;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .empty a:hover {
    color: #86efac;
  }

  .count-badge {
    display: inline-block;
    background: #374151;
    color: #9ca3af;
    font-size: 12px;
    font-weight: normal;
    padding: 2px 7px;
    border-radius: 10px;
    margin-left: 6px;
    vertical-align: middle;
  }

  .watchlist-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .watchlist-item {
    display: grid;
    grid-template-columns: 52px 1fr auto;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    border-bottom: 1px solid #222;
    font-size: 13px;
  }

  .watchlist-item:last-of-type {
    border-bottom: none;
  }

  .wl-code {
    font-weight: bold;
    color: #fff;
  }

  .wl-name {
    color: #a1a1a1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .wl-price {
    color: #4ade80;
    font-weight: 600;
    white-space: nowrap;
  }

  .more-hint {
    color: #555;
    font-size: 12px;
    text-align: right;
    margin: 4px 0 0 0;
  }

  .wl-pnl {
    font-weight: 600;
    white-space: nowrap;
  }

  .wl-pnl.pos { color: #4ade80; }
  .wl-pnl.neg { color: #f87171; }

  .pnl-summary {
    margin-top: 8px;
    font-size: 13px;
    font-weight: 600;
    text-align: right;
  }

  .pnl-summary.pos { color: #4ade80; }
  .pnl-summary.neg { color: #f87171; }

  .link {
    display: inline-block;
    color: #4ade80;
    text-decoration: none;
    font-size: 14px;
    padding: 8px 0;
    border-bottom: 1px solid transparent;
    transition: border-color 0.3s ease;
  }

  .link:hover {
    border-bottom-color: #4ade80;
  }
</style>
