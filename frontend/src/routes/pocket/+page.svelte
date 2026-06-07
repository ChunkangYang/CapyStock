<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  interface Gate1 { passed: boolean; lead_filer: string | null; filing_count: number; dates: string[]; doc_types: string[]; }
  interface Gate2 { passed: boolean; master_cost: number | null; latest_price: number | null; premium_pct: number | null; }
  interface Gate3 { passed: boolean; weeks: number; drop_pct: number | null; series: number[]; }
  interface PocketRow { code: string; name: string; in_pocket: boolean; gates_passed: number; gate1: Gate1; gate2: Gate2; gate3: Gate3; }
  interface Funnel { candidates: number; gate1_continuity: number; gate2_cost: number; gate3_margin: number; }
  interface PocketResp { generated_at: string; funnel: Funnel; pocket: PocketRow[]; near_miss: PocketRow[]; params: any; }

  let data: PocketResp | null = null;
  let loading = true;
  let refreshing = false;
  let error: string | null = null;

  async function load(refresh = false) {
    if (refresh) refreshing = true; else loading = true;
    error = null;
    try {
      data = await api<PocketResp>(`/pocket${refresh ? '?refresh=true' : ''}`);
    } catch (e) {
      error = e instanceof Error ? e.message : '載入失敗';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  onMount(() => load());

  const pct = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`);
  const num = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString());
  function barWidth(n: number, total: number): string {
    if (!total) return '0%';
    return `${Math.max(4, Math.round((n / total) * 100))}%`;
  }
</script>

<div class="page">
  <header class="head">
    <div>
      <h1>三盤口袋名單</h1>
      <p class="sub">舅舅心法「每日三盤濾網選股」日本市場對映 — 三關全過才進口袋名單</p>
    </div>
    <button class="refresh" on:click={() => load(true)} disabled={refreshing}>
      {refreshing ? '掃描中…' : '↻ 重新掃描全市場'}
    </button>
  </header>

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <div class="error">⚠ {error}</div>
  {:else if data}
    <p class="meta">產出時間：{data.generated_at}　參數：申報≥{data.params.min_filings}次／窗口{data.params.window_days}日／成本容忍{pct(data.params.cost_tolerance)}／融資降{data.params.margin_weeks}週</p>

    <section class="funnel">
      <h2>三盤漏斗</h2>
      {#each [
        { label: '候選池（有 EDINET 申報）', n: data.funnel.candidates, cls: 'g0' },
        { label: '① 連續性：同一申報人重複申報', n: data.funnel.gate1_continuity, cls: 'g1' },
        { label: '② 成本：現價 ≤ 主力成本 +5%', n: data.funnel.gate2_cost, cls: 'g2' },
        { label: '③ 籌碼：信用残連續下降 → 口袋名單', n: data.funnel.gate3_margin, cls: 'g3' },
      ] as step}
        <div class="frow">
          <div class="flabel">{step.label}</div>
          <div class="ftrack">
            <div class="fbar {step.cls}" style="width:{barWidth(step.n, data.funnel.candidates)}">{step.n}</div>
          </div>
        </div>
      {/each}
    </section>

    <section>
      <h2>口袋名單（{data.pocket.length} 檔）</h2>
      {#if data.pocket.length === 0}
        <p class="empty">今日無三關全過個股 — 空手不會賠錢。</p>
      {:else}
        <table>
          <thead>
            <tr>
              <th>代碼</th><th>名稱</th>
              <th>① 主力申報人 / 次數</th>
              <th>② 主力成本</th><th>現價</th><th>溢價</th>
              <th>③ 融資趨勢（{data.pocket[0].gate3.weeks}週）</th>
            </tr>
          </thead>
          <tbody>
            {#each data.pocket as r}
              <tr>
                <td class="code">{r.code}</td>
                <td>{r.name}</td>
                <td class="filer">{r.gate1.lead_filer ?? '—'}<span class="cnt">×{r.gate1.filing_count}</span></td>
                <td>{num(r.gate2.master_cost)}</td>
                <td>{num(r.gate2.latest_price)}</td>
                <td class:good={(r.gate2.premium_pct ?? 1) <= 0.05}>{pct(r.gate2.premium_pct)}</td>
                <td class="good">↓ {pct(r.gate3.drop_pct)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>

    {#if data.near_miss.length}
      <section>
        <h2>差一關觀察名單（過 2 盤，{data.near_miss.length} 檔）</h2>
        <table class="dim">
          <thead><tr><th>代碼</th><th>名稱</th><th>①</th><th>②</th><th>③</th></tr></thead>
          <tbody>
            {#each data.near_miss.slice(0, 20) as r}
              <tr>
                <td class="code">{r.code}</td><td>{r.name}</td>
                <td>{r.gate1.passed ? '✓' : '✗'}</td>
                <td>{r.gate2.passed ? '✓' : '✗'}</td>
                <td>{r.gate3.passed ? '✓' : '✗'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/if}
  {/if}
</div>

<style>
  .page { padding: 1.5rem; max-width: 1100px; }
  .head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
  h1 { margin: 0 0 .25rem; font-size: 1.5rem; }
  .sub { margin: 0; color: #888; font-size: .85rem; }
  .meta { color: #999; font-size: .8rem; margin: 0 0 1rem; }
  .refresh { background: #2563eb; color: #fff; border: 0; padding: .5rem .9rem; border-radius: 6px; cursor: pointer; }
  .refresh:disabled { opacity: .6; cursor: default; }
  .error { color: #c0392b; padding: 1rem; }
  .empty { color: #777; font-style: italic; }
  .funnel { margin: 0 0 2rem; }
  h2 { font-size: 1.1rem; margin: 1.2rem 0 .6rem; }
  .frow { display: flex; align-items: center; margin: .35rem 0; gap: .75rem; }
  .flabel { flex: 0 0 290px; font-size: .85rem; color: #ccc; }
  .ftrack { flex: 1; background: #1e293b; border-radius: 4px; overflow: hidden; }
  .fbar { color: #fff; text-align: right; padding: .35rem .6rem; font-size: .8rem; font-weight: 600; border-radius: 4px; }
  .fbar.g0 { background: #475569; }
  .fbar.g1 { background: #0e7490; }
  .fbar.g2 { background: #b45309; }
  .fbar.g3 { background: #15803d; }
  table { width: 100%; border-collapse: collapse; font-size: .85rem; }
  th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #334155; }
  th { color: #94a3b8; font-weight: 600; }
  .code { font-family: monospace; font-weight: 600; }
  .filer { max-width: 220px; }
  .cnt { color: #fbbf24; margin-left: .4rem; font-weight: 600; }
  td.good { color: #34d399; }
  .dim { opacity: .8; }
</style>
