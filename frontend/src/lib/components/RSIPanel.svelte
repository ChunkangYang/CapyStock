<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createChart, type IChartApi } from 'lightweight-charts';

  export let rsiData: { date: string; value: number | null }[] = [];

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
      rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } },
    });

    const rsiSeries = chart.addLineSeries({
      color: '#60a5fa',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    const data = rsiData.filter(d => d.value != null).map(d => ({ time: d.date as any, value: d.value as number }));
    rsiSeries.setData(data);

    // 30 / 70 水平線
    rsiSeries.createPriceLine({ price: 30, color: '#f87171', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'OS' });
    rsiSeries.createPriceLine({ price: 70, color: '#4ade80', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'OB' });

    const ro = new ResizeObserver(() => { if (chart && container) chart.resize(container.clientWidth, 140); });
    ro.observe(container);
    return () => { ro.disconnect(); };
  });

  onDestroy(() => { if (chart) { chart.remove(); chart = null; } });
</script>

<div class="rsi-wrap">
  <div class="label">RSI(14)</div>
  <div bind:this={container}></div>
</div>

<style>
  .rsi-wrap { width: 100%; }
  .label { font-size: 12px; color: #888; padding: 4px 0; }
</style>
