<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  import type { SignalScanRow, SignalResult } from '$lib/types';

  let activeTab: 'market' | 'watchlist' | 'favorites' = 'market';
  let data: SignalScanRow[] = [];
  let loading = true;
  let error = '';

  onMount(async () => {
    await loadData();
  });

  async function loadData() {
    loading = true;
    error = '';
    data = [];

    try {
      if (activeTab === 'market') {
        data = await api('/scan/signals');
      } else if (activeTab === 'watchlist') {
        const watchlist = await api('/watchlist');
        const results = await Promise.all(
          watchlist.map(w => api(`/signals/${w.code}`))
        );
        data = results.map(r => ({
          code: r.code,
          name: r.name,
          latest_price: r.latest_price ?? 0,
          has_accumulation: r.accumulation_signal,
          has_exit: (r.alerts ?? []).some(a => a.alert_type === 'exit'),
          has_stop_loss: r.stop_loss_triggered,
          edinet_recent_count: 0,
          score: 0,
          generated_at: new Date().toISOString(),
        }));
      } else if (activeTab === 'favorites') {
        const favorites = await api('/favorites?tag=speculative');
        const results = await Promise.all(
          favorites.map(f => api(`/signals/${f.code}`))
        );
        data = results.map(r => ({
          code: r.code,
          name: r.name,
          latest_price: r.latest_price ?? 0,
          has_accumulation: r.accumulation_signal,
          has_exit: (r.alerts ?? []).some(a => a.alert_type === 'exit'),
          has_stop_loss: r.stop_loss_triggered,
          edinet_recent_count: 0,
          score: 0,
          generated_at: new Date().toISOString(),
        }));
      }
    } catch (e) {
      error = e instanceof Error ? e.message : '讀取資料失敗';
    } finally {
      loading = false;
    }
  }

  function handleTabChange(tab: typeof activeTab) {
    activeTab = tab;
    loadData();
  }

  function handleRowClick(code: string) {
    goto(`/signals/${code}`);
  }
</script>

<div class="signals-page">
  <div class="header">
    <h1>投機訊號</h1>
    <div class="tabs">
      <button
        class="tab"
        class:active={activeTab === 'market'}
        on:click={() => handleTabChange('market')}
      >
        全市場訊號
      </button>
      <button
        class="tab"
        class:active={activeTab === 'watchlist'}
        on:click={() => handleTabChange('watchlist')}
      >
        我的持倉
      </button>
      <button
        class="tab"
        class:active={activeTab === 'favorites'}
        on:click={() => handleTabChange('favorites')}
      >
        我的最愛
      </button>
    </div>
  </div>

  {#if loading}
    <p class="loading">加載中...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else}
    <DataTable {data} {onRowClick: handleRowClick} />
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
</style>
