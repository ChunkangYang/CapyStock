<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import type { SignalResult, WatchlistEntry, SignalScanRow } from '$lib/types';

  let watchlist: WatchlistEntry[] = [];
  let recentSignals: SignalScanRow[] = [];
  let topDividends: any[] = [];
  let loading = true;
  let error: string | null = null;
  let noSnapshot = false;

  // 僅在「真的失敗」時把錯誤丟出；snapshot 尚未產生（404）視為空狀態。
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

  onMount(async () => {
    try {
      watchlist = await api<WatchlistEntry[]>('/watchlist');

      const signals = await loadOptional<SignalScanRow[]>('/scan/signals', []);
      recentSignals = [...signals]
        .sort((a, b) => b.score - a.score)
        .slice(0, 5);

      topDividends = await loadOptional<any[]>(
        '/scan/dividend?order_by=est_yield&desc=true',
        [],
      );
      topDividends = topDividends.slice(0, 5);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load data';
      console.error(error);
    } finally {
      loading = false;
    }
  });
</script>

<div class="dashboard">
  <h1>Dashboard</h1>

  {#if error}
    <div class="error-banner">{error}</div>
  {:else if noSnapshot}
    <div class="info-banner">
      尚未產生掃描快照。請先執行 <code>POST /api/v1/scan/run</code>（kind=signals / dividend）或等待 daily_pipeline 排程跑完。
    </div>
  {/if}

  <div class="cards-grid">
    <!-- Watchlist Card -->
    <div class="card">
      <h2>持倉狀態</h2>
      <div class="card-content">
        <div class="stat">
          <span class="label">追蹤數</span>
          <span class="value">{watchlist.length}</span>
        </div>
        <div class="stat">
          <span class="label">最近警告</span>
          <span class="value">—</span>
        </div>
      </div>
      <a href="/signals" class="link">查看詳情</a>
    </div>

    <!-- Today's Signals Card -->
    <div class="card">
      <h2>今日訊號</h2>
      <div class="card-content">
        {#if recentSignals.length > 0}
          <div class="signal-list">
            {#each recentSignals.slice(0, 3) as signal}
              <div class="signal-item">
                <span class="code">{signal.code}</span>
                <span class="score" class:positive={signal.score > 0}>
                  +{signal.score}
                </span>
              </div>
            {/each}
          </div>
        {:else}
          <p class="empty">暫無訊號</p>
        {/if}
      </div>
      <a href="/signals" class="link">查看全部</a>
    </div>

    <!-- Top Dividends Card -->
    <div class="card">
      <h2>金雞 Top</h2>
      <div class="card-content">
        {#if topDividends.length > 0}
          <div class="dividend-list">
            {#each topDividends.slice(0, 3) as div}
              <div class="dividend-item">
                <span class="code">{div.code}</span>
                <span class="yield">
                  {((div.est_yield || 0) * 100).toFixed(2)}%
                </span>
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
    font-size: 32px;
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
