<script lang="ts">
  const API = '/api/v1';

  let stopLossInput = '0.05,0.08,0.10';
  let takeProfitInput = '0.15,0.20,0.25';
  let maxHoldInput = '';
  let metric = 'total_return';
  let topN = 20;

  let simCode = '7203';
  let startDate = '2024-01-01';
  let endDate = '2024-12-31';
  let initialCapital = 1000000;

  let estimatedCombos = 0;
  let running = false;
  let error = '';
  let result: any = null;
  let jobId = '';

  function parseList<T>(input: string, parser: (s: string) => T): T[] {
    return input.split(',').map(s => s.trim()).filter(Boolean).map(parser);
  }

  $: {
    const sl = parseList(stopLossInput, Number).length || 1;
    const tp = parseList(takeProfitInput, Number).length || 1;
    const mh = maxHoldInput ? parseList(maxHoldInput, Number).length : 1;
    estimatedCombos = sl * tp * mh;
  }

  async function runSweep() {
    error = '';
    result = null;
    running = true;
    try {
      const grid: any = {};
      const sl = parseList(stopLossInput, Number);
      const tp = parseList(takeProfitInput, Number);
      const mh = maxHoldInput ? parseList(maxHoldInput, Number) : null;
      if (sl.length) grid.stop_loss_pct = sl;
      if (tp.length) grid.take_profit_pct = tp;
      if (mh) grid.max_hold_days = mh;

      const body = {
        base_config: {
          kind: 'backtest',
          initial_capital: initialCapital,
          start_date: startDate,
          end_date: endDate,
          candidates: simCode ? [{ code: simCode, name: simCode }] : [],
          entry_rule: { price_basis: 'next_open', require_signal: false, indicator_entry: [], indicator_entry_logic: 'or' },
          exit_rule: { use_exit_signal: true, use_stop_loss: true, exit_price_basis: 'next_open', indicator_exit: [], indicator_exit_logic: 'or' },
          position_sizing: { mode: 'equal_weight', max_concurrent_positions: 5 },
          cost_model: { commission_pct: 0.001, slippage_pct: 0.001, tax_pct: 0.20315 },
        },
        grid,
        metric,
        top_n: topN,
      };

      const res = await fetch(`${API}/sweep/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || res.statusText);
      }

      const info = await res.json();
      jobId = info.job_id;

      const resultRes = await fetch(`${API}/sweep/${jobId}`);
      if (resultRes.ok) {
        result = await resultRes.json();
      }
    } catch (e: any) {
      error = e.message;
    } finally {
      running = false;
    }
  }

  function goToSim(row: any) {
    alert(`最佳參數：${JSON.stringify(row.params)}\n總報酬：${row.total_return?.toFixed(2)}%\n勝率：${row.win_rate?.toFixed(1)}%`);
  }

  $: heatmap = buildHeatmap(result);

  function buildHeatmap(result: any) {
    if (!result?.rows?.length) return null;
    const rows = result.rows;
    const slValues = [...new Set(rows.map((r: any) => r.params?.stop_loss_pct).filter((v: any) => v != null))].sort((a: any, b: any) => a - b);
    const tpValues = [...new Set(rows.map((r: any) => r.params?.take_profit_pct).filter((v: any) => v != null))].sort((a: any, b: any) => a - b);
    if (!slValues.length || !tpValues.length) return null;

    const matrix: number[][] = tpValues.map(tp =>
      slValues.map(sl => {
        const match = rows.find((r: any) => r.params?.stop_loss_pct === sl && r.params?.take_profit_pct === tp);
        return match ? match.total_return : 0;
      })
    );

    const allVals = matrix.flat();
    const minV = Math.min(...allVals);
    const maxV = Math.max(...allVals);

    return { slValues, tpValues, matrix, minV, maxV };
  }

  function heatColor(val: number, min: number, max: number) {
    if (max === min) return '#374151';
    const t = (val - min) / (max - min);
    const r = Math.round(180 * (1 - t));
    const g = Math.round(220 * t);
    return `rgb(${r},${g},80)`;
  }
</script>

<div class="sweep-page">
  <div class="header">
    <div class="header-top">
      <a href="/simulation" class="back-btn">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 3L5 8L10 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        模擬交易
      </a>
    </div>
    <h1>策略參數 Sweep（網格回測）</h1>
  </div>

  <div class="grid-2col">
    <!-- 參數網格 -->
    <div class="card">
      <h2>參數網格</h2>

      <div class="form-group">
        <label>停損 % (逗號分隔)</label>
        <input bind:value={stopLossInput} placeholder="0.03,0.05,0.08" />
      </div>
      <div class="form-group">
        <label>獲利了結 % (逗號分隔)</label>
        <input bind:value={takeProfitInput} placeholder="0.10,0.15,0.20" />
      </div>
      <div class="form-group">
        <label>最大持倉天數 (可空)</label>
        <input bind:value={maxHoldInput} placeholder="20,30,60" />
      </div>

      <div class="combo-count" class:over-limit={estimatedCombos > 200}>
        估算組合數：<strong>{estimatedCombos}</strong>
        {#if estimatedCombos > 200}<span class="warn">（超過上限 200）</span>{/if}
      </div>
    </div>

    <!-- 回測設定 -->
    <div class="card">
      <h2>回測設定</h2>

      <div class="form-group">
        <label>股票代碼</label>
        <input bind:value={simCode} placeholder="7203" />
      </div>
      <div class="grid-2col-inner">
        <div class="form-group">
          <label>開始日期</label>
          <input type="date" bind:value={startDate} />
        </div>
        <div class="form-group">
          <label>結束日期</label>
          <input type="date" bind:value={endDate} />
        </div>
      </div>
      <div class="form-group">
        <label>初始資金（JPY）</label>
        <input type="number" bind:value={initialCapital} />
      </div>
      <div class="form-group">
        <label>排序指標</label>
        <select bind:value={metric}>
          <option value="total_return">總報酬</option>
          <option value="win_rate">勝率</option>
          <option value="profit_factor">Profit Factor</option>
          <option value="max_drawdown">最大回撤（升序）</option>
        </select>
      </div>
    </div>
  </div>

  <button
    on:click={runSweep}
    disabled={running || estimatedCombos > 200}
    class="btn-run"
  >
    {running ? '執行中...' : '執行 Sweep'}
  </button>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  {#if result}
    <div class="results">
      <h2>Sweep 結果（{result.n_combinations} 組合，顯示 top {result.rows?.length}）</h2>

      {#if heatmap}
        <div class="card">
          <h3>熱圖（stop_loss × take_profit → 總報酬%）</h3>
          <div class="heatmap-wrapper">
            <table class="heatmap">
              <thead>
                <tr>
                  <th>TP \ SL</th>
                  {#each heatmap.slValues as sl}
                    <th>{(sl*100).toFixed(0)}%</th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each heatmap.tpValues as tp, ti}
                  <tr>
                    <td class="row-label">{(tp*100).toFixed(0)}%</td>
                    {#each heatmap.matrix[ti] as val, si}
                      <td
                        class="heat-cell"
                        style="background:{heatColor(val, heatmap.minV, heatmap.maxV)}"
                        title="SL={heatmap.slValues[si]*100}% TP={tp*100}%"
                      >
                        {val.toFixed(1)}%
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}

      <div class="card table-card">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>參數</th>
              <th class="num">總報酬%</th>
              <th class="num">年化%</th>
              <th class="num">最大回撤%</th>
              <th class="num">勝率%</th>
              <th class="num">PF</th>
              <th class="num">交易數</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each result.rows as row, i}
              <tr>
                <td class="rank">{i + 1}</td>
                <td class="params">
                  {#each Object.entries(row.params) as [k, v]}
                    <span>{k}={typeof v === 'number' ? (v * 100).toFixed(0) + '%' : v}</span>
                  {/each}
                </td>
                <td class="num {row.total_return >= 0 ? 'positive' : 'negative'}">
                  {row.total_return?.toFixed(2)}
                </td>
                <td class="num">{row.annualized?.toFixed(2)}</td>
                <td class="num negative">{row.max_drawdown?.toFixed(2)}</td>
                <td class="num">{row.win_rate?.toFixed(1)}</td>
                <td class="num">{row.profit_factor?.toFixed(2)}</td>
                <td class="num">{row.n_trades}</td>
                <td>
                  <button class="btn-detail" on:click={() => goToSim(row)}>詳情</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</div>

<style>
  .sweep-page {
    padding: 20px;
    max-width: 1200px;
    margin: 0 auto;
  }

  .header {
    margin-bottom: 28px;
  }

  .header-top {
    margin-bottom: 12px;
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px 6px 10px;
    background: #1e1e2e;
    border: 1px solid #4b5563;
    border-radius: 6px;
    color: #c4b5fd;
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    transition: background 0.2s, border-color 0.2s, color 0.2s;
  }

  .back-btn:hover {
    background: #2d2b45;
    border-color: #8b5cf6;
    color: #a78bfa;
  }

  h1 {
    color: #4ade80;
    margin: 0;
    font-size: 24px;
  }

  h2 {
    color: #4ade80;
    font-size: 16px;
    margin: 0 0 16px;
  }

  h3 {
    color: #a1a1a1;
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 12px;
  }

  .grid-2col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }

  .grid-2col-inner {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .card {
    background-color: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 20px;
  }

  .form-group {
    margin-bottom: 14px;
  }

  label {
    display: block;
    font-size: 12px;
    color: #9ca3af;
    margin-bottom: 5px;
  }

  input, select {
    width: 100%;
    background-color: #111;
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 7px 10px;
    color: #e5e7eb;
    font-size: 13px;
    box-sizing: border-box;
  }

  input:focus, select:focus {
    outline: none;
    border-color: #4ade80;
  }

  .combo-count {
    font-size: 13px;
    color: #9ca3af;
    padding: 8px 10px;
    background: #111;
    border-radius: 4px;
    border: 1px solid #2a2a2a;
  }

  .combo-count strong {
    color: #e5e7eb;
  }

  .warn {
    color: #f87171;
  }

  .btn-run {
    padding: 10px 28px;
    background-color: #4ade80;
    color: #111;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
    margin-bottom: 24px;
  }

  .btn-run:hover:not(:disabled) {
    background-color: #3dd66f;
  }

  .btn-run:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .error {
    background-color: #7f1d1d;
    color: #fca5a5;
    padding: 12px;
    border-radius: 6px;
    margin-bottom: 20px;
    font-size: 13px;
  }

  .results h2 {
    margin-bottom: 16px;
  }

  .heatmap-wrapper {
    overflow-x: auto;
  }

  .heatmap {
    border-collapse: collapse;
    font-size: 12px;
  }

  .heatmap th {
    padding: 7px 12px;
    background: #2a2a2a;
    color: #9ca3af;
    font-weight: 600;
    text-align: center;
  }

  .row-label {
    padding: 7px 12px;
    background: #222;
    color: #9ca3af;
    font-weight: 600;
    text-align: center;
  }

  .heat-cell {
    padding: 7px 14px;
    text-align: center;
    font-weight: 600;
    color: #1a1a1a;
    cursor: pointer;
    min-width: 56px;
    transition: opacity 0.15s;
  }

  .heat-cell:hover {
    opacity: 0.8;
  }

  .table-card {
    padding: 0;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    background-color: #2a2a2a;
  }

  th {
    padding: 11px 12px;
    color: #4ade80;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
    border-bottom: 1px solid #333;
  }

  td {
    padding: 11px 12px;
    color: #e5e5e5;
    font-size: 13px;
    border-bottom: 1px solid #2a2a2a;
  }

  tbody tr:hover {
    background-color: #222;
  }

  .rank {
    color: #6b7280;
    font-size: 12px;
  }

  .params {
    font-family: monospace;
    font-size: 11px;
    color: #9ca3af;
  }

  .params span {
    display: inline-block;
    margin-right: 8px;
  }

  .num {
    text-align: right;
  }

  .positive {
    color: #4ade80;
    font-weight: 500;
  }

  .negative {
    color: #f87171;
  }

  .btn-detail {
    padding: 4px 10px;
    font-size: 11px;
    background: #374151;
    color: #a3e635;
    border: 1px solid #4b5563;
    border-radius: 3px;
    cursor: pointer;
    transition: background 0.15s;
  }

  .btn-detail:hover {
    background: #4b5563;
  }

  @media (max-width: 768px) {
    .grid-2col {
      grid-template-columns: 1fr;
    }
  }
</style>
