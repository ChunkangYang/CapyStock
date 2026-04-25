<script lang="ts">
  import FavoriteToggle from './FavoriteToggle.svelte';
  import type { SignalScanRow } from '$lib/types';

  export let data: SignalScanRow[] = [];
  export let onRowClick: (code: string) => void = () => {};

  type SortKey = 'score' | 'latest_price' | 'edinet_recent_count';
  type SortOrder = 'asc' | 'desc';

  let sortKey: SortKey = 'score';
  let sortOrder: SortOrder = 'desc';

  let filterAccumulation = false;
  let filterExit = false;
  let filterStopLoss = false;
  let minScore = 0;

  $: filteredData = data.filter(row => {
    if (filterAccumulation && !row.has_accumulation) return false;
    if (filterExit && !row.has_exit) return false;
    if (filterStopLoss && !row.has_stop_loss) return false;
    if (row.score < minScore) return false;
    return true;
  });

  $: sortedData = [...filteredData].sort((a, b) => {
    let aVal = a[sortKey];
    let bVal = b[sortKey];
    if (aVal === null || aVal === undefined) aVal = 0;
    if (bVal === null || bVal === undefined) bVal = 0;

    const compare = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return sortOrder === 'asc' ? compare : -compare;
  });

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      sortOrder = 'desc';
    }
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
      <input type="number" bind:value={minScore} min="0" />
    </label>
  </div>

  <table>
    <thead>
      <tr>
        <th>★</th>
        <th>代號</th>
        <th>名稱</th>
        <th>
          <button class="sort-btn" on:click={() => toggleSort('latest_price')}>
            價格
            {#if sortKey === 'latest_price'}
              {sortOrder === 'asc' ? '▲' : '▼'}
            {/if}
          </button>
        </th>
        <th>C1</th>
        <th>C2</th>
        <th>C3</th>
        <th>訊號</th>
        <th>
          <button class="sort-btn" on:click={() => toggleSort('edinet_recent_count')}>
            EDINET
            {#if sortKey === 'edinet_recent_count'}
              {sortOrder === 'asc' ? '▲' : '▼'}
            {/if}
          </button>
        </th>
        <th>
          <button class="sort-btn" on:click={() => toggleSort('score')}>
            Score
            {#if sortKey === 'score'}
              {sortOrder === 'asc' ? '▲' : '▼'}
            {/if}
          </button>
        </th>
      </tr>
    </thead>
    <tbody>
      {#each sortedData as row}
        <tr on:click={() => onRowClick(row.code)} class="clickable">
          <td>
            <FavoriteToggle code={row.code} name={row.name} tag="speculative" />
          </td>
          <td class="code">{row.code}</td>
          <td>{row.name}</td>
          <td class="price">{row.latest_price.toFixed(0)}</td>
          <td class="indicator" class:active={row.has_accumulation}>🔴</td>
          <td class="indicator" class:active={row.has_exit}>🟠</td>
          <td class="indicator" class:active={row.has_stop_loss}>🔺</td>
          <td>
            {#if row.has_accumulation}
              📈
            {:else if row.has_exit}
              ⬇
            {:else if row.has_stop_loss}
              ⚠
            {/if}
          </td>
          <td class="center">{row.edinet_recent_count}</td>
          <td class="score" class:positive={row.score > 0} class:negative={row.score < 0}>
            {row.score.toFixed(1)}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .table-wrapper {
    width: 100%;
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

  tr.clickable {
    cursor: pointer;
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
</style>
