<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import type { Simulation, SimulationReport } from '$lib/types';
  import EquityCurveChart from '$lib/components/EquityCurveChart.svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  let sim: Simulation | null = null;
  let report: SimulationReport | null = null;
  let loading = true;
  let error = '';

  async function loadSimulation() {
    try {
      sim = await api<Simulation>(`/simulation/${$page.params.id}`);
      // Load report if completed
      if (sim.status === 'completed') {
        report = await api<SimulationReport>(`/simulation/${$page.params.id}/report`);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load simulation';
    } finally {
      loading = false;
    }
  }

  async function advanceToday() {
    if (!sim) return;
    try {
      sim = await api<Simulation>(`/simulation/${sim.id}/advance`, { method: 'POST' });
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to advance';
    }
  }

  async function rerun() {
    if (!sim) return;
    try {
      sim = await api<Simulation>(`/simulation/${sim.id}/run`, { method: 'POST' });
      if (sim.status === 'completed') {
        report = await api<SimulationReport>(`/simulation/${sim.id}/report`);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to rerun';
    }
  }

  async function deleteSimulation() {
    if (!sim || !confirm('確定要刪除嗎?')) return;
    try {
      await api(`/simulation/${sim.id}`, { method: 'DELETE' });
      goto('/simulation');
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Delete failed');
    }
  }

  async function closePosition(code: string) {
    if (!sim) return;
    const priceStr = prompt('出場價格:');
    if (!priceStr) return;
    const price = parseFloat(priceStr);
    if (isNaN(price)) {
      error = '無效的價格';
      return;
    }
    try {
      sim = await api<Simulation>(`/simulation/${sim.id}/close-position`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, exit_price: price })
      });
      if (sim.status === 'completed') {
        report = await api<SimulationReport>(`/simulation/${sim.id}/report`);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to close position';
    }
  }

  function downloadTrades() {
    if (!sim) return;

    let csv = 'Entry Date,Code,Entry Price,Shares,Exit Date,Exit Price,PnL JPY,PnL %,Hold Days,Reason\n';
    for (const trade of sim.state.closed_trades) {
      csv += `${trade.entry_date},${trade.code},${trade.entry_price},${trade.shares},${trade.exit_date},${trade.exit_price},${trade.pnl_jpy},${(trade.pnl_pct * 100).toFixed(2)}%,${trade.hold_days},${trade.exit_reason}\n`;
    }

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `simulation_${sim.id}_trades.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function formatPercent(value: number): string {
    return (value * 100).toFixed(2) + '%';
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('ja-JP');
  }

  loadSimulation();
  setInterval(() => {
    if (sim?.status === 'running' || sim?.status === 'draft') {
      loadSimulation();
    }
  }, 3000);
</script>

<div class="simulation-detail-page">
  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if loading}
    <LoadingSpinner size="lg" />
  {:else if !sim}
    <div class="error-container">找不到模擬</div>
  {:else}
    <div class="header-section">
      <div class="header-info">
        <h1>{sim.name}</h1>
        <div class="header-meta">
          <span class={`status-badge status-${sim.status}`}>{sim.status}</span>
          <span class="kind-badge">{sim.config.kind === 'backtest' ? '回測' : '模擬交易'}</span>
          <span class="period">
            {formatDate(sim.config.start_date)}
            {#if sim.config.end_date}
              ~ {formatDate(sim.config.end_date)}
            {/if}
          </span>
        </div>
      </div>

      <div class="header-actions">
        {#if sim.status === 'running' && sim.config.kind === 'paper'}
          <button class="btn btn-primary" on:click={advanceToday}>推進今日</button>
        {/if}
        {#if sim.status === 'completed' || sim.status === 'failed'}
          <button class="btn btn-secondary" on:click={rerun}>重新執行</button>
        {/if}
        <button class="btn btn-danger" on:click={deleteSimulation}>刪除</button>
      </div>
    </div>

    {#if report && sim.status === 'completed'}
      <div class="kpi-cards">
        <div class="kpi-card">
          <div class="kpi-label">總報酬</div>
          <div class={`kpi-value ${report.total_return_pct >= 0 ? 'positive' : 'negative'}`}>
            {formatPercent(report.total_return_pct)}
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">年化報酬</div>
          <div class={`kpi-value ${report.annualized_return_pct >= 0 ? 'positive' : 'negative'}`}>
            {formatPercent(report.annualized_return_pct)}
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">最大回撤</div>
          <div class="kpi-value negative">{formatPercent(Math.abs(report.max_drawdown_pct))}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">勝率</div>
          <div class={`kpi-value ${report.win_rate >= 0.5 ? 'positive' : 'negative'}`}>
            {formatPercent(report.win_rate)}
          </div>
        </div>
      </div>
    {/if}

    {#if report && sim.status === 'completed' && report.strategy_type}
      <div class="strategy-row">
        <span class="strategy-badge strategy-{report.strategy_type}">
          {report.strategy_type === 'pure_signal' ? '純訊號策略' : report.strategy_type === 'signal_indicator' ? '訊號 + 指標策略' : '純指標策略'}
        </span>
        {#if Object.keys(report.exit_reason_breakdown ?? {}).length}
          <div class="breakdown">
            <span class="breakdown-label">出場原因：</span>
            {#each Object.entries(report.exit_reason_breakdown) as [reason, cnt]}
              <span class="breakdown-item">{reason} × {cnt}</span>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    {#if sim.config.kind === 'paper' && sim.status === 'running'}
      <div class="status-cards">
        <div class="status-card">
          <div class="label">當前權益</div>
          <div class="value positive">¥{(sim.state.cash + (sim.state.positions.reduce((sum, p) => sum + p.shares * (sim?.state.equity_curve[sim.state.equity_curve.length - 1]?.market_value ?? 0), 0) ?? 0)).toLocaleString('ja-JP')}</div>
        </div>
        <div class="status-card">
          <div class="label">持倉數</div>
          <div class="value">{sim.state.positions.length}</div>
        </div>
        <div class="status-card">
          <div class="label">現金</div>
          <div class="value">¥{sim.state.cash.toLocaleString('ja-JP')}</div>
        </div>
      </div>
    {/if}

    <div class="content-grid">
      {#if sim.state.equity_curve.length > 0}
        <div class="chart-container">
          <h2>權益曲線</h2>
          <EquityCurveChart data={sim.state.equity_curve} initialCapital={sim.config.initial_capital} />
        </div>
      {/if}

      {#if sim.state.positions.length > 0}
        <div class="table-container">
          <h2>當前持倉</h2>
          <table>
            <thead>
              <tr>
                <th>代碼</th>
                <th>進場日期</th>
                <th>進場價</th>
                <th>股數</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {#each sim.state.positions as pos (pos.code)}
                <tr>
                  <td><strong>{pos.code}</strong> {pos.name}</td>
                  <td>{formatDate(pos.entry_date)}</td>
                  <td>¥{pos.entry_price.toFixed(2)}</td>
                  <td>{pos.shares}</td>
                  <td>
                    <button class="btn btn-sm btn-secondary" on:click={() => closePosition(pos.code)}>
                      平倉
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      {#if sim.state.closed_trades.length > 0}
        <div class="table-container">
          <div class="table-header">
            <h2>交易紀錄</h2>
            <button class="btn btn-sm btn-secondary" on:click={downloadTrades}>下載 CSV</button>
          </div>
          <table class="trades-table">
            <thead>
              <tr>
                <th>代碼</th>
                <th>進場</th>
                <th>出場</th>
                <th>股數</th>
                <th>損益 (JPY)</th>
                <th>損益 (%)</th>
                <th>持有天數</th>
                <th>出場原因</th>
              </tr>
            </thead>
            <tbody>
              {#each sim.state.closed_trades as trade (trade.code + trade.entry_date)}
                <tr>
                  <td>{trade.code}</td>
                  <td>{formatDate(trade.entry_date)} @ ¥{trade.entry_price.toFixed(2)}</td>
                  <td>{formatDate(trade.exit_date)} @ ¥{trade.exit_price.toFixed(2)}</td>
                  <td>{trade.shares}</td>
                  <td class={trade.pnl_jpy >= 0 ? 'positive' : 'negative'}>
                    ¥{trade.pnl_jpy.toFixed(0)}
                  </td>
                  <td class={trade.pnl_pct >= 0 ? 'positive' : 'negative'}>
                    {formatPercent(trade.pnl_pct)}
                  </td>
                  <td>{trade.hold_days}</td>
                  <td class="reason">{trade.exit_reason}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .simulation-detail-page {
    padding: 20px;
    max-width: 1400px;
    margin: 0 auto;
  }

  .error-banner {
    background-color: #7f1d1d;
    color: #fca5a5;
    padding: 12px;
    border-radius: 4px;
    margin-bottom: 20px;
  }

  .loading-container,
  .error-container {
    text-align: center;
    color: #999;
    padding: 40px;
  }

  .header-section {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 1px solid #333;
  }

  .header-info {
    flex: 1;
  }

  h1 {
    color: #4ade80;
    margin: 0 0 12px 0;
    font-size: 28px;
  }

  .header-meta {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: center;
  }

  .status-badge,
  .kind-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 3px;
    font-size: 12px;
    font-weight: 500;
  }

  .status-badge {
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

  .kind-badge {
    background-color: #444;
    color: #e5e5e5;
  }

  .period {
    color: #999;
    font-size: 14px;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }

  .btn {
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s;
  }

  .btn-primary {
    background-color: #4ade80;
    color: #1a1a1a;
  }

  .btn-primary:hover {
    background-color: #3dd66f;
  }

  .btn-secondary {
    background-color: #444;
    color: #e5e5e5;
  }

  .btn-secondary:hover {
    background-color: #555;
  }

  .btn-danger {
    background-color: #f87171;
    color: #1a1a1a;
  }

  .btn-danger:hover {
    background-color: #ef4444;
  }

  .btn-sm {
    padding: 6px 12px;
    font-size: 12px;
  }

  .kpi-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 30px;
  }

  .kpi-card {
    background-color: #0f0f0f;
    border: 1px solid #333;
    padding: 16px;
    border-radius: 4px;
    text-align: center;
  }

  .kpi-label {
    color: #999;
    font-size: 12px;
    margin-bottom: 8px;
  }

  .kpi-value {
    font-size: 24px;
    font-weight: 700;
    color: #e5e5e5;
  }

  .kpi-value.positive {
    color: #4ade80;
  }

  .kpi-value.negative {
    color: #f87171;
  }

  .status-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 30px;
  }

  .status-card {
    background-color: #0f0f0f;
    border: 1px solid #333;
    padding: 16px;
    border-radius: 4px;
  }

  .status-card .label {
    color: #999;
    font-size: 12px;
    margin-bottom: 8px;
  }

  .status-card .value {
    font-size: 18px;
    font-weight: 600;
    color: #e5e5e5;
  }

  .status-card .value.positive {
    color: #4ade80;
  }

  .content-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 30px;
  }

  .chart-container,
  .table-container {
    background-color: #0f0f0f;
    border: 1px solid #333;
    padding: 20px;
    border-radius: 4px;
  }

  h2 {
    color: #4ade80;
    margin: 0 0 16px 0;
    font-size: 18px;
  }

  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
  }

  .table-header h2 {
    margin: 0;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  thead {
    background-color: #1a1a1a;
  }

  th {
    padding: 10px;
    text-align: left;
    border-bottom: 1px solid #333;
    color: #4ade80;
    font-weight: 600;
  }

  td {
    padding: 10px;
    border-bottom: 1px solid #333;
    color: #e5e5e5;
  }

  tbody tr:hover {
    background-color: #1a1a1a;
  }

  .positive {
    color: #4ade80;
    font-weight: 500;
  }

  .negative {
    color: #f87171;
    font-weight: 500;
  }

  .reason {
    color: #999;
    font-size: 12px;
  }

  .trades-table {
    font-size: 12px;
  }

  .strategy-row {
    display: flex; gap: 16px; align-items: center; margin-bottom: 16px; flex-wrap: wrap;
  }
  .strategy-badge {
    padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;
  }
  .strategy-pure_signal { background: #1e3a5f; color: #60a5fa; }
  .strategy-signal_indicator { background: #1a3a1a; color: #4ade80; }
  .strategy-pure_indicator { background: #3a1a3a; color: #e879f9; }
  .breakdown { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .breakdown-label { color: #666; font-size: 12px; }
  .breakdown-item {
    background: #222; border: 1px solid #444; padding: 2px 8px;
    border-radius: 4px; font-size: 12px; color: #ccc;
  }
</style>
