<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { api } from '$lib/api';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  interface Trade {
    id: string; code: string; name: string;
    entry_date: string; entry_price: number; shares: number; stop_pct: number;
    status: string; high_water: number; stop_line: number; last_advanced_date: string | null;
    exit_date: string | null; exit_price: number | null; exit_reason: string | null;
    pnl_jpy: number | null; pnl_pct: number | null;
  }
  interface Ledger { id: string; name: string; created_at: string; trades: Trade[]; }

  let ledger: Ledger | null = null;
  let loading = true;
  let error: string | null = null;
  let advancing = false;
  let advMsg = '';
  // code -> 即時報價（undefined=載入中，null=取不到）。複用 quote_service（與 portfolio 同源）。
  let quotes: Record<string, { price: number; time: string } | null> = {};

  $: id = $page.params.id;

  async function load() {
    loading = true; error = null;
    try {
      ledger = await api<Ledger>(`/ledgers/${id}`);
      loadQuotes();  // 不 await，先讓表格渲染，現價隨後填入
    } catch (e) {
      error = e instanceof Error ? e.message : '載入失敗';
    } finally {
      loading = false;
    }
  }

  async function loadQuotes() {
    if (!ledger) return;
    const codes = [...new Set(ledger.trades.filter((t) => t.status === 'open').map((t) => t.code))];
    await Promise.all(
      codes.map(async (code) => {
        try {
          const q = await api<{ price: number; price_time: string }>(`/quote/${code}`);
          quotes[code] = { price: q.price, time: q.price_time };
        } catch {
          quotes[code] = null;
        }
      }),
    );
    quotes = quotes;  // 觸發 Svelte 反應
  }

  onMount(load);

  async function advance() {
    advancing = true; advMsg = '';
    try {
      const r = await api<{ advanced_trades: number; closed_trades: number }>(`/ledgers/${id}/advance`, { method: 'POST' });
      advMsg = `推進 ${r.advanced_trades} 筆，新出場 ${r.closed_trades} 筆`;
      await load();
    } catch (e) {
      advMsg = e instanceof Error ? e.message : '推進失敗';
    } finally {
      advancing = false;
    }
  }

  async function removeTrade(tid: string) {
    if (!confirm('刪除這筆交易？')) return;
    try {
      await api(`/ledgers/${id}/trades/${tid}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : '刪除失敗';
    }
  }

  const num = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString());
  const pct = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`);
  const yen = (v: number | null | undefined) => (v == null ? '—' : `¥${Math.round(v).toLocaleString()}`);
</script>

<div class="page">
  <a href="/ledger" class="back">← 返回帳本列表</a>
  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <div class="error">⚠ {error}</div>
  {:else if ledger}
    <header>
      <h1>{ledger.name}</h1>
      <button class="adv" on:click={advance} disabled={advancing}>
        {advancing ? '推進中…' : '↻ 推進到今天（套用移動停損）'}
      </button>
    </header>
    {#if advMsg}<p class="adv-msg">{advMsg}</p>{/if}

    {#if ledger.trades.length === 0}
      <p class="empty">此帳本尚無交易。到三盤口袋名單點「模擬交易」加入。</p>
    {:else}
      <table>
        <thead>
          <tr>
            <th>代碼</th><th>名稱</th><th>進場日</th><th>進場價</th><th>股數</th>
            <th>停損%</th><th>最高收盤</th><th>現價</th><th>目前停損線</th><th>狀態</th>
            <th>出場日</th><th>出場價</th><th>損益</th><th></th>
          </tr>
        </thead>
        <tbody>
          {#each ledger.trades as t}
            <tr class:closed={t.status === 'closed'}>
              <td class="code">{t.code}</td>
              <td>{t.name}</td>
              <td>{t.entry_date}</td>
              <td>{num(t.entry_price)}</td>
              <td>{t.shares.toLocaleString()}</td>
              <td>{pct(t.stop_pct)}</td>
              <td>{num(t.high_water)}</td>
              <td class="quote">
                {#if t.status !== 'open'}
                  —
                {:else if quotes[t.code] === undefined}
                  …
                {:else if quotes[t.code] === null}
                  <span class="muted" title="即時報價取不到">—</span>
                {:else}
                  {@const q = quotes[t.code]}
                  <span class={q && q.price < t.stop_line ? 'neg' : 'pos'} title={q ? '報價時間 ' + q.time : ''}>
                    {q ? num(q.price) : '—'}
                  </span>
                {/if}
              </td>
              <td class="stop">{num(t.stop_line)}</td>
              <td>{t.status === 'open' ? '持有' : '已出場'}</td>
              <td>{t.exit_date ?? '—'}</td>
              <td>{num(t.exit_price)}</td>
              <td class={t.pnl_jpy == null ? '' : t.pnl_jpy >= 0 ? 'pos' : 'neg'}>
                {t.pnl_jpy == null ? '—' : `${yen(t.pnl_jpy)} (${pct(t.pnl_pct)})`}
              </td>
              <td><button class="btn-del" on:click={() => removeTrade(t.id)}>刪</button></td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}
</div>

<style>
  .page { padding: 1.5rem; max-width: 1150px; }
  .back { color: #93c5fd; text-decoration: none; font-size: .85rem; }
  header { display: flex; justify-content: space-between; align-items: center; margin: .6rem 0 .3rem; }
  h1 { margin: 0; font-size: 1.4rem; }
  .adv { background: #2563eb; color: #fff; border: 0; padding: .45rem .9rem; border-radius: 6px; cursor: pointer; }
  .adv:disabled { opacity: .6; cursor: default; }
  .adv-msg { color: #fbbf24; font-size: .82rem; margin: .2rem 0 .6rem; }
  .error { color: #c0392b; padding: 1rem; }
  .empty { color: #777; font-style: italic; }
  table { width: 100%; border-collapse: collapse; font-size: .82rem; }
  th, td { text-align: left; padding: .4rem .5rem; border-bottom: 1px solid #334155; }
  th { color: #94a3b8; }
  .code { font-family: monospace; font-weight: 600; }
  .stop { color: #fbbf24; }
  .quote { font-variant-numeric: tabular-nums; }
  .muted { color: #64748b; }
  tr.closed { opacity: .65; }
  .pos { color: #34d399; }
  .neg { color: #f87171; }
  .btn-del { background: #7f1d1d; color: #fecaca; border: 0; padding: .25rem .5rem; border-radius: 4px; cursor: pointer; font-size: .75rem; }
</style>
