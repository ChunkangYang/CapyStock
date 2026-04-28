<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts';
  import type { PriceBar } from '$lib/types';

  export let prices: PriceBar[] = [];
  export let smaData: Record<string, { date: string; value: number | null }[]> = {};
  export let emaData: Record<string, { date: string; value: number | null }[]> = {};
  export let bbData: { upper: { date: string; value: number | null }[]; mid: { date: string; value: number | null }[]; lower: { date: string; value: number | null }[] } | null = null;

  // toolbar toggles
  export let showSma5 = false;
  export let showSma20 = true;
  export let showSma60 = false;
  export let showSma120 = false;
  export let showEma12 = false;
  export let showEma26 = false;
  export let showBB = false;

  const SMA_COLORS: Record<string, string> = {
    sma_5: '#facc15', sma_20: '#60a5fa', sma_60: '#f97316', sma_120: '#e879f9',
  };
  const EMA_COLORS: Record<string, string> = { ema_12: '#4ade80', ema_26: '#f87171' };
  const BB_COLOR = '#a1a1a1';

  let container: HTMLDivElement;
  let chart: IChartApi | null = null;
  let overlaySeriesMap: Map<string, ISeriesApi<'Line'>> = new Map();

  function makeLineData(arr: { date: string; value: number | null }[]) {
    return arr.filter(d => d.value != null).map(d => ({ time: d.date as any, value: d.value as number }));
  }

  function addOrRemove(key: string, data: { date: string; value: number | null }[], color: string, show: boolean) {
    if (!chart) return;
    if (show) {
      if (!overlaySeriesMap.has(key)) {
        const s = chart.addLineSeries({ color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(makeLineData(data));
        overlaySeriesMap.set(key, s);
      }
    } else {
      if (overlaySeriesMap.has(key)) {
        chart.removeSeries(overlaySeriesMap.get(key)!);
        overlaySeriesMap.delete(key);
      }
    }
  }

  $: if (chart) {
    addOrRemove('sma_5', smaData['sma_5'] ?? [], SMA_COLORS.sma_5, showSma5);
    addOrRemove('sma_20', smaData['sma_20'] ?? [], SMA_COLORS.sma_20, showSma20);
    addOrRemove('sma_60', smaData['sma_60'] ?? [], SMA_COLORS.sma_60, showSma60);
    addOrRemove('sma_120', smaData['sma_120'] ?? [], SMA_COLORS.sma_120, showSma120);
    addOrRemove('ema_12', emaData['ema_12'] ?? [], EMA_COLORS.ema_12, showEma12);
    addOrRemove('ema_26', emaData['ema_26'] ?? [], EMA_COLORS.ema_26, showEma26);
    if (bbData) {
      addOrRemove('bb_upper', bbData.upper, BB_COLOR, showBB);
      addOrRemove('bb_mid', bbData.mid, '#888', showBB);
      addOrRemove('bb_lower', bbData.lower, BB_COLOR, showBB);
    }
  }

  onMount(() => {
    if (!container || !prices.length) return;

    chart = createChart(container, {
      layout: { background: { color: '#1a1a1a' }, textColor: '#888' },
      width: container.clientWidth,
      height: 360,
      timeScale: { timeVisible: true, secondsVisible: false },
      grid: { vertLines: { color: '#222' }, horzLines: { color: '#222' } },
    });

    const candle = chart.addCandlestickSeries({
      upColor: '#4ade80', downColor: '#f87171',
      borderUpColor: '#4ade80', borderDownColor: '#f87171',
      wickUpColor: '#4ade80', wickDownColor: '#f87171',
    });
    candle.setData(prices.map(p => ({ time: p.date as any, open: p.open, high: p.high, low: p.low, close: p.close })));

    const ro = new ResizeObserver(() => {
      if (chart && container) chart.resize(container.clientWidth, 360);
    });
    ro.observe(container);

    return () => { ro.disconnect(); };
  });

  onDestroy(() => { if (chart) { chart.remove(); chart = null; } });
</script>

<div bind:this={container} class="chart-container"></div>

<style>
  .chart-container { width: 100%; }
</style>
