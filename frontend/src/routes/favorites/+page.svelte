<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
  import type { SignalResult, SignalScanRow } from '$lib/types';

  let data: SignalScanRow[] = [];
  let loading = true;
  let error = '';

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

  onMount(async () => {
    try {
      const entries = await api<{ code: string }[]>('/favorites');
      const results: SignalResult[] = await Promise.all(
        entries.map(e => api<SignalResult>(`/signals/${e.code}`))
      );
      data = results.map(toScanRow);
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  });

  function handleRowClick(code: string) {
    goto(`/signals/${code}`);
  }
</script>

<div class="favorites-page">
  <h1>我的最愛</h1>

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
</style>
