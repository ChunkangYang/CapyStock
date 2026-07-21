<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as echarts from 'echarts';

  // 日曆軸資金曲線：總權益（面積線）+ 現金（堆疊底）+ 起始資金基準線。
  export let dates: string[] = [];
  export let equity: number[] = [];
  export let cash: number[] = [];
  export let marketValue: number[] = [];
  export let initialCash = 0;

  let container: HTMLDivElement;
  let chart: echarts.ECharts | null = null;

  function render() {
    if (!chart) return;
    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v: any) => (v == null ? '—' : `¥${Math.round(Number(v)).toLocaleString()}`),
      },
      legend: { data: ['總權益', '現金', '持倉市值'], textStyle: { color: '#94a3b8' }, top: 0 },
      grid: { left: 8, right: 16, top: 34, bottom: 30, containLabel: true },
      xAxis: {
        type: 'category', data: dates, boundaryGap: false,
        axisLine: { lineStyle: { color: '#333' } },
        axisLabel: { color: '#888', fontSize: 11 },
      },
      yAxis: {
        type: 'value', scale: true,
        axisLine: { lineStyle: { color: '#333' } },
        axisLabel: { color: '#888', formatter: (v: number) => `${Math.round(v / 10000)}萬` },
        splitLine: { lineStyle: { color: '#222' } },
      },
      series: [
        {
          name: '總權益', type: 'line', data: equity, showSymbol: false, z: 3,
          itemStyle: { color: '#4ade80' }, lineStyle: { color: '#4ade80', width: 2 },
          areaStyle: { color: 'rgba(74,222,128,0.10)' },
          markLine: {
            symbol: 'none', silent: true,
            data: [{ yAxis: initialCash, lineStyle: { color: '#64748b', type: 'dashed' },
                     label: { formatter: `起始 ¥${Math.round(initialCash).toLocaleString()}`, color: '#94a3b8', fontSize: 11 } }],
          },
        },
        { name: '現金', type: 'line', data: cash, showSymbol: false,
          itemStyle: { color: '#60a5fa' }, lineStyle: { color: '#60a5fa', width: 1, type: 'dotted' } },
        { name: '持倉市值', type: 'line', data: marketValue, showSymbol: false,
          itemStyle: { color: '#fbbf24' }, lineStyle: { color: '#fbbf24', width: 1, type: 'dotted' } },
      ],
    });
  }

  $: if (chart && dates.length) render();

  onMount(() => {
    if (!container) return;
    chart = echarts.init(container, null, { useDirtyRect: true });
    render();
    const onResize = () => chart?.resize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  });

  onDestroy(() => {
    chart?.dispose();
    chart = null;
  });
</script>

<div bind:this={container} class="chart" />

<style>
  .chart { width: 100%; height: 340px; }
</style>
