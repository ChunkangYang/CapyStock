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
  type SignalRow = { code: string; name: string; score: number };

  const COLORS = ['#4ade80', '#60a5fa', '#f97316', '#e879f9', '#facc15'];

  const SIG_LABEL: Record<string, { text: string; bullish: boolean }> = {
    rsi_oversold:          { text: 'RSI 超賣（可能反彈）', bullish: true },
    rsi_overbought:        { text: 'RSI 超買（注意回調）', bullish: false },
    macd_golden_cross:     { text: 'MACD 金叉（動能向上）', bullish: true },
    macd_dead_cross:       { text: 'MACD 死叉（動能向下）', bullish: false },
    bb_breakout_up:        { text: '布林上突破（強勢突破）', bullish: true },
    bb_breakout_down:      { text: '布林下突破（跌破支撐）', bullish: false },
    sma_golden_cross_5_20: { text: '均線金叉 5/20（短線翻多）', bullish: true },
    sma_dead_cross_5_20:   { text: '均線死叉 5/20（短線翻空）', bullish: false },
  };

  function sigLabel(name: string) {
    return SIG_LABEL[name] ?? { text: name, bullish: true };
  }

  const bundleCache = new Map<string, Bundle>();

  let inputCode = '';
  let codes: string[] = [];
  let days = 60;
  let bundle: Bundle | null = null;
  let loading = false;
  let error = '';

  // picker state
  let pickerOpen = false;
  let pickerLoading = false;
  let pickerRows: SignalRow[] = [];
  let pickerSelected: Set<string> = new Set();

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
    const cacheKey = `${[...codes].sort().join(',')}:${days}`;
    if (bundleCache.has(cacheKey)) {
      bundle = bundleCache.get(cacheKey)!;
      goto(`/compare?codes=${codes.join(',')}&days=${days}`, { replaceState: true });
      return;
    }
    loading = true;
    error = '';
    bundle = null;
    try {
      const data = await api<Bundle>(`/compare/signals?codes=${codes.join(',')}&days=${days}`);
      bundleCache.set(cacheKey, data);
      bundle = data;
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

  async function openPicker() {
    pickerOpen = true;
    pickerSelected = new Set(codes);
    if (pickerRows.length === 0) {
      pickerLoading = true;
      try {
        pickerRows = await api<SignalRow[]>('/scan/signals');
        pickerRows = pickerRows.sort((a, b) => b.score - a.score);
      } catch {
        pickerRows = [];
      } finally {
        pickerLoading = false;
      }
    }
  }

  function togglePicker(code: string) {
    const next = new Set(pickerSelected);
    if (next.has(code)) {
      next.delete(code);
    } else if (next.size < 5) {
      next.add(code);
    }
    pickerSelected = next;
  }

  function confirmPicker() {
    codes = Array.from(pickerSelected);
    pickerOpen = false;
    if (codes.length) load();
    else bundle = null;
  }
</script>

<div class="page">
  <h1>投機對比</h1>

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
        <button class="btn btn-secondary" on:click={openPicker}>從清單選取</button>
      {/if}
    </div>
    <div class="day-select">
      <label>期間
        <select bind:value={days} on:change={load}>
          <option value={30}>30 日</option>
          <option value={60}>60 日</option>
          <option value={120}>120 日</option>
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
      <h3>最近 14 日指標訊號</h3>
      {#each bundle.codes as code, ci}
        {@const sigs = bundle.signals_by_code[code] ?? []}
        {#if sigs.length}
          <div class="sig-group">
            <span class="sig-code" style="color:{COLORS[ci % COLORS.length]}">{code}</span>
            <div class="sig-pills">
              {#each sigs.slice(0, 6) as s}
                {@const lbl = sigLabel(s.name)}
                <span class="sig-pill" class:bullish={lbl.bullish} class:bearish={!lbl.bullish}>
                  <span class="sig-arrow">{lbl.bullish ? '▲' : '▼'}</span>
                  {lbl.text}
                  <span class="sig-date">{s.date.slice(5)}</span>
                </span>
              {/each}
            </div>
          </div>
        {:else}
          <div class="sig-group">
            <span class="sig-code" style="color:{COLORS[ci % COLORS.length]}">{code}</span>
            <span class="sig-none">近 14 日無訊號</span>
          </div>
        {/if}
      {/each}
    </div>
  {:else if codes.length === 0}
    <p class="status">請輸入股票代碼開始比較（最多 5 檔）</p>
  {/if}
</div>

{#if pickerOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="overlay" on:click={() => (pickerOpen = false)}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="picker-modal" on:click|stopPropagation>
      <div class="picker-header">
        <span>從投機訊號清單選取（最多 5 檔）</span>
        <button class="close-btn" on:click={() => (pickerOpen = false)}>✕</button>
      </div>
      {#if pickerLoading}
        <div class="picker-loading"><LoadingSpinner /></div>
      {:else if pickerRows.length === 0}
        <p class="picker-empty">尚無投機訊號快照</p>
      {:else}
        <div class="picker-col-header">
          <span class="picker-col-check"></span>
          <span class="picker-col-code">代碼</span>
          <span class="picker-col-name">名稱</span>
          <span class="picker-col-score">訊號分數</span>
        </div>
        <div class="picker-list">
          {#each pickerRows as row}
            {@const checked = pickerSelected.has(row.code)}
            {@const disabled = !checked && pickerSelected.size >= 5}
            {@const scoreColor =
              row.score >= 7 ? '#60a5fa' :
              row.score >= 4 ? '#4ade80' :
              row.score >= 1 ? '#facc15' : '#f87171'}
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div
              class="picker-row"
              class:checked
              class:disabled
              on:click={() => !disabled && togglePicker(row.code)}
            >
              <input
                type="checkbox"
                {checked}
                {disabled}
                on:change={() => togglePicker(row.code)}
                on:click|stopPropagation
              />
              <span class="picker-code">{row.code}</span>
              <span class="picker-name">{row.name}</span>
              <span class="picker-score" style="color:{scoreColor}">{row.score}</span>
            </div>
          {/each}
        </div>
      {/if}
      <div class="picker-footer">
        <span class="picker-hint">已選 {pickerSelected.size} / 5</span>
        <button class="btn" on:click={confirmPicker}>確認</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page { padding: 24px; }
  h1 { color: #4ade80; font-size: 28px; margin: 0 0 20px 0; }
  h3 { color: #e5e7eb; margin: 0 0 12px 0; font-size: 14px; }

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

  .sig-group { margin-bottom: 12px; display: flex; align-items: flex-start; gap: 10px; flex-wrap: wrap; }
  .sig-code { font-weight: bold; font-size: 13px; flex-shrink: 0; padding-top: 3px; min-width: 44px; }
  .sig-pills { display: flex; flex-wrap: wrap; gap: 6px; }
  .sig-pill {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 12px; padding: 3px 8px; border-radius: 12px;
    border: 1px solid;
  }
  .sig-pill.bullish { color: #4ade80; border-color: #4ade8055; background: #4ade8011; }
  .sig-pill.bearish { color: #f87171; border-color: #f8717155; background: #f8717111; }
  .sig-arrow { font-size: 10px; }
  .sig-date { color: #666; font-size: 11px; margin-left: 2px; }
  .sig-none { font-size: 12px; color: #555; padding-top: 4px; }

  .status { color: #666; }
  .err { color: #f87171; }

  .btn-secondary {
    background: #3b3b3b; color: #fff; border: 1px solid #555;
    padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px;
  }
  .btn-secondary:hover { background: #4b4b4b; }

  .overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.6);
    display: flex; align-items: center; justify-content: center; z-index: 100;
  }
  .picker-modal {
    background: #1a1a1a; border: 1px solid #333; border-radius: 8px;
    width: 480px; max-height: 70vh; display: flex; flex-direction: column;
  }
  .picker-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 14px 16px; border-bottom: 1px solid #333; color: #fff; font-size: 14px;
  }
  .close-btn { background: none; border: none; color: #888; cursor: pointer; font-size: 18px; }
  .picker-loading { padding: 24px; display: flex; justify-content: center; }
  .picker-empty { color: #666; padding: 24px; text-align: center; }
  .picker-list { overflow-y: auto; flex: 1; }
  .picker-row {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px; cursor: pointer; border-bottom: 1px solid #222;
    transition: background 0.1s;
  }
  .picker-row:hover:not(.disabled) { background: #252525; }
  .picker-row.checked { background: #1e3a2a; }
  .picker-row.disabled { opacity: 0.4; cursor: default; }
  .picker-code { font-size: 13px; font-weight: bold; color: #fff; width: 56px; flex-shrink: 0; }
  .picker-name { font-size: 13px; color: #a1a1a1; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .picker-score { font-size: 12px; font-weight: bold; flex-shrink: 0; min-width: 52px; text-align: right; }

  .picker-col-header {
    display: flex; align-items: center; gap: 10px;
    padding: 6px 16px; background: #111; border-bottom: 1px solid #333;
    font-size: 11px; color: #555;
  }
  .picker-col-check { width: 16px; flex-shrink: 0; }
  .picker-col-code { width: 56px; flex-shrink: 0; }
  .picker-col-name { flex: 1; }
  .picker-col-score { min-width: 52px; text-align: right; flex-shrink: 0; }
  .picker-footer {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 16px; border-top: 1px solid #333;
  }
  .picker-hint { color: #666; font-size: 13px; }
</style>
