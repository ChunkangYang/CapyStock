<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import type { Simulation } from '$lib/types';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  let simulations: Simulation[] = [];
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      simulations = await api<Simulation[]>('/simulation');
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load simulations';
    } finally {
      loading = false;
    }
  });

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('ja-JP');
  }

  function formatPercent(value: number): string {
    return (value * 100).toFixed(2) + '%';
  }

  async function deleteSimulation(id: string) {
    if (!confirm('本当に削除しますか?')) return;
    try {
      await api(`/simulation/${id}`, { method: 'DELETE' });
      simulations = simulations.filter((s) => s.id !== id);
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Delete failed');
    }
  }

  function getStatusBadgeClass(status: string): string {
    return `status-badge status-${status}`;
  }

  function getKindLabel(kind: string): string {
    return kind === 'backtest' ? '回測' : '模擬交易';
  }
</script>

<div class="simulation-page">
  <div class="header">
    <h1>模擬交易</h1>
    <a href="/simulation/new" class="btn btn-primary">+ 新建模擬</a>
  </div>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  {#if loading}
    <LoadingSpinner />
  {:else if simulations.length === 0}
    <div class="empty">
      <p>模擬交易模型未找到</p>
      <a href="/simulation/new" class="btn btn-primary">建立第一個模擬</a>
    </div>
  {:else}
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>名稱</th>
            <th>類型</th>
            <th>狀態</th>
            <th>期間</th>
            <th>初始資金</th>
            <th>當前權益</th>
            <th>報酬</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {#each simulations as sim (sim.id)}
            <tr>
              <td>{sim.name}</td>
              <td>{getKindLabel(sim.config.kind)}</td>
              <td>
                <span class={getStatusBadgeClass(sim.status)}>
                  {sim.status}
                </span>
              </td>
              <td>
                {formatDate(sim.config.start_date)}
                {#if sim.config.end_date}
                  ~ {formatDate(sim.config.end_date)}
                {/if}
              </td>
              <td>¥{sim.config.initial_capital.toLocaleString('ja-JP')}</td>
              <td>¥{sim.state.cash.toLocaleString('ja-JP')}</td>
              <td>
                {#if sim.state.equity_curve.length > 0}
                  {@const final = sim.state.equity_curve[sim.state.equity_curve.length - 1]}
                  {@const returnPct = (final.equity - sim.config.initial_capital) / sim.config.initial_capital}
                  <span class={returnPct >= 0 ? 'positive' : 'negative'}>
                    {formatPercent(returnPct)}
                  </span>
                {/if}
              </td>
              <td class="actions">
                <a href="/simulation/{sim.id}" class="btn btn-sm btn-view">檢視</a>
                <button class="btn btn-sm btn-danger" on:click={() => deleteSimulation(sim.id)}>
                  刪除
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .simulation-page {
    padding: 20px;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
  }

  h1 {
    color: #4ade80;
    margin: 0;
    font-size: 24px;
  }

  .btn {
    display: inline-block;
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    text-decoration: none;
    font-size: 14px;
    transition: all 0.2s;
  }

  .btn-primary {
    background-color: #4ade80;
    color: #1a1a1a;
    font-weight: 500;
  }

  .btn-primary:hover {
    background-color: #3dd66f;
  }

  .btn-sm {
    padding: 6px 12px;
    font-size: 12px;
  }

  .btn-danger {
    background-color: #f87171;
    color: white;
  }

  .btn-danger:hover {
    background-color: #ef4444;
  }

  .btn-view {
    background-color: #3b82f6;
    color: #fff;
  }

  .btn-view:hover {
    background-color: #2563eb;
  }

  .error {
    background-color: #7f1d1d;
    color: #fca5a5;
    padding: 12px;
    border-radius: 4px;
    margin-bottom: 20px;
  }

  .loading,
  .empty {
    text-align: center;
    color: #a1a1a1;
    padding: 40px;
  }

  .empty .btn-primary {
    margin-top: 20px;
  }

  .table-wrapper {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    border: 1px solid #333;
    background-color: #1a1a1a;
  }

  thead {
    background-color: #2a2a2a;
  }

  th,
  td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #333;
    color: #e5e5e5;
  }

  th {
    font-weight: 600;
    color: #4ade80;
  }

  tbody tr:hover {
    background-color: #222;
  }

  .status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 3px;
    font-size: 12px;
    font-weight: 500;
  }

  .status-draft {
    background-color: #7c2d12;
    color: #fed7aa;
  }

  .status-running {
    background-color: #1e40af;
    color: #bfdbfe;
  }

  .status-completed {
    background-color: #15803d;
    color: #bbf7d0;
  }

  .status-failed {
    background-color: #7f1d1d;
    color: #fca5a5;
  }

  .positive {
    color: #4ade80;
    font-weight: 500;
  }

  .negative {
    color: #f87171;
    font-weight: 500;
  }

  .actions {
    display: flex;
    gap: 8px;
  }
</style>
