<script lang="ts">
  import { onMount } from 'svelte';
  // @ts-ignore – $app/stores types resolved at SvelteKit build time
  import { page } from '$app/stores';
  // @ts-ignore
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import ComparePanel from '$lib/components/ComparePanel.svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  type IndicatorSeries = { name: string; dates: string[]; values: (number | null)[] };
  type IndicatorSignal = { date: string; name: string; type: string; strength: string };
  type Bundle = {
    codes: string[];
    period_days: number;
    series_by_code: Record<string, Record<string, IndicatorSeries>>;
    dates_by_code: Record<string, string[]>;
    normalized_close: Record<string, (number | null)[]>;
    signals_by_code: Record<string, IndicatorSignal[]>;
    correlation_matrix: Record<string, Record<string, number>>;
  };

  const COLORS = ['#4ade80', '#60a5fa', '#f97316', '#e879f9', '#facc15'];

  let inputCode = '';
  let codes: string[] = [];
  let days = 120;
  let bundle: Bundle | null = null;
  let loading = false;
  let error = '';

  // init from query params
  onMount(() => {
    const params = new URLSearchParams($page.url.search);
    const c = params.get('codes');
    if (c) codes = c.split(',').filter(Boolean);
    const d = params.get('days');
    if (d) days = parseInt(d) || 120;
    if (codes.length) load();
  });

  async function load() {
    if (!codes.length) return;
    loading = true;
    error = '';
    bundle = null;
    try {
      bundle = await api<Bundle>(`/compare/signals?codes=${codes.join(',')}&days=${days}`);
    } catch (e) {
      error = e instanceof Error ? e.message : '讀取失敗';
    } finally {
      loading = false;
    }
    goto(`/compare?codes=${codes.join(',')}&days=${days}`, { replaceState: true });
  }

  function addCode() {
    const c = inputCode.trim().toUpperCase();
    if (!c || codes.includes(c) || codes.length >= 5) return;
    codes = [...codes, c];
    inputCode = '';
    load();
  }

  function removeCode(c: string) {
    codes = codes.filter(x => x !== c);
    if (codes.length) load();
    else bundle = null;
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') addCode();
  }
</script>

<div class="page">
  <h2>投機對比</h2>

  <div class="controls">
    <div class="chip-bar">
      {#each codes as c, i}
        <span class="chip" style="border-color:{COLORS[i % COLORS.length]}">
          {c}
          <button class="remove" on:click={() => removeCode(c)}>×</button>
        </span>
      {/each}
      {#if codes.length < 5}
        <input
          class="code-input"
          placeholder="輸入代碼 Enter"
          bind:value={inputCode}
          on:keydown={onKeydown}
        />
        <button class="btn" on:click={addCode}>加入</button>
      {/if}
    </div>
    <div class="day-select">
      <label>期間
        <select bind:value={days} on:change={load}>
          <option value={60}>60 日</option>
          <option value={120}>120 日</option>
          <option value={250}>250 日</option>
        </select>
      </label>
    </div>
  </div>

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <p class="err">{error}</p>
  {:else if bundle}
    <!-- Normalized K 線圖（SVG 折線） -->
    <div class="card">
      <h3>正規化走勢（期初 = 100）</h3>
      <div class="chart-area">
        <svg viewBox="0 0 800 300" preserveAspectRatio="none" class="svg-chart">
          {#each bundle.codes as code, ci}
            {@const vals = bundle.normalized_close[code] ?? []}
            {@const pts = vals
              .map((v, i) => v != null ? `${(i / (vals.length - 1)) * 800},${300 - ((v - 80) / 60) * 300}` : null)
              .filter(Boolean)}
            {#if pts.length > 1}
              <polyline
                points={pts.join(' ')}
                fill="none"
                stroke={COLORS[ci % COLORS.length]}
                stroke-width="2"
              />
            {/if}
          {/each}
          <!-- baseline 100 -->
          <line x1="0" y1={300 - ((100 - 80) / 60) * 300} x2="800" y2={300 - ((100 - 80) / 60) * 300}
            stroke="#555" stroke-dasharray="4" stroke-width="1" />
        </svg>
        <div class="legend">
          {#each bundle.codes as code, ci}
            <span class="legend-item" style="color:{COLORS[ci % COLORS.length]}">■ {code}</span>
          {/each}
        </div>
      </div>
    </div>

    <!-- Correlation heatmap -->
    <ComparePanel correlationMatrix={bundle.correlation_matrix} codes={bundle.codes} />

    <!-- 訊號清單 -->
    <div class="card">
      <h3>最近指標訊號</h3>
      {#each bundle.codes as code, ci}
        {@const sigs = bundle.signals_by_code[code] ?? []}
        {#if sigs.length}
          <div class="sig-group">
            <span class="sig-code" style="color:{COLORS[ci % COLORS.length]}">{code}</span>
            {#each sigs.slice(0, 5) as s}
              <span class="sig-item">{s.date} {s.name}</span>
            {/each}
          </div>
        {/if}
      {/each}
    </div>
  {:else if codes.length === 0}
    <p class="status">請輸入股票代碼開始比較（最多 5 檔）</p>
  {/if}
</div>

<style>
  .page { padding: 24px; }
  h2 { color: #fff; margin: 0 0 20px 0; }
  h3 { color: #fff; margin: 0 0 12px 0; font-size: 14px; }

  .controls { display: flex; gap: 16px; align-items: center; margin-bottom: 20px; flex-wrap: wrap; }
  .chip-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .chip {
    display: flex; align-items: center; gap: 4px;
    padding: 4px 10px; border-radius: 16px; border: 1px solid;
    font-size: 13px; color: #fff;
  }
  .remove { background: none; border: none; color: #888; cursor: pointer; font-size: 16px; padding: 0 2px; }
  .code-input {
    background: #222; border: 1px solid #444; color: #fff;
    padding: 6px 10px; border-radius: 4px; font-size: 13px; width: 120px;
  }
  .btn {
    background: #4ade80; color: #000; border: none;
    padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px;
  }
  .day-select label { color: #a1a1a1; font-size: 13px; display: flex; align-items: center; gap: 8px; }
  .day-select select { background: #222; border: 1px solid #444; color: #fff; padding: 4px 8px; border-radius: 4px; }

  .card { background: #1a1a1a; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
  .chart-area { position: relative; }
  .svg-chart { width: 100%; height: 250px; display: block; }
  .legend { display: flex; gap: 12px; margin-top: 8px; font-size: 12px; }
  .legend-item { }

  .sig-group { margin-bottom: 8px; }
  .sig-code { font-weight: bold; font-size: 13px; margin-right: 8px; }
  .sig-item { font-size: 12px; color: #a1a1a1; margin-right: 8px; }

  .status { color: #666; }
  .err { color: #f87171; }
</style>
