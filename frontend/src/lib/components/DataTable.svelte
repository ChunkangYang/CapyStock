<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import FavoriteToggle from './FavoriteToggle.svelte';
  import { favorites } from '$lib/stores/favorites';
  import type { SignalScanRow } from '$lib/types';

  export let data: SignalScanRow[] = [];
  export let extraRows: SignalScanRow[] = [];
  export let onRowClick: (code: string) => void = () => {};
  export let onRefreshRow: ((code: string) => void) | null = null;
  export let refreshingCodes: Set<string> = new Set();
  // Client-side pagination (null = render all rows)
  export let pageSize: number | null = null;
  export let currentPage: number = 1;

  const dispatch = createEventDispatcher<{ filteredTotal: number; pageReset: void }>();

  type SortKey = 'favorite' | 'code' | 'name' | 'latest_price' | 'c1' | 'c2' | 'c3' | 'edinet_recent_count' | 'score';
  type SortOrder = 'asc' | 'desc';

  const DEFAULT_ORDER: Record<SortKey, SortOrder> = {
    favorite: 'desc',
    code: 'asc',
    name: 'asc',
    latest_price: 'desc',
    c1: 'desc',
    c2: 'desc',
    c3: 'desc',
    edinet_recent_count: 'desc',
    score: 'desc',
  };

  let sortKey: SortKey = 'score';
  let sortOrder: SortOrder = 'desc';

  let filterAccumulation = false;
  let filterExit = false;
  let filterStopLoss = false;
  let minScore: number | null = null;

  function getSortValue(row: SignalScanRow, key: SortKey, favMap: Record<string, { tags: string[] }>): number | string {
    switch (key) {
      case 'favorite': return favMap[row.code]?.tags?.length > 0 ? 1 : 0;
      case 'code': return row.code;
      case 'name': return row.name;
      case 'latest_price': return row.latest_price ?? 0;
      case 'c1': return row.has_accumulation ? 1 : 0;
      case 'c2': return row.has_exit ? 1 : 0;
      case 'c3': return row.has_stop_loss ? 1 : 0;
      case 'edinet_recent_count': return row.edinet_recent_count ?? 0;
      case 'score': return row.score ?? 0;
    }
  }

  // extraRows（favorite 銘柄）を現在ページデータにマージ（重複除去）
  $: mergedData = [
    ...extraRows.filter(r => !data.some(d => d.code === r.code)),
    ...data,
  ];

  let prevFilterKey = '';
  $: filteredData = (() => {
    const newKey = `${filterAccumulation}|${filterExit}|${filterStopLoss}|${minScore}`;
    if (newKey !== prevFilterKey) {
      prevFilterKey = newKey;
      dispatch('pageReset');
    }
    return mergedData.filter(row => {
      if (filterAccumulation && !row.has_accumulation) return false;
      if (filterExit && !row.has_exit) return false;
      if (filterStopLoss && !row.has_stop_loss) return false;
      if (minScore !== null && row.score < minScore) return false;
      return true;
    });
  })();

  $: dispatch('filteredTotal', filteredData.length);

  $: sortedData = [...filteredData].sort((a, b) => {
    const aVal = getSortValue(a, sortKey, $favorites as Record<string, { tags: string[] }>);
    const bVal = getSortValue(b, sortKey, $favorites as Record<string, { tags: string[] }>);

    if (typeof aVal === 'string' && typeof bVal === 'string') {
      const compare = aVal.localeCompare(bVal, 'ja');
      return sortOrder === 'asc' ? compare : -compare;
    }

    const an = aVal as number;
    const bn = bVal as number;
    const compare = an < bn ? -1 : an > bn ? 1 : 0;
    return sortOrder === 'asc' ? compare : -compare;
  });

  $: pagedData = pageSize && pageSize > 0
    ? sortedData.slice((currentPage - 1) * pageSize, currentPage * pageSize)
    : sortedData;

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      sortOrder = DEFAULT_ORDER[key];
    }
    dispatch('pageReset');
  }

  function getIcon(alertType: string) {
    switch (alertType) {
      case 'accumulation':
        return '📈';
      case 'exit':
        return '⬇';
      case 'stop_loss':
        return '⚠';
      default:
        return '';
    }
  }
</script>

<div class="table-wrapper">
  <details class="signal-legend">
    <summary>訊號判斷條件說明</summary>
    <div class="legend-grid">
      <div><span class="dot blue">🔵</span><b>吃貨</b> — 外資或法人連續買超（≥2 期），同期融資餘額下降</div>
      <div><span class="dot orange">🟠</span><b>出場</b> — 符合三選二中至少 2 項（法人連賣 3 日累計 ≥ 前 10 日買超 20% ／ 融資 3 週增加且本週幅度 ≥ 8 週均 2 倍 ／ 股價離近 30 日低點 +30%）</div>
      <div><span class="dot red">🔴</span><b>停損</b> — 連續 2 日收盤低於停損錨點（主力成本或起始價 ×95%）</div>
    </div>
  </details>

  <div class="filters">
    <label>
      <input type="checkbox" bind:checked={filterAccumulation} />
      只看吃貨
    </label>
    <label>
      <input type="checkbox" bind:checked={filterExit} />
      只看出場
    </label>
    <label>
      <input type="checkbox" bind:checked={filterStopLoss} />
      只看停損
    </label>
    <label>
      最低 score:
      <input type="number" bind:value={minScore} placeholder="不限" />
    </label>
  </div>

  <table>
    <thead>
      <tr>
        <th>
          <button class="sort-btn" class:active={sortKey === 'favorite'} on:click={() => toggleSort('favorite')}>
            ★{#if sortKey === 'favorite'}&nbsp;{sortOrder === 'asc' ? '▲' : '▼'}{/if}
          </button>
        </th>
        <th>
          <button class="sort-btn" class:active={sortKey === 'code'} on:click={() => toggleSort('code')}>
            代號{#if sortKey === 'code'}&nbsp;{sortOrder === 'asc' ? '▲' : '▼'}{/if}
          </button>
        </th>
        <th>
          <button class="sort-btn" class:active={sortKey === 'name'} on:click={() => toggleSort('name')}>
            名稱{#if sortKey === 'name'}&nbsp;{sortOrder === 'asc' ? '▲' : '▼'}{/if}
          </button>
        </th>
        <th>
          <button class="sort-btn" class:active={sortKey === 'latest_price'} on:click={() => toggleSort('latest_price')}>
            價格{#if sortKey === 'latest_price'}&nbsp;{sortOrder === 'asc' ? '▲' : '▼'}{/if}
          </button>
        </th>
        <th title="外資或法人連續買超（≥2 期），同期融資餘額下降">
          <button class="sort-btn" class:active={sortKey === 'c1'} on:click={() => toggleSort('c1')}>
            吃貨ⓘ{#if sortKey === 'c1'}&nbsp;{sortOrder === 'asc' ? '▲' : '▼'}{/if}
          </button>
        </th>
        <th title="符合三選二出場條件中至少 2 項（法人連賣 / 融資暴增 / 股價飆升）">
          <button class="sort-btn" class:active={sortKey === 'c2'} on:click={() => toggleSort('c2')}>
            出場ⓘ{#if sortKey === 'c2'}&nbsp;{sortOrder === 'asc' ? '▲' : '▼'}{/if}
          </button>
        </th>
        <th title="連續 2 日收盤低於停損錨點（主力成本或起始價 ×95%）">
          <button class="sort-btn" class:active={sortKey === 'c3'} on:click={() => toggleSort('c3')}>
            停損ⓘ{#if sortKey === 'c3'}&nbsp;{sortOrder === 'asc' ? '▲' : '▼'}{/if}
          </button>
        </th>
        <th>訊號</th>
        <th>
          <button class="sort-btn" class:active={sortKey === 'edinet_recent_count'} on:click={() => toggleSort('edinet_recent_count')}>
            EDINET{#if sortKey === 'edinet_recent_count'}&nbsp;{sortOrder === 'asc' ? '▲' : '▼'}{/if}
          </button>
        </th>
        <th>
          <button class="sort-btn" class:active={sortKey === 'score'} on:click={() => toggleSort('score')}>
            Score{#if sortKey === 'score'}&nbsp;{sortOrder === 'asc' ? '▲' : '▼'}{/if}
          </button>
        </th>
        {#if onRefreshRow}
          <th></th>
        {/if}
      </tr>
    </thead>
    <tbody>
      {#each pagedData as row (row.code)}
        <tr>
          <td>
            <FavoriteToggle code={row.code} name={row.name} tag="speculative" />
          </td>
          <td class="code clickable" on:click={() => onRowClick(row.code)}>{row.code}</td>
          <td class="clickable" on:click={() => onRowClick(row.code)}>{row.name}</td>
          <td class="price">{row.latest_price.toFixed(0)}</td>
          <td
            class="indicator"
            class:active={row.has_accumulation}
            title={row.has_accumulation
              ? '✓ 觸發吃貨訊號：外資或法人連續買超（≥2 期），同期融資餘額下降'
              : '✗ 未觸發吃貨訊號（判斷條件：外資/法人連續買超且融資餘額下降）'}
          >🔵</td>
          <td
            class="indicator"
            class:active={row.has_exit}
            title={row.has_exit
              ? '⚠ 觸發出場警告：符合三選二中至少 2 項條件'
              : '✓ 未觸發出場警告（三選二條件未滿足）'}
          >🟠</td>
          <td
            class="indicator"
            class:active={row.has_stop_loss}
            title={row.has_stop_loss
              ? '🛑 停損已觸發：連續 2 日收盤低於停損錨點'
              : '✓ 未觸發停損'}
          >🔴</td>
          <td>
            {#if row.has_accumulation}
              💹
            {:else if row.has_exit}
              🔔
            {:else if row.has_stop_loss}
              🛑
            {/if}
          </td>
          <td class="center">{row.edinet_recent_count}</td>
          <td class="score" class:positive={row.score > 0} class:negative={row.score < 0}>
            {row.score.toFixed(1)}
          </td>
          {#if onRefreshRow}
            <td class="refresh-cell" on:click|stopPropagation>
              <button
                class="refresh-btn"
                class:spinning={refreshingCodes.has(row.code)}
                title="更新此股資料"
                disabled={refreshingCodes.has(row.code)}
                on:click={() => onRefreshRow && onRefreshRow(row.code)}
              >↻</button>
            </td>
          {/if}
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .table-wrapper {
    width: 100%;
  }

  .signal-legend {
    background: #0a0a0a;
    border: 1px solid #222;
    border-radius: 4px;
    margin-bottom: 12px;
    padding: 8px 12px;
    font-size: 12px;
    color: #aaa;
  }

  .signal-legend summary {
    cursor: pointer;
    color: #888;
    user-select: none;
  }

  .signal-legend summary:hover {
    color: #4ade80;
  }

  .legend-grid {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #1a1a1a;
    line-height: 1.6;
  }

  .legend-grid b {
    color: #ccc;
    margin: 0 4px;
  }

  .dot {
    margin-right: 4px;
  }

  .filters {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
    padding: 12px;
    background: #0a0a0a;
    border-radius: 4px;
  }

  .filters label {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #a1a1a1;
    font-size: 12px;
    cursor: pointer;
  }

  .filters input[type='checkbox'] {
    cursor: pointer;
  }

  .filters input[type='number'] {
    width: 50px;
    padding: 4px;
    background: #1a1a1a;
    border: 1px solid #333;
    color: #fff;
    border-radius: 3px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    background: #0a0a0a;
    border-radius: 4px;
    overflow: hidden;
  }

  thead {
    background: #1a1a1a;
  }

  th {
    padding: 12px 8px;
    text-align: left;
    font-weight: 500;
    color: #888;
    font-size: 12px;
    border-bottom: 1px solid #333;
  }

  td {
    padding: 12px 8px;
    color: #a1a1a1;
    font-size: 12px;
    border-bottom: 1px solid #222;
  }

  tbody tr {
    transition: background-color 0.2s;
  }

  tbody tr:hover {
    background: #1a1a1a;
  }

  td.clickable {
    cursor: pointer;
  }

  td.clickable:hover {
    color: #4ade80;
  }

  .code {
    font-weight: bold;
    color: #fff;
  }

  .price {
    color: #4ade80;
    font-weight: bold;
  }

  .indicator {
    text-align: center;
    opacity: 0.3;
  }

  .indicator.active {
    opacity: 1;
  }

  .center {
    text-align: center;
  }

  .score {
    font-weight: bold;
  }

  .score.positive {
    color: #4ade80;
  }

  .score.negative {
    color: #f87171;
  }

  .sort-btn {
    background: none;
    border: none;
    color: #888;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
    padding: 0;
    transition: color 0.2s;
  }

  .sort-btn:hover {
    color: #4ade80;
  }

  .sort-btn.active {
    color: #4ade80;
  }

  .refresh-cell {
    text-align: center;
    width: 36px;
    padding: 4px;
  }

  .refresh-btn {
    background: none;
    border: 1px solid #444;
    color: #888;
    cursor: pointer;
    border-radius: 4px;
    width: 26px;
    height: 26px;
    font-size: 14px;
    line-height: 1;
    transition: color 0.2s, border-color 0.2s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .refresh-btn:hover:not(:disabled) {
    color: #4ade80;
    border-color: #4ade80;
  }

  .refresh-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .refresh-btn.spinning {
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
