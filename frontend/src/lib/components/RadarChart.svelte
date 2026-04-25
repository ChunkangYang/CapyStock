<script lang="ts">
  import { onMount } from 'svelte';
  import * as echarts from 'echarts';
  import type { FundamentalReport } from '$lib/types';

  export let report: FundamentalReport | null = null;

  let container: HTMLDivElement;
  let chart: echarts.ECharts | null = null;

  function scoreToValue(score: string): number {
    switch (score) {
      case 'PASS':
        return 100;
      case 'WARN':
        return 60;
      case 'FAIL':
        return 20;
      case 'N/A':
        return 0;
      default:
        return 0;
    }
  }

  onMount(() => {
    if (!container || !report) return;

    chart = echarts.init(container, null, { useDirtyRect: true });

    const metricsData = report.metrics.map((m) => scoreToValue(m.score));
    const metricsNames = report.metrics.map((m) => m.name);

    const option = {
      backgroundColor: '#1a1a1a',
      tooltip: {
        trigger: 'item',
      },
      radar: {
        indicator: metricsNames.map((name) => ({
          name,
          max: 100,
        })),
        axisLine: { lineStyle: { color: '#444' } },
        splitLine: { lineStyle: { color: '#333' } },
        axisLabel: { color: '#888', fontSize: 11 },
        name: { textStyle: { color: '#888' } },
      },
      series: [
        {
          name: report.code,
          data: [metricsData],
          type: 'radar',
          itemStyle: { color: '#4ade80' },
          lineStyle: { color: '#4ade80', width: 2 },
          areaStyle: { color: 'rgba(74, 222, 128, 0.1)' },
        },
      ],
      legend: {
        data: [report.code],
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
    height: 400px;
  }
</style>
