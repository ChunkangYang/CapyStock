<script lang="ts">
  import { onMount } from 'svelte';
  // @ts-ignore – $app/stores types resolved at SvelteKit build time
  import { page } from '$app/stores';
  import { api } from '$lib/api';
  import IndicatorOverlay from '$lib/components/IndicatorOverlay.svelte';
  import RSIPanel from '$lib/components/RSIPanel.svelte';
  import MACDPanel from '$lib/components/MACDPanel.svelte';
  import FlowBarChart from '$lib/components/FlowBarChart.svelte';
  import MarginLineChart from '$lib/components/MarginLineChart.svelte';
  import SignalTimeline from '$lib/components/SignalTimeline.svelte';
  import ConditionGauge from '$lib/components/ConditionGauge.svelte';
  import FavoriteToggle from '$lib/components/FavoriteToggle.svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
  import { cacheGet, cacheSet, cacheClear, cacheTimestamp, formatCacheAge } from '$lib/utils/signalsCache';
  import type { SignalResult, PriceBar, FlowRow, MarginRow, EdinetEvent, Simulation } from '$lib/types';

  const code = $page.params.code;

  // 進場到帳本
  let showEntryModal = false;
  let ledgers: Simulation[] = [];
  let ledgersLoading = false;
  let selectedLedgerId = '';
  let entryShares: number = 100;
  let entryPrice: number = 0;
  let entryDate: string = new Date().toISOString().split('T')[0];
  let entrySubmitting = false;
  let entryMessage = '';
  let entryError = '';

  async function openEntryModal() {
    if (!signal) return;
    entryPrice = signal.latest_price ?? 0;
    showEntryModal = true;
    entryError = '';
    entryMessage = '';
    ledgersLoading = true;
    try {
      const all = await api<Simulation[]>(`/simulation`);
      ledgers = all.filter(s => s.config.kind === 'paper' && s.status !== 'completed' && s.status !== 'failed');
      if (ledgers.length > 0 && !selectedLedgerId) {
        selectedLedgerId = ledgers[0].id;
      }
    } catch (e) {
      entryError = e instanceof Error ? e.message : '讀取帳本失敗';
    } finally {
      ledgersLoading = false;
    }
  }

  async function submitEntry() {
    if (!signal || !selectedLedgerId) {
      entryError = '請選擇帳本';
      return;
    }
    if (entryShares <= 0 || entryPrice <= 0) {
      entryError = '股數和價格必須 > 0';
      return;
    }
    entrySubmitting = true;
    entryError = '';
    try {
      const params = new URLSearchParams({
        code: signal.code,
        name: signal.name,
        shares: String(entryShares),
        entry_price: String(entryPrice),
        entry_date: entryDate,
      });
      await api(`/simulation/${selectedLedgerId}/open-position?${params}`, {
        method: 'POST',
      });
      entryMessage = `✓ 已加入帳本（${entryShares} 股 @ ¥${entryPrice}）`;
      setTimeout(() => { showEntryModal = false; }, 1200);
    } catch (e) {
      entryError = e instanceof Error ? e.message : '進場失敗';
    } finally {
      entrySubmitting = false;
    }
  }
  let signal: SignalResult | null = null;
  let prices: PriceBar[] = [];
  let flows: FlowRow[] = [];
  let margins: MarginRow[] = [];
  let edinet: EdinetEvent[] = [];
  let loading = true;
  let refreshing = false;
  let error = '';
  let cacheTs: number | null = null;

  const DETAIL_KEY = `signals_detail:${code}`;

  // indicator data
  type IndicatorSeries = { name: string; dates: string[]; values: (number | null)[] };
  type IndicatorBundle = { code: string; series: Record<string, IndicatorSeries>; signals: any[] };
  let indBundle: IndicatorBundle | null = null;

  // toolbar toggles
  let showSma5 = false;
  let showSma20 = true;
  let showSma60 = false;
  let showSma120 = false;
  let showEma12 = false;
  let showEma26 = false;
  let showBB = false;
  let showRSI = false;
  let showMACD = false;

  function seriesAsDateValue(s: IndicatorSeries | undefined): { date: string; value: number | null }[] {
    if (!s) return [];
    return s.dates.map((d, i) => ({ date: d, value: s.values[i] }));
  }

  $: smaData = {
    sma_5: seriesAsDateValue(indBundle?.series['sma_5']),
    sma_20: seriesAsDateValue(indBundle?.series['sma_20']),
    sma_60: seriesAsDateValue(indBundle?.series['sma_60']),
    sma_120: seriesAsDateValue(indBundle?.series['sma_120']),
  };
  $: emaData = {
    ema_12: seriesAsDateValue(indBundle?.series['ema_12']),
    ema_26: seriesAsDateValue(indBundle?.series['ema_26']),
  };
  $: bbData = indBundle ? {
    upper: seriesAsDateValue(indBundle.series['bb_upper']),
    mid: seriesAsDateValue(indBundle.series['bb_mid']),
    lower: seriesAsDateValue(indBundle.series['bb_lower']),
  } : null;
  $: rsiData = seriesAsDateValue(indBundle?.series['rsi_14']);
  $: macdLineData = seriesAsDateValue(indBundle?.series['macd']);
  $: macdSignalData = seriesAsDateValue(indBundle?.series['macd_signal']);
  $: macdHistData = seriesAsDateValue(indBundle?.series['macd_hist']);

  type DetailBundle = {
    signal: SignalResult;
    prices: PriceBar[];
    flows: FlowRow[];
    margins: MarginRow[];
    edinet: EdinetEvent[];
    indBundle: IndicatorBundle;
  };

  async function fetchAll(): Promise<DetailBundle> {
    const [s, p, f, m, e, ind] = await Promise.all([
      api<SignalResult>(`/signals/${code}`),
      api<PriceBar[]>(`/signals/${code}/price?days=120`),
      api<FlowRow[]>(`/signals/${code}/flow?days=60`),
      api<MarginRow[]>(`/signals/${code}/margin?weeks=20`),
      api<EdinetEvent[]>(`/signals/${code}/edinet?days=30`),
      api<IndicatorBundle>(`/indicators/${code}?days=120&include=sma_5,sma_20,sma_60,sma_120,ema_12,ema_26,rsi_14,macd,macd_signal,macd_hist,bb_upper,bb_mid,bb_lower`),
    ]);
    return { signal: s, prices: p, flows: f, margins: m, edinet: e, indBundle: ind };
  }

  function applyBundle(b: DetailBundle) {
    signal = b.signal;
    prices = b.prices;
    flows = b.flows;
    margins = b.margins;
    edinet = b.edinet;
    indBundle = b.indBundle;
  }

  onMount(async () => {
    try {
      const cached = cacheGet<DetailBundle>(DETAIL_KEY);
      if (cached) {
        applyBundle(cached);
        cacheTs = cacheTimestamp(DETAIL_KEY);
      } else {
        const bundle = await fetchAll();
        cacheSet(DETAIL_KEY, bundle);
        cacheTs = cacheTimestamp(DETAIL_KEY);
        applyBundle(bundle);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : '讀取資料失敗';
    } finally {
      loading = false;
    }
  });

  async function refreshData() {
    refreshing = true;
    cacheClear(DETAIL_KEY);
    try {
      const bundle = await fetchAll();
      cacheSet(DETAIL_KEY, bundle);
      cacheTs = cacheTimestamp(DETAIL_KEY);
      applyBundle(bundle);
    } catch (e) {
      error = e instanceof Error ? e.message : '更新失敗';
    } finally {
      refreshing = false;
    }
  }

  $: indSignals = (indBundle?.signals ?? []).slice(0, 15);
  $: accumulationAlert = signal?.alerts.find(a => a.alert_type === 'accumulation');
  $: stopLossAlert = signal?.alerts.find(a => a.alert_type === 'stop_loss');
  $: exitAlert = signal?.alerts.find(a => a.alert_type === 'exit');

  function strengthColor(s: string): string {
    if (s === 'strong') return '#4ade80';
    if (s === 'moderate') return '#facc15';
    return '#a1a1a1';
  }
</script>

<div class="detail-page">
  {#if loading}
    <LoadingSpinner size="lg" label="載入個股資料中…" />
  {:else if error}
    <p class="error">{error}</p>
  {:else if signal}
    <div class="header">
      <div class="info">
        <span class="code">{signal.code}</span>
        <span class="name">{signal.name}</span>
        <span class="price">{signal.latest_price?.toFixed(0) ?? 'N/A'}</span>
      </div>
      <div class="actions">
        {#if cacheTs !== null}
          <span class="cache-age">上次更新：{formatCacheAge(cacheTs)}</span>
        {/if}
        <button
          class="btn btn-refresh"
          class:spinning={refreshing}
          disabled={refreshing}
          title="清除快取，重新抓取最新資料"
          on:click={refreshData}
        >↻ 更新</button>
        <FavoriteToggle {code} name={signal.name} tag="speculative" />
        <a href="/compare?codes={code}" class="btn btn-secondary">對比模式</a>
        <button class="btn btn-entry" on:click={openEntryModal}>📥 進場到帳本</button>
      </div>
    </div>

    {#if showEntryModal}
      <div class="modal-backdrop" on:click={() => (showEntryModal = false)} role="presentation">
        <div class="modal" on:click|stopPropagation role="dialog" aria-modal="true">
          <h3>進場 {signal.code} {signal.name}</h3>

          {#if ledgersLoading}
            <p>載入帳本中...</p>
          {:else if ledgers.length === 0}
            <p class="warn">
              沒有可用的模擬帳本。
              <a href="/simulation/ledger/new">先建立一個帳本 →</a>
            </p>
          {:else}
            <div class="form-row">
              <label>選擇帳本</label>
              <select bind:value={selectedLedgerId}>
                {#each ledgers as l}
                  <option value={l.id}>{l.name}（現金 ¥{Math.round(l.state.cash).toLocaleString()}）</option>
                {/each}
              </select>
            </div>
            <div class="form-row">
              <label>進場日</label>
              <input type="date" bind:value={entryDate} />
            </div>
            <div class="form-row">
              <label>股數</label>
              <input type="number" bind:value={entryShares} min="1" step="100" />
            </div>
            <div class="form-row">
              <label>成交價 (JPY)</label>
              <input type="number" bind:value={entryPrice} min="0" step="1" />
              <small>已預填當前價 ¥{signal.latest_price?.toFixed(0) ?? '?'}</small>
            </div>
            <div class="form-row">
              <strong>預估成本：¥{Math.round(entryShares * entryPrice * 1.002).toLocaleString()}</strong>
              <small>含 0.2% 手續費 + 滑價（實際以帳本設定為準）</small>
            </div>
            {#if entryError}<div class="msg-error">{entryError}</div>{/if}
            {#if entryMessage}<div class="msg-ok">{entryMessage}</div>{/if}
            <div class="modal-actions">
              <button class="btn btn-secondary" on:click={() => (showEntryModal = false)}>取消</button>
              <button class="btn btn-entry" on:click={submitEntry} disabled={entrySubmitting}>
                {entrySubmitting ? '送出中...' : '確認進場'}
              </button>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <div class="content">
      <div class="charts">
        <!-- Indicator toolbar -->
        <div class="toolbar">
          <span class="toolbar-label">SMA：</span>
          <label><input type="checkbox" bind:checked={showSma5} /> 5</label>
          <label><input type="checkbox" bind:checked={showSma20} /> 20</label>
          <label><input type="checkbox" bind:checked={showSma60} /> 60</label>
          <label><input type="checkbox" bind:checked={showSma120} /> 120</label>
          <span class="toolbar-sep">｜</span>
          <span class="toolbar-label">EMA：</span>
          <label><input type="checkbox" bind:checked={showEma12} /> 12</label>
          <label><input type="checkbox" bind:checked={showEma26} /> 26</label>
          <span class="toolbar-sep">｜</span>
          <label><input type="checkbox" bind:checked={showBB} /> 布林通道</label>
          <span class="toolbar-sep">｜</span>
          <label><input type="checkbox" bind:checked={showRSI} /> RSI</label>
          <label><input type="checkbox" bind:checked={showMACD} /> MACD</label>
        </div>

        <!-- K 線 + 指標 overlay -->
        {#if prices.length}
          <div class="chart-container">
            <h3>K 線（120 日）</h3>
            <IndicatorOverlay
              {prices}
              {smaData} {emaData} {bbData}
              {showSma5} {showSma20} {showSma60} {showSma120}
              {showEma12} {showEma26} {showBB}
            />
          </div>
        {/if}

        <!-- RSI 子圖（可摺疊） -->
        {#if showRSI && rsiData.length}
          <div class="chart-container sub-chart">
            <RSIPanel {rsiData} />
          </div>
        {/if}

        <!-- MACD 子圖 -->
        {#if showMACD && macdLineData.length}
          <div class="chart-container sub-chart">
            <MACDPanel macdData={macdLineData} signalData={macdSignalData} histData={macdHistData} />
          </div>
        {/if}

        {#if flows.length}
          <div class="chart-container">
            <h3>投資部門別買賣超</h3>
            <FlowBarChart {flows} />
          </div>
        {/if}

        {#if margins.length}
          <div class="chart-container">
            <h3>信用殘</h3>
            <MarginLineChart {margins} />
          </div>
        {/if}

        <div class="chart-container">
          <h3>訊號時間軸</h3>
          <SignalTimeline alerts={signal.alerts} />
        </div>
      </div>

      <div class="sidebar">
        <ConditionGauge conditions={signal.conditions} exitAlert={exitAlert} />

        <div class="card signal-card" class:active={signal.accumulation_signal}>
          <h4>吃貨訊號</h4>
          <p class="signal-status" class:green={signal.accumulation_signal}>
            {signal.accumulation_signal ? '✓ 是' : '✗ 否'}
          </p>
          {#if accumulationAlert}
            <p class="signal-detail">{accumulationAlert.message}</p>
          {:else}
            <p class="signal-hint">判斷條件：外資或法人連續買超（≥2期），同期融資餘額下降</p>
          {/if}
        </div>

        <div class="card signal-card" class:warn={signal.stop_loss_triggered}>
          <h4>停損狀態</h4>
          <p class="signal-status" class:red={signal.stop_loss_triggered}>
            {signal.stop_loss_triggered ? '⚠ 已觸發' : '✓ 未觸發'}
          </p>
          {#if stopLossAlert}
            <p class="signal-detail">{stopLossAlert.message}</p>
          {:else}
            <p class="signal-hint">判斷條件：連續 2 日收盤低於停損錨點（主力成本或起始價 ×95%）</p>
          {/if}
        </div>

        {#if signal.trailing_stop_stage}
          <div class="card signal-card" class:warn={signal.trailing_stop_triggered}>
            <h4>移動停損（Chandelier）</h4>
            <p class="trailing-stage">
              <span class="stage-badge" class:s1={signal.trailing_stop_stage === 1} class:s2={signal.trailing_stop_stage === 2} class:s3={signal.trailing_stop_stage === 3}>
                Stage {signal.trailing_stop_stage}
              </span>
              <span class="stage-name">
                {#if signal.trailing_stop_stage === 1}初始停損{:else if signal.trailing_stop_stage === 2}保本{:else}最大化獲利{/if}
              </span>
            </p>
            <p class="trailing-price" class:red={signal.trailing_stop_triggered}>
              停損價：<b>{signal.trailing_stop_price?.toLocaleString(undefined, {maximumFractionDigits: 0})}</b>
              {#if signal.trailing_stop_triggered}<span class="trigger-mark">⚠ 已觸發</span>{/if}
            </p>
            {#if signal.latest_price && signal.trailing_stop_price}
              <p class="trailing-buffer">
                當前 {signal.latest_price.toLocaleString(undefined, {maximumFractionDigits: 0})}
                距停損 <b class:red={(signal.latest_price - signal.trailing_stop_price) / signal.trailing_stop_price < 0.02}>
                  {(((signal.latest_price - signal.trailing_stop_price) / signal.trailing_stop_price) * 100).toFixed(1)}%
                </b>
              </p>
            {/if}
            {#if signal.atr_14}
              <p class="signal-detail">ATR(14) = {signal.atr_14.toFixed(1)}</p>
            {/if}
            {#if signal.trailing_stop_anchor}
              <p class="signal-hint">{signal.trailing_stop_anchor}</p>
            {/if}
          </div>
        {/if}

        {#if signal.exit_warnings && signal.exit_warnings.length}
          <div class="card signal-card warn">
            <h4>減碼警示</h4>
            <ul class="warn-list">
              {#each signal.exit_warnings as w}
                <li>⚠ {w}</li>
              {/each}
            </ul>
            <p class="signal-hint">這些是技術破位訊號，建議減碼觀察（不強制砍倉）</p>
          </div>
        {/if}

        <!-- 指標訊號卡片 -->
        {#if indSignals.length}
          <div class="card">
            <h4>指標訊號（近 30 日）</h4>
            <div class="ind-signal-list">
              {#each indSignals as s}
                <div class="ind-sig-item">
                  <span class="ind-date">{s.date}</span>
                  <span class="ind-name">{s.name}</span>
                  <span class="ind-strength" style="color:{strengthColor(s.strength)}">{s.strength}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if edinet.length}
          <div class="card">
            <h4>EDINET 事件（30 日）</h4>
            <div class="edinet-list">
              {#each edinet as event}
                <div class="event-item">
                  <span class="date">{event.date}</span>
                  <span class="filer">{event.filer}</span>
                  <a href={event.pdf_url} target="_blank">{event.doc_type}</a>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if signal.notes.length}
          <div class="card">
            <h4>備註</h4>
            <ul>
              {#each signal.notes as note}
                <li>{note}</li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
    </div>
  {:else}
    <p>找不到該股票</p>
  {/if}
</div>

<style>
  .detail-page { padding: 24px; }

  .header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #2a2a2a;
  }
  .info { display: flex; gap: 16px; align-items: baseline; }
  .code { font-size: 18px; font-weight: bold; color: #fff; }
  .name { color: #a1a1a1; }
  .price { font-size: 20px; color: #4ade80; font-weight: bold; }
  .actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .cache-age { font-size: 12px; color: #666; }
  .btn { padding: 6px 14px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; }
  .btn-secondary { background: #333; color: #fff; border: 1px solid #555; }
  .btn-refresh { background: #1a1a1a; color: #ccc; border: 1px solid #444; transition: color 0.2s, border-color 0.2s; }
  .btn-refresh:hover:not(:disabled) { color: #4ade80; border-color: #4ade80; }
  .btn-refresh:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-refresh.spinning { animation: spin 0.7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .btn-entry { background: #4ade80; color: #0a0a0a; font-weight: 500; border: none; }
  .btn-entry:hover:not(:disabled) { background: #3dd66f; }
  .btn-entry:disabled { opacity: 0.5; cursor: wait; }

  .modal-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,0.7);
    display: flex; align-items: center; justify-content: center; z-index: 1000;
  }
  .modal {
    background: #1a1a1a; border: 1px solid #333; border-radius: 8px;
    padding: 24px; width: 420px; max-width: 90vw;
  }
  .modal h3 { color: #4ade80; margin: 0 0 16px; font-size: 16px; }
  .form-row { margin-bottom: 12px; }
  .form-row label { display: block; color: #a1a1a1; font-size: 12px; margin-bottom: 4px; }
  .form-row input, .form-row select {
    width: 100%; padding: 7px 10px; background: #0a0a0a; color: #fff;
    border: 1px solid #333; border-radius: 4px; font-size: 13px;
  }
  .form-row small { display: block; color: #666; font-size: 11px; margin-top: 4px; }
  .form-row strong { color: #4ade80; font-size: 14px; display: block; }
  .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
  .msg-error { background: #7f1d1d; color: #fca5a5; padding: 8px; border-radius: 4px; font-size: 12px; margin: 8px 0; }
  .msg-ok { background: #14532d; color: #bbf7d0; padding: 8px; border-radius: 4px; font-size: 12px; margin: 8px 0; }
  .warn { color: #fbbf24; font-size: 13px; }
  .warn a { color: #4ade80; }

  .toolbar {
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
    background: #1a1a1a; padding: 10px 16px; border-radius: 8px; margin-bottom: 4px;
    font-size: 13px; color: #a1a1a1;
  }
  .toolbar label { display: flex; align-items: center; gap: 4px; cursor: pointer; color: #ccc; }
  .toolbar-label { color: #666; }
  .toolbar-sep { color: #444; }

  .content { display: grid; grid-template-columns: 1fr 0.4fr; gap: 24px; }
  .charts { display: flex; flex-direction: column; gap: 16px; }
  .chart-container { background: #1a1a1a; padding: 16px; border-radius: 8px; }
  .sub-chart { padding: 8px 16px; }
  .chart-container h3 { color: #fff; margin: 0 0 12px 0; font-size: 14px; }

  .sidebar { display: flex; flex-direction: column; gap: 16px; }
  .card { background: #1a1a1a; padding: 16px; border-radius: 8px; }
  .card h4 { color: #fff; margin: 0 0 8px 0; font-size: 13px; }
  .card p { color: #4ade80; margin: 0; }

  .signal-card { border: 1px solid transparent; transition: border-color 0.2s; }
  .signal-card.active { border-color: rgba(74, 222, 128, 0.3); }
  .signal-card.warn { border-color: rgba(248, 113, 113, 0.3); }
  .signal-status { font-size: 15px; font-weight: bold; margin: 0 0 8px 0 !important; }
  .signal-status.green { color: #4ade80; }
  .signal-status.red { color: #f87171; }
  .signal-detail { font-size: 11px; color: #a1a1a1; margin: 0 !important; line-height: 1.5; }
  .signal-hint { font-size: 11px; color: #555; margin: 0 !important; line-height: 1.5; font-style: italic; }

  .trailing-stage { font-size: 13px; margin: 0 0 8px 0 !important; }
  .stage-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-right: 6px; }
  .stage-badge.s1 { background: rgba(248, 113, 113, 0.15); color: #f87171; }
  .stage-badge.s2 { background: rgba(250, 204, 21, 0.15); color: #facc15; }
  .stage-badge.s3 { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
  .stage-name { color: #ccc; font-size: 12px; }
  .trailing-price { font-size: 13px; color: #ccc; margin: 0 0 4px 0 !important; }
  .trailing-price b { color: #fff; }
  .trailing-price.red b { color: #f87171; }
  .trigger-mark { color: #f87171; margin-left: 8px; font-weight: bold; }
  .trailing-buffer { font-size: 12px; color: #888; margin: 0 0 4px 0 !important; }
  .trailing-buffer b { color: #4ade80; }
  .trailing-buffer b.red { color: #f87171; }
  .warn-list { margin: 0 0 8px 0; padding-left: 16px; color: #facc15; font-size: 12px; line-height: 1.6; }
  .warn-list li { margin-bottom: 2px; }

  .ind-signal-list { display: flex; flex-direction: column; gap: 6px; }
  .ind-sig-item { display: flex; gap: 6px; font-size: 12px; align-items: center; }
  .ind-date { color: #666; min-width: 70px; }
  .ind-name { color: #ccc; flex: 1; }
  .ind-strength { font-size: 11px; font-weight: 600; }

  .edinet-list { display: flex; flex-direction: column; gap: 8px; }
  .event-item { display: flex; flex-direction: column; gap: 4px; padding: 8px; background: #0a0a0a; border-radius: 4px; font-size: 12px; }
  .date { color: #888; }
  .filer { color: #a1a1a1; }
  .event-item a { color: #4ade80; text-decoration: none; }

  .card ul { margin: 0; padding: 0; list-style: none; }
  .card li { color: #a1a1a1; font-size: 12px; padding: 4px 0; }
  .error { color: #f87171; }

  @media (max-width: 1200px) { .content { grid-template-columns: 1fr; } }
</style>
