<script lang="ts">
  import { onMount } from 'svelte';
  // @ts-ignore – $app/stores types resolved at SvelteKit build time
  import { page } from '$app/stores';
  // @ts-ignore
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  type FundamentalMetric = { metric: string; score: string; note: string };
  type FundamentalReport = { code: string; name: string; overall: string; metrics: FundamentalMetric[] };
  type DpsRow = { year: number; dps: number | null };
  type Bundle = {
    codes: string[];
    fundamentals: Record<string, FundamentalReport | null>;
    dividend_history: Record<string, DpsRow[]>;
    radar_normalized: Record<string, Record<string, float>>;
  };
  type DividendScanRow = { code: string; name: string; overall: string; est_yield: number | null };

  const COLORS = ['#4ade80', '#60a5fa', '#f97316', '#e879f9', '#facc15'];
  const SCORE_COLOR: Record<string, string> = { PASS: '#4ade80', WARN: '#facc15', FAIL: '#f87171', 'N/A': '#666' };
  const METRIC_ZH: Record<string, string> = {
    sales:        '營業收入',
    eps:          '每股盈餘（EPS）',
    op_margin:    '營業利益率',
    equity_ratio: '自有資本比率',
    op_cf:        '營業現金流',
    cash:         '現金及等價物',
    dps:          '每股配息（DPS）',
    payout:       '配息率',
  };

  let inputCode = '';
  let codes: string[] = [];
  let bundle: Bundle | null = null;
  let loading = false;
  let error = '';

  // picker state
  let pickerOpen = false;
  let pickerLoading = false;
  let pickerRows: DividendScanRow[] = [];
  let pickerSelected: Set<string> = new Set();

  onMount(() => {
    const params = new URLSearchParams($page.url.search);
    const c = params.get('codes');
    if (c) codes = c.split(',').filter(Boolean);
    if (codes.length) load();
  });

  async function load() {
    if (!codes.length) return;
    loading = true; error = ''; bundle = null;
    try {
      bundle = await api<Bundle>(`/compare/dividend?codes=${codes.join(',')}`);
    } catch (e) {
      error = e instanceof Error ? e.message : '讀取失敗';
    } finally {
      loading = false;
    }
    goto(`/dividend/compare?codes=${codes.join(',')}`, { replaceState: true });
  }

  function addCode() {
    const c = inputCode.trim().toUpperCase();
    if (!c || codes.includes(c) || codes.length >= 5) return;
    codes = [...codes, c]; inputCode = ''; load();
  }
  function removeCode(c: string) {
    codes = codes.filter(x => x !== c);
    if (codes.length) load(); else bundle = null;
  }
  function onKeydown(e: KeyboardEvent) { if (e.key === 'Enter') addCode(); }

  async function openPicker() {
    pickerOpen = true;
    pickerSelected = new Set(codes);
    if (pickerRows.length === 0) {
      pickerLoading = true;
      try {
        pickerRows = await api<DividendScanRow[]>('/scan/dividend');
        pickerRows = pickerRows.sort((a, b) => (b.est_yield ?? 0) - (a.est_yield ?? 0));
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

  // DPS bar chart helpers
  function allYears(bundle: Bundle): number[] {
    const s = new Set<number>();
    for (const rows of Object.values(bundle.dividend_history)) for (const r of rows) s.add(r.year);
    return [...s].sort();
  }
  function dpsMap(rows: DpsRow[]): Record<number, number | null> {
    return Object.fromEntries(rows.map(r => [r.year, r.dps]));
  }
  function maxDps(bundle: Bundle): number {
    let m = 0;
    for (const rows of Object.values(bundle.dividend_history))
      for (const r of rows) if (r.dps != null && r.dps > m) m = r.dps;
    return m || 1;
  }

  // Radar helpers
  function radarMetrics(bundle: Bundle): string[] {
    const all = new Set<string>();
    for (const r of Object.values(bundle.radar_normalized)) for (const k of Object.keys(r)) all.add(k);
    return [...all];
  }
  function radarPoints(scores: Record<string, float>, metrics: string[], cx: number, cy: number, r: number): string {
    const n = metrics.length;
    return metrics.map((m, i) => {
      const angle = (2 * Math.PI * i / n) - Math.PI / 2;
      const val = (scores[m] ?? 50) / 100;
      const x = cx + r * val * Math.cos(angle);
      const y = cy + r * val * Math.sin(angle);
      return `${x},${y}`;
    }).join(' ');
  }
  function labelPos(i: number, n: number, cx: number, cy: number, r: number): { x: number; y: number } {
    const angle = (2 * Math.PI * i / n) - Math.PI / 2;
    return { x: cx + (r + 20) * Math.cos(angle), y: cy + (r + 20) * Math.sin(angle) };
  }
</script>

<div class="page">
  <h2>金雞高股息對比</h2>

  <div class="controls">
    <div class="chip-bar">
      {#each codes as c, i}
        <span class="chip" style="border-color:{COLORS[i % COLORS.length]}">
          {c}
          <button class="remove" on:click={() => removeCode(c)}>×</button>
        </span>
      {/each}
      {#if codes.length < 5}
        <input class="code-input" placeholder="輸入代碼 Enter" bind:value={inputCode} on:keydown={onKeydown} />
        <button class="btn" on:click={addCode}>加入</button>
        <button class="btn btn-secondary" on:click={openPicker}>從清單選取</button>
      {/if}
    </div>
  </div>

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <p class="err">{error}</p>
  {:else if bundle}
    <!-- 雷達圖 -->
    {@const metrics = radarMetrics(bundle)}
    {#if metrics.length > 0}
      <div class="card">
        <h3>基本面雷達圖</h3>
        <div class="radar-wrap">
          <svg viewBox="0 0 400 400" class="radar-svg">
            <!-- 同心圓 -->
            {#each [0.25, 0.5, 0.75, 1.0] as r}
              <circle cx="200" cy="200" r={r * 150} fill="none" stroke="#333" stroke-width="1" />
            {/each}
            <!-- 軸線 -->
            {#each metrics as m, i}
              {@const angle = (2 * Math.PI * i / metrics.length) - Math.PI / 2}
              <line x1="200" y1="200"
                x2={200 + 150 * Math.cos(angle)}
                y2={200 + 150 * Math.sin(angle)}
                stroke="#444" stroke-width="1" />
              {@const lp = labelPos(i, metrics.length, 200, 200, 150)}
              <text x={lp.x} y={lp.y} text-anchor="middle" dominant-baseline="middle" fill="#888" font-size="10">{METRIC_ZH[m] ?? m}</text>
            {/each}
            <!-- 各 code -->
            {#each bundle.codes as code, ci}
              {#if bundle.radar_normalized[code]}
                <polygon
                  points={radarPoints(bundle.radar_normalized[code], metrics, 200, 200, 150)}
                  fill={COLORS[ci % COLORS.length]}
                  fill-opacity="0.15"
                  stroke={COLORS[ci % COLORS.length]}
                  stroke-width="2"
                />
              {/if}
            {/each}
          </svg>
          <div class="legend">
            {#each bundle.codes as code, ci}
              <span style="color:{COLORS[ci % COLORS.length]}">■ {code}</span>
            {/each}
          </div>
        </div>
      </div>
    {/if}

    <!-- DPS 並排 bar -->
    {@const years = allYears(bundle)}
    {@const maxD = maxDps(bundle)}
    {#if years.length}
      <div class="card">
        <h3>DPS 歷史（年度配息）</h3>
        <div class="bar-chart">
          {#each years as yr}
            <div class="yr-group">
              <div class="bars">
                {#each bundle.codes as code, ci}
                  {@const val = dpsMap(bundle.dividend_history[code] ?? [])[yr]}
                  <div class="bar-wrap">
                    <div
                      class="bar"
                      style="height:{val != null ? (val / maxD * 120) : 0}px; background:{COLORS[ci % COLORS.length]}"
                      title="{code} {yr}: {val ?? 'N/A'}"
                    ></div>
                  </div>
                {/each}
              </div>
              <div class="yr-label">{yr}</div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- 指標明細表 -->
    {#if metrics.length}
      <div class="card">
        <h3>基本面指標明細</h3>
        <table class="detail-table">
          <thead>
            <tr>
              <th>指標</th>
              {#each bundle.codes as code}
                <th>{code}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each metrics as m}
              <tr>
                <td>{METRIC_ZH[m] ?? m}</td>
                {#each bundle.codes as code}
                  {@const rpt = bundle.fundamentals[code]}
                  {@const met = rpt?.metrics.find(x => x.metric === m)}
                  <td style="color:{SCORE_COLOR[met?.score ?? 'N/A']}">{met?.score ?? 'N/A'}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {:else if codes.length === 0}
    <p class="status">請輸入股票代碼開始比較</p>
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
        <span>從高股息掃描清單選取（最多 5 檔）</span>
        <button class="close-btn" on:click={() => (pickerOpen = false)}>✕</button>
      </div>
      {#if pickerLoading}
        <div class="picker-loading"><LoadingSpinner /></div>
      {:else if pickerRows.length === 0}
        <p class="picker-empty">尚無高股息掃描快照</p>
      {:else}
        <div class="picker-col-header">
          <span class="picker-col-check"></span>
          <span class="picker-col-code">代碼</span>
          <span class="picker-col-name">名稱</span>
          <span class="picker-col-overall">基本面</span>
          <span class="picker-col-yield">預估殖利率</span>
        </div>
        <div class="picker-list">
          {#each pickerRows as row}
            {@const checked = pickerSelected.has(row.code)}
            {@const disabled = !checked && pickerSelected.size >= 5}
            {@const overallColor =
              row.overall === 'STRONG'  ? '#60a5fa' :
              row.overall === 'HEALTHY' ? '#4ade80' :
              row.overall === 'CAUTION' ? '#facc15' :
              row.overall === 'RISKY'   ? '#f87171' : '#666'}
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
              <span class="picker-overall" style="color:{overallColor}">{row.overall}</span>
              <span class="picker-yield">{row.est_yield != null ? (row.est_yield * 100).toFixed(1) + '%' : '—'}</span>
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
  h2 { color: #fff; margin: 0 0 20px 0; }
  h3 { color: #fff; margin: 0 0 12px 0; font-size: 14px; }

  .controls { display: flex; gap: 16px; align-items: center; margin-bottom: 20px; flex-wrap: wrap; }
  .chip-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .chip { display: flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 16px; border: 1px solid; font-size: 13px; color: #fff; }
  .remove { background: none; border: none; color: #888; cursor: pointer; font-size: 16px; padding: 0 2px; }
  .code-input { background: #222; border: 1px solid #444; color: #fff; padding: 6px 10px; border-radius: 4px; font-size: 13px; width: 120px; }
  .btn { background: #4ade80; color: #000; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }

  .card { background: #1a1a1a; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
  .radar-wrap { display: flex; flex-direction: column; align-items: center; }
  .radar-svg { width: 320px; height: 320px; }
  .legend { display: flex; gap: 12px; font-size: 12px; margin-top: 8px; }

  .bar-chart { display: flex; gap: 4px; align-items: flex-end; overflow-x: auto; padding: 8px 0; }
  .yr-group { display: flex; flex-direction: column; align-items: center; gap: 4px; }
  .bars { display: flex; gap: 2px; align-items: flex-end; height: 130px; }
  .bar-wrap { display: flex; align-items: flex-end; height: 120px; }
  .bar { width: 12px; border-radius: 2px 2px 0 0; min-height: 0; transition: height 0.3s; }
  .yr-label { font-size: 11px; color: #666; }

  .detail-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .detail-table th, .detail-table td { border: 1px solid #333; padding: 8px 12px; text-align: center; }
  .detail-table th { background: #111; color: #a1a1a1; }
  .detail-table td:first-child { color: #a1a1a1; text-align: left; }

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
  .picker-overall { font-size: 12px; flex-shrink: 0; font-weight: bold; min-width: 60px; text-align: right; }
  .picker-yield { font-size: 12px; color: #4ade80; flex-shrink: 0; min-width: 52px; text-align: right; }

  .picker-col-header {
    display: flex; align-items: center; gap: 10px;
    padding: 6px 16px; background: #111; border-bottom: 1px solid #333;
    font-size: 11px; color: #555;
  }
  .picker-col-check { width: 16px; flex-shrink: 0; }
  .picker-col-code { width: 56px; flex-shrink: 0; }
  .picker-col-name { flex: 1; }
  .picker-col-overall { min-width: 60px; text-align: right; flex-shrink: 0; }
  .picker-col-yield { min-width: 52px; text-align: right; flex-shrink: 0; }
  .picker-footer {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 16px; border-top: 1px solid #333;
  }
  .picker-hint { color: #666; font-size: 13px; }
</style>
