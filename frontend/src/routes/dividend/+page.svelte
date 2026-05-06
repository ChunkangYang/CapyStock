<script lang="ts">
  import { onMount } from 'svelte';
  import { api, ApiError } from '$lib/api';
  import type { DividendScanRow } from '$lib/types';
  import FavoriteToggle from '$lib/components/FavoriteToggle.svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
  import { favorites } from '$lib/stores/favorites';

  interface FilterState {
    overall: Set<string>;
    minYield: number;
    minDpsStreak: number;
    minEquityRatio: number;
    maxPayoutRatio: number;
    onlyFavorites: boolean;
  }

  interface SortState {
    column: string;
    desc: boolean;
  }

  let loading = true;
  let error = '';
  let noSnapshot = false;
  let rows: DividendScanRow[] = [];
  let filtered: DividendScanRow[] = [];

  const filters: FilterState = {
    overall: new Set(['STRONG', 'HEALTHY', 'CAUTION', 'RISKY']),
    minYield: 0,
    minDpsStreak: 0,
    minEquityRatio: 0,
    maxPayoutRatio: 100,
    onlyFavorites: false,
  };

  const sort: SortState = {
    column: 'est_yield',
    desc: true,
  };

  $: {
    applyFiltersAndSort();
  }

  onMount(async () => {
    try {
      const data = await api<DividendScanRow[]>('/scan/dividend');
      rows = data;
      applyFiltersAndSort();
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        noSnapshot = true;
      } else {
        error = e instanceof Error ? e.message : String(e);
      }
    } finally {
      loading = false;
    }
  });

  function applyFiltersAndSort() {
    const favoriteSet = new Set(
      Object.values($favorites)
        .filter((f: { tags: string[] }) => f.tags?.includes('dividend'))
        .map((f: { code: string }) => f.code)
    );

    let result = rows.filter((row) => {
      if (!filters.overall.has(row.overall)) return false;
      if (filters.minYield > 0 && (row.est_yield == null || row.est_yield < filters.minYield)) return false;
      if (row.dps_streak_no_cut < filters.minDpsStreak) return false;
      if (filters.minEquityRatio > 0 && (row.equity_ratio_latest == null || row.equity_ratio_latest < filters.minEquityRatio)) return false;
      if (row.payout_avg != null && row.payout_avg * 100 > filters.maxPayoutRatio) return false;
      if (filters.onlyFavorites && !favoriteSet.has(row.code)) return false;
      return true;
    });

    result.sort((a, b) => {
      let aVal: string | number;
      let bVal: string | number;

      if (sort.column === 'overall') {
        aVal = OVERALL_RANK[a.overall] ?? 0;
        bVal = OVERALL_RANK[b.overall] ?? 0;
      } else if (sort.column === 'favorite') {
        aVal = favoriteSet.has(a.code) ? 1 : 0;
        bVal = favoriteSet.has(b.code) ? 1 : 0;
      } else if (sort.column === 'metrics') {
        aVal = a.pass_count;
        bVal = b.pass_count;
      } else if (sort.column === 'name' || sort.column === 'code') {
        aVal = (a[sort.column as keyof DividendScanRow] as string) ?? '';
        bVal = (b[sort.column as keyof DividendScanRow] as string) ?? '';
        const cmp = aVal.localeCompare(bVal, 'ja');
        return sort.desc ? -cmp : cmp;
      } else {
        aVal = (a[sort.column as keyof DividendScanRow] as number) ?? -Infinity;
        bVal = (b[sort.column as keyof DividendScanRow] as number) ?? -Infinity;
      }

      return sort.desc
        ? (bVal as number) - (aVal as number)
        : (aVal as number) - (bVal as number);
    });

    filtered = result;
  }

  function toggleOverall(overall: string) {
    if (filters.overall.has(overall)) {
      filters.overall.delete(overall);
    } else {
      filters.overall.add(overall);
    }
    filters.overall = filters.overall;
    applyFiltersAndSort();
  }

  const OVERALL_RANK: Record<string, number> = { STRONG: 4, HEALTHY: 3, CAUTION: 2, RISKY: 1 };

  function updateSort(column: string) {
    if (sort.column === column) {
      sort.desc = !sort.desc;
    } else {
      sort.column = column;
      sort.desc = true;
    }
    applyFiltersAndSort();
  }

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
</script>

<div class="page">
  <div class="header">
    <h1>金雞高股息</h1>
  </div>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  {#if noSnapshot}
    <div class="empty-state">
      <p>尚無金雞掃描快照。請至 <a href="/data">資料管理</a> 或執行掃描排程後再回來。</p>
    </div>
  {/if}

  <div class="filters">
    <div class="filter-group">
      <label>Overall</label>
      <div class="checkboxes">
        {#each ['STRONG', 'HEALTHY', 'CAUTION', 'RISKY'] as overall}
          <label class="checkbox">
            <input
              type="checkbox"
              checked={filters.overall.has(overall)}
              on:change={() => toggleOverall(overall)}
            />
            {overall}
          </label>
        {/each}
      </div>
    </div>

    <div class="filter-group">
      <label>殖利率最低值 ({(filters.minYield * 100).toFixed(1)}%)</label>
      <input
        type="range"
        min="0"
        max="0.30"
        step="0.005"
        bind:value={filters.minYield}
        on:change={() => applyFiltersAndSort()}
      />
    </div>

    <div class="filter-group">
      <label>無減配年數 ({filters.minDpsStreak})</label>
      <input
        type="range"
        min="0"
        max="10"
        step="1"
        bind:value={filters.minDpsStreak}
        on:change={() => applyFiltersAndSort()}
      />
    </div>

    <div class="filter-group">
      <label>自己資本比率 ({(filters.minEquityRatio * 100).toFixed(0)}%)</label>
      <input
        type="range"
        min="0"
        max="1.0"
        step="0.01"
        bind:value={filters.minEquityRatio}
        on:change={() => applyFiltersAndSort()}
      />
    </div>

    <div class="filter-group">
      <label>配當性向上限 ({filters.maxPayoutRatio}%)</label>
      <input
        type="range"
        min="10"
        max="100"
        step="1"
        bind:value={filters.maxPayoutRatio}
        on:change={() => applyFiltersAndSort()}
      />
    </div>

    <div class="filter-group">
      <label class="checkbox">
        <input
          type="checkbox"
          bind:checked={filters.onlyFavorites}
          on:change={() => applyFiltersAndSort()}
        />
        只看我的最愛
      </label>
    </div>
  </div>

  <div class="table-wrapper">
    <table>
      <thead>
        <tr>
          <th on:click={() => updateSort('favorite')}>★</th>
          <th on:click={() => updateSort('code')}>Code</th>
          <th on:click={() => updateSort('name')}>Name</th>
          <th on:click={() => updateSort('overall')}>Overall</th>
          <th on:click={() => updateSort('latest_dps')}>DPS</th>
          <th on:click={() => updateSort('est_yield')}>Yield</th>
          <th on:click={() => updateSort('dps_streak_no_cut')}>連無減配</th>
          <th on:click={() => updateSort('payout_avg')}>Payout Avg</th>
          <th on:click={() => updateSort('equity_ratio_latest')}>自己資本比</th>
          <th on:click={() => updateSort('eps_growth')}>EPS Growth</th>
          <th on:click={() => updateSort('metrics')}>指標</th>
        </tr>
      </thead>
      <tbody>
        {#each filtered as row (row.code)}
          <tr on:click={() => (window.location.href = `/dividend/${row.code}`)}>
            <td class="favorite-cell">
              <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
              <span on:click|stopPropagation>
                <FavoriteToggle
                  code={row.code}
                  name={row.name}
                  tag="dividend"
                />
              </span>
            </td>
            <td class="code">{row.code}</td>
            <td class="name">{row.name}</td>
            <td class="overall" style="color: {getOverallColor(row.overall)}">
              {row.overall}
            </td>
            <td class="number">{row.latest_dps != null ? row.latest_dps.toFixed(2) : '-'}</td>
            <td class="number">{row.est_yield != null ? (row.est_yield * 100).toFixed(2) + '%' : '-'}</td>
            <td class="number">{row.dps_streak_no_cut}</td>
            <td class="number">{row.payout_avg != null ? (row.payout_avg * 100).toFixed(1) + '%' : '-'}</td>
            <td class="number">{row.equity_ratio_latest != null ? (row.equity_ratio_latest * 100).toFixed(1) + '%' : '-'}</td>
            <td class="number">{row.eps_growth != null ? (row.eps_growth * 100).toFixed(1) + '%' : '-'}</td>
            <td class="metrics">
              <div class="stacked-bar">
                <div
                  class="bar-part pass"
                  style="width: {(row.pass_count / 8) * 100}%"
                  title="Pass: {row.pass_count}"
                />
                <div
                  class="bar-part warn"
                  style="width: {(row.warn_count / 8) * 100}%"
                  title="Warn: {row.warn_count}"
                />
                <div
                  class="bar-part fail"
                  style="width: {(row.fail_count / 8) * 100}%"
                  title="Fail: {row.fail_count}"
                />
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if !loading && filtered.length === 0}
    <div class="empty">沒有符合條件的股票</div>
  {/if}

  {#if loading}
    <LoadingSpinner />
  {/if}
</div>

<style>
  .page {
    padding: 20px;
    color: #e0e0e0;
  }

  .header {
    margin-bottom: 30px;
  }

  .header h1 {
    color: #4ade80;
    margin: 0;
    font-size: 28px;
  }

  .error {
    color: #ef4444;
    padding: 10px;
    background: rgba(239, 68, 68, 0.1);
    border-radius: 4px;
    margin-bottom: 20px;
  }

  .filters {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    padding: 15px;
    background: #222;
    border-radius: 8px;
    margin-bottom: 20px;
  }

  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .filter-group label {
    color: #888;
    font-size: 12px;
    text-transform: uppercase;
  }

  .checkboxes {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    color: #ccc;
    font-size: 14px;
  }

  .checkbox input[type='checkbox'] {
    cursor: pointer;
    width: 16px;
    height: 16px;
  }

  .filter-group input[type='range'] {
    cursor: pointer;
    accent-color: #4ade80;
  }

  .table-wrapper {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  thead {
    background: #222;
    position: sticky;
    top: 0;
  }

  th {
    padding: 12px 8px;
    text-align: left;
    color: #888;
    border-bottom: 1px solid #333;
    cursor: pointer;
    user-select: none;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
  }

  th:hover {
    color: #4ade80;
    background: #2a2a2a;
  }

  tbody tr {
    cursor: pointer;
    border-bottom: 1px solid #2a2a2a;
    transition: background 0.2s;
  }

  tbody tr:hover {
    background: #2a2a2a;
  }

  td {
    padding: 10px 8px;
    color: #ddd;
  }

  td.favorite-cell {
    text-align: center;
    padding: 6px;
  }

  td.code {
    color: #4ade80;
    font-weight: 600;
    width: 60px;
  }

  td.name {
    width: 120px;
    color: #ccc;
  }

  td.overall {
    font-weight: 600;
    width: 70px;
  }

  td.number {
    text-align: right;
    color: #aaa;
    font-variant-numeric: tabular-nums;
    width: 80px;
  }

  td.metrics {
    width: 80px;
  }

  .stacked-bar {
    display: flex;
    height: 16px;
    border-radius: 2px;
    overflow: hidden;
    background: #333;
  }

  .bar-part {
    height: 100%;
  }

  .bar-part.pass {
    background: #4ade80;
  }

  .bar-part.warn {
    background: #f59e0b;
  }

  .bar-part.fail {
    background: #ef4444;
  }

  .empty,
  .loading {
    text-align: center;
    color: #888;
    padding: 40px;
  }

  .empty-state {
    text-align: center;
    color: #aaa;
    padding: 60px 20px;
    background: #1d1d1d;
    border: 1px dashed #333;
    border-radius: 8px;
  }

  .empty-state a {
    color: #4ade80;
  }
</style>
