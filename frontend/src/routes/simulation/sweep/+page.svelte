<script lang="ts">
  import { onMount } from 'svelte';

  const API = '/api/v1';

  // grid params
  let stopLossInput = '0.03,0.05,0.08';
  let takeProfitInput = '0.10,0.15,0.20';
  let maxHoldInput = '';
  let metric = 'total_return';
  let topN = 20;

  // base config（簡化版，使用現有模擬清單選）
  let simCode = '';
  let startDate = '2024-01-01';
  let endDate = '2024-12-31';
  let initialCapital = 1000000;

  // runtime
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
          entry_rule: { price_basis: 'next_open', require_signal: true, indicator_entry: [], indicator_entry_logic: 'or' },
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

      // 取得完整結果
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
    // 在新視窗開啟模擬頁（未來可實作自動建立一筆模擬）
    alert(`最佳參數：${JSON.stringify(row.params)}\n總報酬：${row.total_return?.toFixed(2)}%\n勝率：${row.win_rate?.toFixed(1)}%`);
  }

  // 計算熱圖資料（stop_loss × take_profit）
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
    if (max === min) return '#64748b';
    const t = (val - min) / (max - min);
    const r = Math.round(255 * (1 - t));
    const g = Math.round(200 * t);
    return `rgb(${r},${g},80)`;
  }
</script>

<div class="p-6 max-w-6xl mx-auto">
  <h1 class="text-2xl font-bold mb-6">策略參數 Sweep（網格回測）</h1>

  <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
    <!-- 參數設定 -->
    <div class="bg-white border rounded-xl p-5 shadow-sm">
      <h2 class="font-semibold text-lg mb-4">參數網格</h2>

      <div class="mb-3">
        <label class="block text-sm text-gray-600 mb-1">停損 % (逗號分隔)</label>
        <input bind:value={stopLossInput} class="w-full border rounded px-3 py-1.5 text-sm" placeholder="0.03,0.05,0.08" />
      </div>
      <div class="mb-3">
        <label class="block text-sm text-gray-600 mb-1">獲利了結 % (逗號分隔)</label>
        <input bind:value={takeProfitInput} class="w-full border rounded px-3 py-1.5 text-sm" placeholder="0.10,0.15,0.20" />
      </div>
      <div class="mb-3">
        <label class="block text-sm text-gray-600 mb-1">最大持倉天數 (可空)</label>
        <input bind:value={maxHoldInput} class="w-full border rounded px-3 py-1.5 text-sm" placeholder="20,30,60" />
      </div>

      <div class="text-sm text-blue-700 font-medium">
        估算組合數：<span class:text-red-600={estimatedCombos > 200}>{estimatedCombos}</span>
        {#if estimatedCombos > 200}<span class="text-red-500">（超過上限 200）</span>{/if}
      </div>
    </div>

    <!-- 基本設定 -->
    <div class="bg-white border rounded-xl p-5 shadow-sm">
      <h2 class="font-semibold text-lg mb-4">回測設定</h2>

      <div class="mb-3">
        <label class="block text-sm text-gray-600 mb-1">股票代碼</label>
        <input bind:value={simCode} class="w-full border rounded px-3 py-1.5 text-sm" placeholder="7203" />
      </div>
      <div class="mb-3 grid grid-cols-2 gap-2">
        <div>
          <label class="block text-sm text-gray-600 mb-1">開始日期</label>
          <input type="date" bind:value={startDate} class="w-full border rounded px-3 py-1.5 text-sm" />
        </div>
        <div>
          <label class="block text-sm text-gray-600 mb-1">結束日期</label>
          <input type="date" bind:value={endDate} class="w-full border rounded px-3 py-1.5 text-sm" />
        </div>
      </div>
      <div class="mb-3">
        <label class="block text-sm text-gray-600 mb-1">初始資金（JPY）</label>
        <input type="number" bind:value={initialCapital} class="w-full border rounded px-3 py-1.5 text-sm" />
      </div>
      <div class="mb-3">
        <label class="block text-sm text-gray-600 mb-1">排序指標</label>
        <select bind:value={metric} class="w-full border rounded px-3 py-1.5 text-sm">
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
    class="px-6 py-2 bg-blue-600 text-white rounded-lg font-semibold disabled:opacity-50 hover:bg-blue-700 transition"
  >
    {running ? '執行中...' : '執行 Sweep'}
  </button>

  {#if error}
    <div class="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded">{error}</div>
  {/if}

  {#if result}
    <div class="mt-8">
      <h2 class="text-xl font-bold mb-4">
        Sweep 結果（{result.n_combinations} 組合，顯示 top {result.rows?.length}）
      </h2>

      <!-- 熱圖 -->
      {#if heatmap}
        <div class="bg-white border rounded-xl p-4 shadow-sm mb-6 overflow-auto">
          <h3 class="font-semibold mb-3">熱圖（stop_loss × take_profit → 總報酬%）</h3>
          <table class="text-xs border-collapse">
            <thead>
              <tr>
                <th class="p-2 bg-gray-100">TP \ SL</th>
                {#each heatmap.slValues as sl}
                  <th class="p-2 bg-gray-100">{(sl*100).toFixed(0)}%</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each heatmap.tpValues as tp, ti}
                <tr>
                  <td class="p-2 bg-gray-50 font-medium">{(tp*100).toFixed(0)}%</td>
                  {#each heatmap.matrix[ti] as val, si}
                    <td
                      class="p-2 text-center font-semibold cursor-pointer hover:opacity-80"
                      style="background:{heatColor(val, heatmap.minV, heatmap.maxV)}; color: #1e293b; min-width:56px"
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
      {/if}

      <!-- 排行榜 -->
      <div class="bg-white border rounded-xl shadow-sm overflow-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-3 py-2 text-left">#</th>
              <th class="px-3 py-2 text-left">參數</th>
              <th class="px-3 py-2 text-right">總報酬%</th>
              <th class="px-3 py-2 text-right">年化%</th>
              <th class="px-3 py-2 text-right">最大回撤%</th>
              <th class="px-3 py-2 text-right">勝率%</th>
              <th class="px-3 py-2 text-right">PF</th>
              <th class="px-3 py-2 text-right">交易數</th>
              <th class="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {#each result.rows as row, i}
              <tr class="border-t hover:bg-gray-50">
                <td class="px-3 py-2 text-gray-500">{i + 1}</td>
                <td class="px-3 py-2 font-mono text-xs">
                  {#each Object.entries(row.params) as [k, v]}
                    <span class="mr-2">{k}={typeof v === 'number' ? (v * 100).toFixed(0) + '%' : v}</span>
                  {/each}
                </td>
                <td class="px-3 py-2 text-right font-semibold {row.total_return >= 0 ? 'text-green-600' : 'text-red-600'}">
                  {row.total_return?.toFixed(2)}
                </td>
                <td class="px-3 py-2 text-right">{row.annualized?.toFixed(2)}</td>
                <td class="px-3 py-2 text-right text-red-500">{row.max_drawdown?.toFixed(2)}</td>
                <td class="px-3 py-2 text-right">{row.win_rate?.toFixed(1)}</td>
                <td class="px-3 py-2 text-right">{row.profit_factor?.toFixed(2)}</td>
                <td class="px-3 py-2 text-right">{row.n_trades}</td>
                <td class="px-3 py-2">
                  <button
                    on:click={() => goToSim(row)}
                    class="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                  >
                    詳情
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</div>
