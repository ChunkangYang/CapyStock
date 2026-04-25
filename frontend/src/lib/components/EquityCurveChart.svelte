<script lang="ts">
  import { onMount } from 'svelte';
  import type { EquityPoint } from '$lib/types';
  import { createChart, ColorType } from 'lightweight-charts';

  export let data: EquityPoint[];
  export let initialCapital: number;

  let container: HTMLDivElement;

  onMount(() => {
    if (!container || !data.length) return;

    const chart = createChart(container, {
      layout: {
        textColor: '#a1a1a1',
        background: { type: ColorType.Solid, color: '#0f0f0f' }
      },
      width: container.clientWidth,
      height: 400,
      timeScale: {
        timeVisible: true,
        secondsVisible: false
      }
    });

    const areaSeries = chart.addAreaSeries({
      lineColor: '#4ade80',
      topColor: '#4ade8033',
      bottomColor: '#4ade8000'
    });

    // Convert data to lightweight-charts format
    const chartData = data.map((point) => ({
      time: new Date(point.date).getTime() / 1000,
      value: point.equity
    }));

    areaSeries.setData(chartData);

    // Add initial capital line
    const initialLine = chart.addLineSeries({
      color: '#999',
      lineStyle: 2,
      lineWidth: 1
    });

    initialLine.setData(
      chartData.map((p) => ({
        time: p.time,
        value: initialCapital
      }))
    );

    chart.timeScale().fitContent();

    // Handle resize
    const handleResize = () => {
      if (container) {
        chart.applyOptions({
          width: container.clientWidth
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  });
</script>

<div class="chart-wrapper">
  <div class="chart-container" bind:this={container}></div>
</div>

<style>
  .chart-wrapper {
    width: 100%;
    overflow-x: auto;
  }

  .chart-container {
    width: 100%;
    min-height: 400px;
  }
</style>
