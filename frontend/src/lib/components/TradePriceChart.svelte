<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as echarts from 'echarts';

  // 日曆軸（含週末/未同步日），closes 對應日無資料為 null → 折線留白不連線。
  export let dates: string[] = [];
  export let closes: (number | null)[] = [];
  export let entryPrice: number;
  export let stopLine: number;
  export let exitDate: string | null = null;
  export let exitPrice: number | null = null;

  let container: HTMLDivElement;
  let chart: echarts.ECharts | null = null;

  onMount(() => {
    if (!container) return;
    chart = echarts.init(container, null, { useDirtyRect: true });

    const markLines: any[] = [
      { name: '進場價', yAxis: entryPrice, lineStyle: { color: '#60a5fa', type: 'dashed' },
        label: { formatter: `進場 ${Math.round(entryPrice)}`, color: '#60a5fa' } },
      { name: '停損線', yAxis: stopLine, lineStyle: { color: '#f87171', type: 'dashed' },
        label: { formatter: `停損 ${Math.round(stopLine)}`, color: '#f87171' } },
    ];

    const series: any = {
      name: '收盤',
      type: 'line',
      data: closes,
      connectNulls: false, // 缺資料留白：不跨空白連線
      showSymbol: false,
      itemStyle: { color: '#4ade80' },
      lineStyle: { color: '#4ade80' },
      areaStyle: { color: 'rgba(74,222,128,0.08)' },
      markLine: { symbol: 'none', data: markLines, label: { fontSize: 11 } },
    };

    if (exitDate && exitPrice != null) {
      series.markPoint = {
        symbolSize: 46,
        data: [{ name: '出場', coord: [exitDate, exitPrice], value: '出場',
                 itemStyle: { color: '#f87171' }, label: { color: '#fff', fontSize: 10 } }],
      };
    }

    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v: any) => (v == null ? '無資料' : `¥${Number(v).toLocaleString()}`),
      },
      grid: { left: 8, right: 16, top: 24, bottom: 30, containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#333' } },
        axisLabel: { color: '#888', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLine: { lineStyle: { color: '#333' } },
        axisLabel: { color: '#888' },
        splitLine: { lineStyle: { color: '#222' } },
      },
      series: [series],
    });

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
  .chart {
    width: 100%;
    height: 360px;
  }
</style>
