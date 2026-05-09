<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  interface WatchlistEntry {
    code: string;
    name: string;
    start_price: number;
    added_date: string | null;
  }

  let watchlist: WatchlistEntry[] = [];
  let loading = true;
  let error: string | null = null;

  let addCode = '';
  let addLoading = false;
  let addMsg = '';

  async function loadWatchlist() {
    try {
      watchlist = await api<WatchlistEntry[]>('/watchlist');
    } catch (e) {
      error = e instanceof Error ? e.message : '載入失敗';
    } finally {
      loading = false;
    }
  }

  async function handleAdd() {
    if (!addCode) return;
    addLoading = true;
    addMsg = '';
    try {
      // 不帶 start_price，由後端自動從 price cache 取當下市場價
      await api('/watchlist', {
        method: 'POST',
        body: JSON.stringify({ code: addCode.trim() }),
      });
      addMsg = `✓ 已加入追蹤：${addCode.trim()}`;
      addCode = '';
      await loadWatchlist();
    } catch (e) {
      addMsg = `✗ ${e instanceof Error ? e.message : '新增失敗'}`;
    } finally {
      addLoading = false;
    }
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') handleAdd();
  }

  async function handleRemove(code: string) {
    if (!confirm(`確認移除 ${code}？`)) return;
    try {
      await api(`/watchlist/${code}`, { method: 'DELETE' });
      await loadWatchlist();
    } catch (e) {
      alert(`移除失敗：${e instanceof Error ? e.message : String(e)}`);
    }
  }

  onMount(loadWatchlist);
</script>

<div class="watchlist-page">
  <h1>追蹤清單</h1>

  <!-- 新增表單 -->
  <section class="add-section">
    <h2>新增追蹤</h2>
    <div class="add-form">
      <input
        class="inp"
        bind:value={addCode}
        placeholder="股票代號（e.g. 7203）"
        on:keydown={onKeydown}
      />
      <button class="btn-add" on:click={handleAdd} disabled={addLoading}>
        {addLoading ? '新增中…' : '＋ 加入追蹤'}
      </button>
    </div>
    <p class="hint">起始價自動以加入當下市場收盤價為基準</p>
    {#if addMsg}
      <p class="msg" class:error-msg={addMsg.startsWith('✗')}>{addMsg}</p>
    {/if}
  </section>

  <!-- 追蹤清單 -->
  <section class="list-section">
    <h2>追蹤中（{watchlist.length} 檔）</h2>

    {#if loading}
      <LoadingSpinner />
    {:else if error}
      <p class="empty error-msg">{error}</p>
    {:else if watchlist.length === 0}
      <p class="empty">目前無追蹤股票。請使用上方表單新增。</p>
    {:else}
      <table class="wl-table">
        <thead>
          <tr>
            <th>代號</th>
            <th>名稱</th>
            <th>起始價</th>
            <th>加入日期</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each watchlist as entry}
            <tr>
              <td class="code">
                <a href="/signals/{entry.code}">{entry.code}</a>
              </td>
              <td class="name">{entry.name || '—'}</td>
              <td>¥{entry.start_price.toLocaleString()}</td>
              <td class="date">{entry.added_date ?? '—'}</td>
              <td>
                <button class="btn-remove" on:click={() => handleRemove(entry.code)}>
                  移除
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
</div>

<style>
  .watchlist-page {
    max-width: 900px;
    margin: 0 auto;
  }

  h1 {
    font-size: 28px;
    color: #4ade80;
    margin: 0 0 24px;
  }

  h2 {
    font-size: 16px;
    color: #a1a1a1;
    margin: 0 0 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .add-section {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 24px;
  }

  .add-form {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
  }

  .inp {
    background: #0f0f0f;
    border: 1px solid #333;
    border-radius: 4px;
    color: #e5e7eb;
    padding: 8px 12px;
    font-size: 14px;
    width: 200px;
  }

  .inp:focus {
    outline: none;
    border-color: #4ade80;
  }

  .btn-add {
    background: #4ade80;
    color: #0f0f0f;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
    cursor: pointer;
    font-size: 14px;
  }

  .btn-add:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .hint {
    color: #4b5563;
    font-size: 12px;
    margin: 6px 0 0 0;
  }

  .msg {
    margin: 8px 0 0;
    font-size: 13px;
    color: #4ade80;
  }

  .error-msg {
    color: #f87171;
  }

  .list-section {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 20px;
  }

  .empty {
    color: #6b7280;
    text-align: center;
    padding: 32px;
    margin: 0;
  }

  .wl-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }

  .wl-table th {
    text-align: left;
    padding: 10px 12px;
    color: #6b7280;
    border-bottom: 1px solid #333;
    font-weight: 500;
  }

  .wl-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #222;
    color: #e5e7eb;
  }

  .wl-table tr:last-child td {
    border-bottom: none;
  }

  .wl-table tr:hover td {
    background: #222;
  }

  .code a {
    color: #fff;
    font-weight: 700;
    text-decoration: none;
  }

  .code a:hover {
    color: #4ade80;
  }

  .name {
    color: #a1a1a1;
  }

  .date {
    color: #6b7280;
    font-size: 13px;
  }

  .btn-remove {
    background: transparent;
    border: 1px solid #ef4444;
    color: #f87171;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
    cursor: pointer;
  }

  .btn-remove:hover {
    background: #7f1d1d;
  }
</style>
