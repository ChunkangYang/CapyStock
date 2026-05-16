<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { cachedFetch, cacheClear, formatCacheAge } from '$lib/utils/signalsCache';
  import DataTable from '$lib/components/DataTable.svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
  import type { SignalResult, SignalScanRow } from '$lib/types';

  const CACHE_KEY = 'page_favorites';

  let data: SignalScanRow[] = [];
  let loading = true;
  let refreshing = false;
  let error = '';
  let cacheTs: number | null = null;

  function toScanRow(r: SignalResult): SignalScanRow {
    return {
      code: r.code,
      name: r.name,
      latest_price: r.latest_price ?? 0,
      has_accumulation: r.accumulation_signal ?? false,
      has_exit: (r.alerts ?? []).some(a => a.alert_type === 'exit'),
      has_stop_loss: r.stop_loss_triggered,
      edinet_recent_count: 0,
      score: (r as any).technical_score ?? 0,
      generated_at: new Date().toISOString(),
    };
  }

  async function loadData(forceRefresh = false) {
    if (forceRefresh) refreshing = true; else loading = true;
    try {
      const { data: result, ts } = await cachedFetch(
        CACHE_KEY,
        async () => {
          const entries = await api<{ code: string }[]>('/favorites');
          const results: SignalResult[] = await Promise.all(
            entries.map(e => api<SignalResult>(`/signals/${e.code}`))
          );
          return results.map(toScanRow);
        },
        forceRefresh,
      );
      data = result;
      cacheTs = ts;
    } catch (e) {
      error = String(e);
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

  function handleRowClick(code: string) {
    goto(`/signals/${code}`);
  }
</script>

<div class="favorites-page">
  <div class="title-row">
    <h1>我的最愛</h1>
    <div class="header-actions">
      {#if cacheTs}<span class="cache-age">上次更新：{formatCacheAge(cacheTs)}</span>{/if}
      <button class="btn-refresh" disabled={refreshing || loading} on:click={handleRefresh}>
        <span class:spinning={refreshing}>↻</span> 更新
      </button>
    </div>
  </div>

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <p class="error">{error}</p>
  {:else if data.length === 0}
    <p class="empty">還沒有任何最愛股票</p>
  {:else}
    <DataTable {data} onRowClick={handleRowClick} />
  {/if}
</div>

<style>
  .favorites-page h1 {
    color: #4ade80;
    margin: 0 0 30px 0;
  }

  .empty,
  .error {
    color: #6b7280;
    text-align: center;
    padding: 40px 20px;
  }

  .error {
    color: #f87171;
  }
  .title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .header-actions { display: flex; align-items: center; gap: 12px; }
  .cache-age { font-size: 12px; color: #666; }
  .btn-refresh {
    background: #1a1a1a; border: 1px solid #444; color: #ccc;
    padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px;
    display: inline-flex; align-items: center; gap: 6px;
  }
  .btn-refresh:hover:not(:disabled) { color: #4ade80; border-color: #4ade80; }
  .btn-refresh:disabled { opacity: 0.4; cursor: not-allowed; }
  .spinning { animation: spin 0.7s linear infinite; display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
