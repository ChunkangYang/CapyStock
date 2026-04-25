<script lang="ts">
  import { onMount } from 'svelte';
  import * as echarts from 'echarts';
  import type { FlowRow } from '$lib/types';

  export let flows: FlowRow[] = [];

  let container: HTMLDivElement;
  let chart: echarts.ECharts | null = null;

  onMount(() => {
    if (!container || !flows.length) return;

    chart = echarts.init(container, null, { useDirtyRect: true });

    const option = {
      backgroundColor: '#1a1a1a',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
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
        data: flows.map((f) => f.date),
        axisLine: { lineStyle: { color: '#333' } },
        axisLabel: { color: '#888', fontSize: 12 },
      },
      yAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#333' } },
        axisLabel: { color: '#888' },
        splitLine: { lineStyle: { color: '#222' } },
      },
      series: [
        {
          name: '外資',
          data: flows.map((f) => f.foreign_net ?? 0),
          type: 'bar',
          stack: 'total',
          itemStyle: { color: '#60a5fa' },
        },
        {
          name: '法人',
          data: flows.map((f) => f.institution_net ?? 0),
          type: 'bar',
          stack: 'total',
          itemStyle: { color: '#4ade80' },
        },
        {
          name: '個人',
          data: flows.map((f) => f.individual_net ?? 0),
          type: 'bar',
          stack: 'total',
          itemStyle: { color: '#f59e0b' },
        },
      ],
      legend: {
        data: ['外資', '法人', '個人'],
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
