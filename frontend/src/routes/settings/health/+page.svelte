<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api, ApiError } from '$lib/api';

  type Health = {
    generated_at: string;
    heartbeat: {
      job_id: string;
      last_success_at: string | null;
      seconds_since: number | null;
      status: 'ok' | 'stale' | 'unknown';
    };
    freshness: {
      signals_latest_date: string | null;
      dividend_latest_date: string | null;
      paper_oldest_cursor: string | null;
    };
    deliverability: { date: string; total: number; ok: number; success_rate: number }[];
    disk: {
      total_bytes: number;
      breakdown: { name: string; bytes: number }[];
    };
  };

  let data: Health | null = null;
  let errorMsg = '';
  let chartEl: HTMLDivElement | null = null;
  let chartInstance: any = null;

  async function load() {
    try {
      data = await api<Health>('/health/system');
      errorMsg = '';
      await renderChart();
    } catch (e) {
      errorMsg = e instanceof ApiError ? e.detail : String(e);
    }
  }

  async function renderChart() {
    if (!data || !chartEl) return;
    const echarts = await import('echarts');
    if (!chartInstance) chartInstance = echarts.init(chartEl);
    chartInstance.setOption({
      backgroundColor: 'transparent',
      grid: { left: 40, right: 16, top: 24, bottom: 24 },
      xAxis: {
        type: 'category',
        data: data.deliverability.map((d) => d.date.slice(5)),
        axisLine: { lineStyle: { color: '#444' } },
        axisLabel: { color: '#9ca3af' },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 1,
        axisLine: { lineStyle: { color: '#444' } },
        splitLine: { lineStyle: { color: '#222' } },
        axisLabel: {
          color: '#9ca3af',
          formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
        },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0];
          const row = data!.deliverability[p.dataIndex];
          return `${row.date}<br/>${row.ok}/${row.total} (${(row.success_rate * 100).toFixed(1)}%)`;
        },
      },
      series: [
        {
          type: 'line',
          data: data.deliverability.map((d) => d.success_rate),
          smooth: true,
          itemStyle: { color: '#4ade80' },
          areaStyle: { color: 'rgba(74,222,128,0.15)' },
          symbolSize: 6,
        },
      ],
    });
  }

  function fmtBytes(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
    if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
    return `${(n / 1024 ** 3).toFixed(2)} GB`;
  }

  function daysAgo(dateStr: string | null): string {
    if (!dateStr) return '無資料';
    const d = new Date(dateStr);
    const today = new Date();
    const diff = Math.floor((today.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
    if (diff <= 0) return '今日';
    return `${diff} 日前`;
  }

  function fmtSeconds(s: number | null): string {
    if (s == null) return '–';
    if (s < 60) return `${s.toFixed(0)} 秒前`;
    if (s < 3600) return `${(s / 60).toFixed(0)} 分前`;
    if (s < 86400) return `${(s / 3600).toFixed(1)} 小時前`;
    return `${(s / 86400).toFixed(1)} 日前`;
  }

  onMount(() => {
    load();
  });
  onDestroy(() => {
    if (chartInstance) chartInstance.dispose();
  });
</script>

<div class="page" data-testid="health-page">
  <h2>系統健康</h2>
  {#if errorMsg}<div class="error">{errorMsg}</div>{/if}

  {#if data}
    <div class="grid">
      <div class="card" data-testid="card-heartbeat">
        <h3>Worker 心跳</h3>
        <div class="value">
          <span
            class="dot"
            class:ok={data.heartbeat.status === 'ok'}
            class:warn={data.heartbeat.status === 'stale'}
            class:off={data.heartbeat.status === 'unknown'}
          ></span>
          {data.heartbeat.status}
        </div>
        <div class="meta">last success: {fmtSeconds(data.heartbeat.seconds_since)}</div>
      </div>

      <div class="card" data-testid="card-freshness">
        <h3>資料新鮮度</h3>
        <div class="row"><span>signals 最新</span><strong>{daysAgo(data.freshness.signals_latest_date)}</strong></div>
        <div class="row"><span>dividend 最新</span><strong>{daysAgo(data.freshness.dividend_latest_date)}</strong></div>
        <div class="row"><span>paper cursor 最舊</span><strong>{daysAgo(data.freshness.paper_oldest_cursor)}</strong></div>
      </div>

      <div class="card chart-card" data-testid="card-deliverability">
        <h3>Notification Deliverability（過去 7 日）</h3>
        <div bind:this={chartEl} class="chart" data-testid="deliverability-chart"></div>
      </div>

      <div class="card" data-testid="card-disk">
        <h3>Disk Usage</h3>
        <div class="value">{fmtBytes(data.disk.total_bytes)}</div>
        <table class="disk-table">
          <tbody>
            {#each data.disk.breakdown as b}
              <tr><td>{b.name}</td><td class="num">{fmtBytes(b.bytes)}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {:else if !errorMsg}
    <p class="muted">載入中…</p>
  {/if}
</div>

<style>
  .page { display: flex; flex-direction: column; gap: 16px; }
  h2 { margin: 0; }
  h3 { margin: 0 0 12px; font-size: 14px; color: #9ca3af; font-weight: 500; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
  .card { background: #161616; border: 1px solid #2a2a2a; border-radius: 8px; padding: 16px; }
  .chart-card { grid-column: span 2; }
  .chart { width: 100%; height: 200px; }
  .value { font-size: 22px; color: #e5e7eb; display: flex; align-items: center; gap: 8px; }
  .meta { font-size: 12px; color: #9ca3af; margin-top: 8px; }
  .row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; color: #d1d5db; }
  .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; background: #555; }
  .dot.ok { background: #4ade80; }
  .dot.warn { background: #facc15; }
  .dot.off { background: #555; }
  .disk-table { width: 100%; margin-top: 8px; border-collapse: collapse; }
  .disk-table td { padding: 4px 0; font-size: 12px; border-bottom: 1px solid #222; }
  .disk-table .num { text-align: right; color: #9ca3af; }
  .muted { color: #6b7280; }
  .error { background: #7f1d1d; color: #fee2e2; padding: 8px 12px; border-radius: 4px; }
</style>
