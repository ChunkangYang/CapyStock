<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import type { FundamentalReport, DpsRow } from '$lib/types';
  import RadarChart from '$lib/components/RadarChart.svelte';
  import DividendBarChart from '$lib/components/DividendBarChart.svelte';
  import FavoriteToggle from '$lib/components/FavoriteToggle.svelte';

  let code = '';
  let loading = true;
  let error = '';
  let report: FundamentalReport | null = null;
  let dpsHistory: DpsRow[] = [];

  onMount(async () => {
    code = $page.params.code;
    try {
      const [fundReport, dpsSeries] = await Promise.all([
        api<FundamentalReport>(`/dividend/${code}`),
        api<DpsRow[]>(`/dividend/${code}/series`),
      ]);
      report = fundReport;
      dpsHistory = dpsSeries;
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  });

  function getOverallColor(overall: string): string {
    switch (overall) {
      case 'STRONG':
        return '#4ade80';
      case 'HEALTHY':
        return '#60a5fa';
      case 'CAUTION':
        return '#f59e0b';
      case 'RISKY':
        return '#ef4444';
      default:
        return '#888';
    }
  }

  function getScoreColor(score: string): string {
    switch (score) {
      case 'PASS':
        return '#4ade80';
      case 'WARN':
        return '#f59e0b';
      case 'FAIL':
        return '#ef4444';
      default:
        return '#888';
    }
  }
</script>

<div class="page">
  {#if loading}
    <div class="loading">載入中...</div>
  {:else if error}
    <div class="error">{error}</div>
  {:else if report}
    <div class="header">
      <div class="header-top">
        <div class="code-section">
          <h1>{report.code}</h1>
          <p class="name">{report.name}</p>
        </div>
        <div class="header-right">
          <div class="overall" style="color: {getOverallColor(report.overall)}">
            {report.overall}
          </div>
          <FavoriteToggle code={report.code} name={report.name} tag="dividend" />
        </div>
      </div>
    </div>

    <div class="main-content">
      <div class="left-col">
        <div class="chart-box">
          <h3>8 指標雷達圖</h3>
          <RadarChart {report} />
        </div>

        <div class="chart-box">
          <h3>配當歷史</h3>
          <DividendBarChart {dpsHistory} />
        </div>
      </div>

      <div class="right-col">
        <div class="metrics-box">
          <h3>指標評分</h3>
          <table class="metrics-table">
            <thead>
              <tr>
                <th>指標</th>
                <th>評分</th>
                <th>說明</th>
              </tr>
            </thead>
            <tbody>
              {#each report.metrics as metric (metric.name)}
                <tr>
                  <td class="metric-name">{metric.name}</td>
                  <td class="metric-score" style="color: {getScoreColor(metric.score)}">
                    {metric.score}
                  </td>
                  <td class="metric-note">{metric.note || '—'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        <div class="stats-box">
          <h3>統計摘要</h3>
          <div class="stat-row">
            <span class="stat-label">PASS</span>
            <span class="stat-value" style="color: #4ade80">{report.pass_count} / 8</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">WARN</span>
            <span class="stat-value" style="color: #f59e0b">{report.warn_count} / 8</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">FAIL</span>
            <span class="stat-value" style="color: #ef4444">{report.fail_count} / 8</span>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .page {
    padding: 20px;
    color: #e0e0e0;
  }

  .loading,
  .error {
    text-align: center;
    padding: 40px;
    font-size: 16px;
  }

  .error {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.1);
    border-radius: 4px;
  }

  .header {
    margin-bottom: 30px;
    padding: 20px;
    background: #222;
    border-radius: 8px;
  }

  .header-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .code-section h1 {
    margin: 0 0 4px 0;
    font-size: 32px;
    color: #4ade80;
  }

  .code-section p.name {
    margin: 0;
    color: #888;
    font-size: 14px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .overall {
    font-size: 24px;
    font-weight: bold;
  }

  .main-content {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 20px;
  }

  .chart-box,
  .metrics-box,
  .stats-box {
    background: #222;
    border-radius: 8px;
    padding: 20px;
  }

  .chart-box h3,
  .metrics-box h3,
  .stats-box h3 {
    margin: 0 0 16px 0;
    color: #4ade80;
    font-size: 16px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .chart-box {
    margin-bottom: 20px;
  }

  .metrics-table {
    width: 100%;
    font-size: 13px;
    border-collapse: collapse;
  }

  .metrics-table thead {
    background: #2a2a2a;
  }

  .metrics-table th {
    padding: 8px;
    text-align: left;
    color: #888;
    border-bottom: 1px solid #333;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
  }

  .metrics-table tbody tr {
    border-bottom: 1px solid #2a2a2a;
  }

  .metrics-table td {
    padding: 8px;
    color: #ccc;
  }

  .metric-name {
    font-weight: 500;
  }

  .metric-score {
    text-align: center;
    font-weight: 600;
    width: 60px;
  }

  .metric-note {
    color: #888;
    font-size: 12px;
    text-align: right;
  }

  .stats-box {
    margin-top: 20px;
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #2a2a2a;
  }

  .stat-row:last-child {
    border-bottom: none;
  }

  .stat-label {
    color: #888;
    font-size: 13px;
  }

  .stat-value {
    font-weight: 600;
    font-size: 16px;
  }

  @media (max-width: 1024px) {
    .main-content {
      grid-template-columns: 1fr;
    }
  }
</style>
