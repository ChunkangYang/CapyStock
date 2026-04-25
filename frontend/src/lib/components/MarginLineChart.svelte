<script lang="ts">
  import { onMount } from 'svelte';
  import * as echarts from 'echarts';
  import type { MarginRow } from '$lib/types';

  export let margins: MarginRow[] = [];

  let container: HTMLDivElement;
  let chart: echarts.ECharts | null = null;

  onMount(() => {
    if (!container || !margins.length) return;

    chart = echarts.init(container, null, { useDirtyRect: true });

    const option = {
      backgroundColor: '#1a1a1a',
      tooltip: {
        trigger: 'axis',
      },
      grid: {
        left: '50px',
        right: '20px',
        bottom: '30px',
        top: '20px',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: margins.map((m) => m.week),
        axisLine: { lineStyle: { color: '#333' } },
        axisLabel: { color: '#888', fontSize: 12 },
      },
      yAxis: [
        {
          type: 'value',
          name: '融資 / 融券',
          axisLine: { lineStyle: { color: '#333' } },
          axisLabel: { color: '#888' },
          splitLine: { lineStyle: { color: '#222' } },
        },
        {
          type: 'value',
          name: '倍率',
          axisLine: { lineStyle: { color: '#333' } },
          axisLabel: { color: '#888' },
          splitLine: { lineStyle: { color: '#222' } },
        },
      ],
      series: [
        {
          name: '融資',
          data: margins.map((m) => m.margin_long),
          type: 'line',
          smooth: true,
          itemStyle: { color: '#f87171' },
          yAxisIndex: 0,
        },
        {
          name: '融券',
          data: margins.map((m) => m.margin_short),
          type: 'line',
          smooth: true,
          itemStyle: { color: '#4ade80' },
          yAxisIndex: 0,
        },
        {
          name: '倍率',
          data: margins.map((m) => m.ratio),
          type: 'line',
          smooth: true,
          itemStyle: { color: '#888' },
          lineStyle: { type: 'dashed' },
          yAxisIndex: 1,
        },
      ],
      legend: {
        data: ['融資', '融券', '倍率'],
        textStyle: { color: '#888' },
        bottom: 0,
      },
    };

    chart.setOption(option);

    const handleResize = () => {
      if (chart) {
        chart.resize();
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
    height: 300px;
  }
</style>
