<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  interface LedgerSummary {
    id: string; name: string; created_at: string;
    trade_count: number; open_count: number; closed_count: number;
    realized_pnl_jpy: number; unrealized_pnl_jpy: number;
  }

  let ledgers: LedgerSummary[] = [];
  let loading = true;
  let error: string | null = null;
  let newName = '';
  let creating = false;

  async function load() {
    loading = true; error = null;
    try {
      ledgers = await api<LedgerSummary[]>('/ledgers');
    } catch (e) {
      error = e instanceof Error ? e.message : '載入失敗';
    } finally {
      loading = false;
    }
  }

  onMount(load);

  async function create() {
    if (!newName.trim()) return;
    creating = true;
    try {
      await api('/ledgers', { method: 'POST', body: JSON.stringify({ name: newName.trim() }) });
      newName = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '建立失敗';
    } finally {
      creating = false;
    }
  }

  async function remove(id: string, name: string) {
    if (!confirm(`刪除帳本「${name}」？（檔案會改名保留，不會真的刪除）`)) return;
    try {
      await api(`/ledgers/${id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '刪除失敗';
    }
  }

  const yen = (v: number) => `¥${Math.round(v).toLocaleString()}`;
</script>

<div class="page">
  <header>
    <h1>模擬交易帳本</h1>
    <p class="sub">帳本當資料夾用；每筆交易獨立，採棘輪式移動停損（只升不降）出場。新增交易請到「三盤口袋名單」點各檔「模擬交易」。</p>
  </header>

  <div class="create">
    <input type="text" placeholder="新帳本名稱" bind:value={newName} on:keydown={(e) => e.key === 'Enter' && create()} />
    <button on:click={create} disabled={creating || !newName.trim()}>＋ 新建帳本</button>
  </div>

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <div class="error">⚠ {error}</div>
  {:else if ledgers.length === 0}
    <p class="empty">尚無帳本。先新建一個，或到三盤口袋名單加入交易（會自動建帳本）。</p>
  {:else}
    <table>
      <thead>
        <tr><th>帳本</th><th>交易數</th><th>持有</th><th>已出場</th><th>已實現損益</th><th>建立時間</th><th></th></tr>
      </thead>
      <tbody>
        {#each ledgers as lg}
          <tr>
            <td><a href={`/ledger/${lg.id}`} class="name">{lg.name}</a></td>
            <td>{lg.trade_count}</td>
            <td>{lg.open_count}</td>
            <td>{lg.closed_count}</td>
            <td class={lg.realized_pnl_jpy >= 0 ? 'pos' : 'neg'}>{yen(lg.realized_pnl_jpy)}</td>
            <td class="ts">{lg.created_at}</td>
            <td><button class="btn-del" on:click={() => remove(lg.id, lg.name)}>刪除</button></td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .page { padding: 1.5rem; max-width: 950px; }
  h1 { margin: 0 0 .25rem; font-size: 1.5rem; }
  .sub { margin: 0 0 1rem; color: #888; font-size: .85rem; }
  .create { display: flex; gap: .5rem; margin-bottom: 1.2rem; }
  .create input { flex: 0 0 280px; padding: .45rem .6rem; background: #0f172a; color: #e2e8f0; border: 1px solid #475569; border-radius: 6px; }
  .create button { background: #15803d; color: #fff; border: 0; padding: .45rem .9rem; border-radius: 6px; cursor: pointer; }
  .create button:disabled { opacity: .6; cursor: default; }
  .error { color: #c0392b; padding: 1rem; }
  .empty { color: #777; font-style: italic; }
  table { width: 100%; border-collapse: collapse; font-size: .88rem; }
  th, td { text-align: left; padding: .5rem .6rem; border-bottom: 1px solid #334155; }
  th { color: #94a3b8; }
  .name { color: #93c5fd; font-weight: 600; text-decoration: none; }
  .name:hover { text-decoration: underline; }
  .ts { color: #94a3b8; font-size: .8rem; }
  .pos { color: #34d399; }
  .neg { color: #f87171; }
  .btn-del { background: #7f1d1d; color: #fecaca; border: 0; padding: .3rem .6rem; border-radius: 5px; cursor: pointer; font-size: .78rem; }
</style>
