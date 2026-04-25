<script lang="ts">
  import { onMount } from 'svelte';
  import {
    createChart,
    type IChartApi,
    type ISeriesApi,
    type SeriesType,
  } from 'lightweight-charts';
  import type { PriceBar } from '$lib/types';

  export let prices: PriceBar[] = [];
  export let startPrice: number | null = null;
  export let recentLow: number = 0;

  let container: HTMLDivElement;
  let chart: IChartApi | null = null;

  onMount(() => {
    if (!container || !prices.length) return;

    const width = container.clientWidth;
    const height = 400;

    chart = createChart(container, {
      layout: {
        background: { color: '#1a1a1a' },
        textColor: '#888',
      },
      width,
      height,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chart.applyOptions({
      watermark: {
        visible: false,
      },
    });

    // K線系列
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#4ade80',
      downColor: '#f87171',
      borderDownColor: '#f87171',
      borderUpColor: '#4ade80',
      wickDownColor: '#f87171',
      wickUpColor: '#4ade80',
    });

    const candleData = prices.map((p) => ({
      time: p.date as any,
      open: p.open,
      high: p.high,
      low: p.low,
      close: p.close,
    }));

    candleSeries.setData(candleData);

    // 起始價線
    if (startPrice) {
      const lineSeries = chart.addLineSeries({
        color: '#60a5fa',
        lineWidth: 1,
        lineStyle: 2, // dashed
      });
      const lineData = prices.map((p) => ({
        time: p.date as any,
        value: startPrice,
      }));
      lineSeries.setData(lineData);
    }

    // 停損線
    if (startPrice) {
      const stopLossPrice = startPrice * 0.95;
      const lineSeries = chart.addLineSeries({
        color: '#f87171',
        lineWidth: 1,
        lineStyle: 2,
      });
      const lineData = prices.map((p) => ({
        time: p.date as any,
        value: stopLossPrice,
      }));
      lineSeries.setData(lineData);
    }

    // 近 30 日最低價線
    if (recentLow > 0) {
      const lineSeries = chart.addLineSeries({
        color: '#888',
        lineWidth: 1,
        lineStyle: 2,
      });
      const lineData = prices.map((p) => ({
        time: p.date as any,
        value: recentLow,
      }));
      lineSeries.setData(lineData);
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (container && chart) {
        chart.applyOptions({
          width: container.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  });
</script>

<div bind:this={container} class="chart-container" />

<style>
  .chart-container {
    width: 100%;
    min-height: 400px;
  }
</style>
