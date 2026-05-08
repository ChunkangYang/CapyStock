<script lang="ts">
  import { onMount } from 'svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  const API = '/api/v1';

  interface OverviewRow {
    code: string;
    name: string;
    price_age_days: number | null;
    margin_age_days: number | null;
    flow_age_days: number | null;
    fundamental_age_days: number | null;
  }

  let rows: OverviewRow[] = [];
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      const res = await fetch(`${API}/data/overview`);
      if (!res.ok) throw new Error(res.statusText);
      rows = await res.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  function ageCellClass(days: number | null): string {
    if (days === null) return 'age-none';
    if (days > 30) return 'age-old';
    if (days > 7) return 'age-mid';
    return 'age-new';
  }

  function ageLabel(days: number | null): string {
    if (days === null) return '—';
    return `${days}d`;
  }
</script>

<div class="data-page">
  <div class="page-header">
    <h1>資料管理</h1>
    <div class="actions">
      <a href="/data/ingest" class="btn-primary">批量抓取</a>
      <a href="/data/upload" class="btn-secondary">上傳資料</a>
    </div>
  </div>

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <div class="error-banner">{error}</div>
  {:else}
    <div class="legend">
      <span class="legend-item"><span class="dot dot-new"></span>最新（≤7日）</span>
      <span class="legend-item"><span class="dot dot-mid"></span>偏舊（7-30日）</span>
      <span class="legend-item"><span class="dot dot-old"></span>過舊（>30日）</span>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>代碼</th>
            <th>名稱</th>
            <th class="center">股價</th>
            <th class="center">信用残</th>
            <th class="center">投資部門別</th>
            <th class="center">基本面</th>
            <th class="center">操作</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row}
            <tr>
              <td class="code">{row.code}</td>
              <td class="name">{row.name}</td>
              <td class="center {ageCellClass(row.price_age_days)}">{ageLabel(row.price_age_days)}</td>
              <td class="center {ageCellClass(row.margin_age_days)}">{ageLabel(row.margin_age_days)}</td>
              <td class="center {ageCellClass(row.flow_age_days)}">{ageLabel(row.flow_age_days)}</td>
              <td class="center {ageCellClass(row.fundamental_age_days)}">{ageLabel(row.fundamental_age_days)}</td>
              <td class="center ops">
                <a href="/data/ingest?code={row.code}" class="op-link blue">重抓</a>
                <a href="/data/upload?code={row.code}" class="op-link green">上傳</a>
              </td>
            </tr>
          {/each}
          {#if rows.length === 0}
            <tr><td colspan="7" class="empty">追蹤清單為空</td></tr>
          {/if}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .data-page {
    max-width: 900px;
    margin: 0 auto;
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
  }

  h1 {
    font-size: 28px;
    color: #4ade80;
    margin: 0;
  }

  .actions {
    display: flex;
    gap: 10px;
  }

  .btn-primary {
    background: #4ade80;
    color: #0f0f0f;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 14px;
    text-decoration: none;
    cursor: pointer;
  }

  .btn-primary:hover {
    background: #22c55e;
  }

  .btn-secondary {
    background: transparent;
    color: #4ade80;
    border: 1px solid #4ade80;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 14px;
    text-decoration: none;
    cursor: pointer;
  }

  .btn-secondary:hover {
    background: #052e16;
  }

  .error-banner {
    background: #1f1a1a;
    border: 1px solid #7f1d1d;
    color: #f87171;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 14px;
  }

  .legend {
    display: flex;
    gap: 20px;
    margin-bottom: 16px;
    font-size: 13px;
    color: #a1a1a1;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    display: inline-block;
  }

  .dot-new  { background: #166534; }
  .dot-mid  { background: #854d0e; }
  .dot-old  { background: #7f1d1d; }

  .table-wrap {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    overflow: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }

  .data-table th {
    text-align: left;
    padding: 10px 14px;
    color: #6b7280;
    border-bottom: 1px solid #333;
    font-weight: 500;
    white-space: nowrap;
  }

  .data-table td {
    padding: 10px 14px;
    border-bottom: 1px solid #222;
    color: #e5e7eb;
  }

  .data-table tr:last-child td {
    border-bottom: none;
  }

  .data-table tbody tr:hover td {
    background: #222;
  }

  .center { text-align: center; }

  .code {
    font-family: monospace;
    font-weight: 700;
    color: #fff;
  }

  .name { color: #a1a1a1; }

  .empty {
    text-align: center;
    padding: 40px;
    color: #6b7280;
  }

  /* age badge colours */
  .age-new  { color: #4ade80; }
  .age-mid  { color: #facc15; }
  .age-old  { color: #f87171; font-weight: 600; }
  .age-none { color: #4b5563; }

  .ops { white-space: nowrap; }

  .op-link {
    font-size: 12px;
    text-decoration: none;
    margin: 0 4px;
  }

  .op-link.blue  { color: #60a5fa; }
  .op-link.blue:hover  { color: #93c5fd; }
  .op-link.green { color: #4ade80; }
  .op-link.green:hover { color: #86efac; }
</style>
