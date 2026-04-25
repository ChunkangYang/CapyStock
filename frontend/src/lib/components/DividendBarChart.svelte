<script lang="ts">
  import { onMount } from 'svelte';
  import * as echarts from 'echarts';
  import type { DpsRow } from '$lib/types';

  export let dpsHistory: DpsRow[] = [];

  let container: HTMLDivElement;
  let chart: echarts.ECharts | null = null;

  onMount(() => {
    if (!container || !dpsHistory.length) return;

    chart = echarts.init(container, null, { useDirtyRect: true });

    const sortedHistory = [...dpsHistory].sort((a, b) => a.fiscal_year - b.fiscal_year);

    const option = {
      backgroundColor: '#1a1a1a',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
      },
      grid: {
        left: '50px',
        right: '50px',
        bottom: '30px',
        top: '20px',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: sortedHistory.map((row) => row.fiscal_year.toString()),
        axisLine: { lineStyle: { color: '#333' } },
        axisLabel: { color: '#888', fontSize: 12 },
      },
      yAxis: [
        {
          type: 'value',
          name: 'DPS',
          position: 'left',
          axisLine: { lineStyle: { color: '#4ade80' } },
          axisLabel: { color: '#4ade80' },
          splitLine: { lineStyle: { color: '#222' } },
        },
        {
          type: 'value',
          name: 'EPS',
          position: 'right',
          axisLine: { lineStyle: { color: '#f59e0b' } },
          axisLabel: { color: '#f59e0b' },
          splitLine: { lineStyle: { color: '#222' } },
        },
      ],
      series: [
        {
          name: 'DPS',
          data: sortedHistory.map((row) => row.dps),
          type: 'bar',
          yAxisIndex: 0,
          itemStyle: { color: '#4ade80' },
        },
        {
          name: 'EPS',
          data: sortedHistory.map((row) => row.eps),
          type: 'line',
          yAxisIndex: 1,
          lineStyle: { type: 'dashed', color: '#f59e0b', width: 2 },
          symbol: 'circle',
          symbolSize: 5,
          itemStyle: { color: '#f59e0b' },
        },
      ],
      legend: {
        data: ['DPS', 'EPS'],
        textStyle: { color: '#888' },
        top: 0,
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
