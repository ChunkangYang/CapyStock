<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createChart, type IChartApi } from 'lightweight-charts';

  export let macdData: { date: string; value: number | null }[] = [];
  export let signalData: { date: string; value: number | null }[] = [];
  export let histData: { date: string; value: number | null }[] = [];

  let container: HTMLDivElement;
  let chart: IChartApi | null = null;

  onMount(() => {
    if (!container) return;

    chart = createChart(container, {
      layout: { background: { color: '#1a1a1a' }, textColor: '#888' },
      width: container.clientWidth,
      height: 140,
      timeScale: { timeVisible: true, secondsVisible: false },
      grid: { vertLines: { color: '#222' }, horzLines: { color: '#222' } },
    });

    const macdSeries = chart.addLineSeries({ color: '#60a5fa', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    macdSeries.setData(macdData.filter(d => d.value != null).map(d => ({ time: d.date as any, value: d.value as number })));

    const signalSeries = chart.addLineSeries({ color: '#f97316', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    signalSeries.setData(signalData.filter(d => d.value != null).map(d => ({ time: d.date as any, value: d.value as number })));

    const histSeries = chart.addHistogramSeries({
      color: '#4ade80',
      priceLineVisible: false,
      lastValueVisible: false,
    });
    histSeries.setData(
      histData.filter(d => d.value != null).map(d => ({
        time: d.date as any,
        value: d.value as number,
        color: (d.value as number) >= 0 ? '#4ade80' : '#f87171',
      }))
    );

    const ro = new ResizeObserver(() => { if (chart && container) chart.resize(container.clientWidth, 140); });
    ro.observe(container);
    return () => { ro.disconnect(); };
  });

  onDestroy(() => { if (chart) { chart.remove(); chart = null; } });
</script>

<div class="macd-wrap">
  <div class="label">MACD(12,26,9)</div>
  <div bind:this={container}></div>
</div>

<style>
  .macd-wrap { width: 100%; }
  .label { font-size: 12px; color: #888; padding: 4px 0; }
</style>
