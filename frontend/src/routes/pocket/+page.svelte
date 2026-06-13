<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
  import FavoriteToggle from '$lib/components/FavoriteToggle.svelte';
  import { loadFavorites } from '$lib/stores/favorites';

  interface Gate1 { passed: boolean; lead_filer: string | null; filing_count: number; dates: string[]; doc_types: string[]; }
  interface Gate2 { passed: boolean; master_cost: number | null; latest_price: number | null; premium_pct: number | null; price_date?: string | null; }
  interface Gate3 { passed: boolean; weeks: number; drop_pct: number | null; series: number[]; }
  interface PocketRow { code: string; name: string; in_pocket: boolean; gates_passed: number; gate1: Gate1; gate2: Gate2; gate3: Gate3; }
  interface Funnel { candidates: number; gate1_continuity: number; gate2_cost: number; gate3_margin: number; }
  interface PocketResp { generated_at: string; funnel: Funnel; pocket: PocketRow[]; near_miss: PocketRow[]; params: any; }

  let data: PocketResp | null = null;
  let loading = true;
  let refreshing = false;
  let error: string | null = null;
  // 每檔的「加入追蹤」狀態：'idle' | 'loading' | 'done' | 'error'
  let watchState: Record<string, string> = {};

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

  onMount(() => {
    loadFavorites();
    load();
  });

  const pct = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`);
  const num = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString());
  function barWidth(n: number, total: number): string {
    if (!total) return '0%';
    return `${Math.max(4, Math.round((n / total) * 100))}%`;
  }

  // 溢價配色：負（現價低於主力成本＝便宜）綠、零（等於成本）灰、正（高於成本＝偏貴/接近追高）橙
  function premiumClass(v: number | null | undefined): string {
    if (v == null) return 'prem-na';
    if (v < 0) return 'prem-neg';
    if (v > 0) return 'prem-pos';
    return 'prem-zero';
  }

  // 「現價」實際是最後收盤日的值；距今 > 3 個日曆日視為過期，提示先雲端同步。
  function priceDateLabel(d: string | null | undefined): string {
    return d ? d : '日期不明';
  }
  function priceStaleDays(d: string | null | undefined): number | null {
    if (!d) return null;
    const t = Date.parse(d);
    if (Number.isNaN(t)) return null;
    return Math.floor((Date.now() - t) / 86400000);
  }
  function isPriceStale(d: string | null | undefined): boolean {
    const days = priceStaleDays(d);
    return days != null && days > 3;
  }

  async function addToWatch(r: PocketRow) {
    watchState[r.code] = 'loading';
    watchState = { ...watchState };
    try {
      await api('/watchlist', {
        method: 'POST',
        body: JSON.stringify({
          code: r.code,
          name: r.name,
          start_price: r.gate2.latest_price,
          master_cost: r.gate2.master_cost,
        }),
      });
      watchState[r.code] = 'done';
    } catch (e) {
      watchState[r.code] = 'error';
    }
    watchState = { ...watchState };
  }

  // ── 加入模擬交易（跟單帳本）popup ──
  interface LedgerSummary { id: string; name: string; trade_count: number; }
  let simOpen = false;
  let simRow: PocketRow | null = null;
  let ledgers: LedgerSummary[] = [];
  let simLedgerId = '';
  let simNewLedger = '';
  let simEntryPrice = 0;
  let simShares: number | null = null;
  let simStopPct = 10;        // 移動停損 N%，預設 10
  let simSaving = false;
  let simMsg = '';
  let simQuoteNote = '';      // 即時報價來源說明（成功＝即時，失敗＝fallback 收盤日期）

  async function openSim(r: PocketRow) {
    simRow = r;
    simEntryPrice = r.gate2.latest_price ?? 0;  // 預設帶最後收盤，下面嘗試以即時價覆蓋
    simShares = null;
    simStopPct = 10;
    simNewLedger = '';
    simMsg = '';
    simQuoteNote = `最後收盤 ${priceDateLabel(r.gate2.price_date)}`;
    simOpen = true;
    // 嘗試即時報價（延遲約 20 分）；成功→預設購入價改用即時價，失敗→維持收盤值
    api<{ price: number; price_time: string }>(`/quote/${r.code}`)
      .then((q) => {
        if (q && q.price > 0) {
          simEntryPrice = q.price;
          simQuoteNote = `即時報價（延遲約20分）${q.price_time}`;
        }
      })
      .catch(() => {});
    try {
      ledgers = await api<LedgerSummary[]>('/ledgers');
      simLedgerId = ledgers.length ? ledgers[0].id : '';
    } catch {
      ledgers = [];
      simLedgerId = '';
    }
  }

  function closeSim() {
    simOpen = false;
    simRow = null;
  }

  async function confirmSim() {
    if (!simRow) return;
    if (!simShares || simShares <= 0) { simMsg = '請輸入購入股數'; return; }
    if (!simEntryPrice || simEntryPrice <= 0) { simMsg = '購入時價需大於 0'; return; }
    simSaving = true;
    simMsg = '';
    try {
      let ledgerId = simLedgerId;
      // 沒有選帳本或要新建 → 先建帳本
      if (!ledgerId || simNewLedger.trim()) {
        const created = await api<{ id: string }>('/ledgers', {
          method: 'POST',
          body: JSON.stringify({ name: simNewLedger.trim() || '我的帳本' }),
        });
        ledgerId = created.id;
      }
      await api(`/ledgers/${ledgerId}/trades`, {
        method: 'POST',
        body: JSON.stringify({
          code: simRow.code,
          name: simRow.name,
          entry_price: simEntryPrice,
          shares: simShares,
          stop_pct: simStopPct / 100,
        }),
      });
      simMsg = '✓ 已加入帳本';
      setTimeout(closeSim, 700);
    } catch (e) {
      simMsg = e instanceof Error ? e.message : '加入失敗';
    } finally {
      simSaving = false;
    }
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
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {#each data.pocket as r}
              <tr>
                <td class="code"><FavoriteToggle code={r.code} name={r.name} />{r.code}</td>
                <td>{r.name}</td>
                <td class="filer">{r.gate1.lead_filer ?? '—'}<span class="cnt">×{r.gate1.filing_count}</span></td>
                <td>{num(r.gate2.master_cost)}</td>
                <td title={`最後收盤 ${priceDateLabel(r.gate2.price_date)}`}>
                  {num(r.gate2.latest_price)}
                  <span class="pdate" class:stale={isPriceStale(r.gate2.price_date)}>{priceDateLabel(r.gate2.price_date)}</span>
                </td>
                <td class={premiumClass(r.gate2.premium_pct)}>{pct(r.gate2.premium_pct)}</td>
                <td class="prem-neg">↓ {pct(r.gate3.drop_pct)}</td>
                <td class="actions">
                  <button
                    class="btn-watch"
                    title="加入追蹤清單（帶入主力成本）"
                    disabled={watchState[r.code] === 'loading' || watchState[r.code] === 'done'}
                    on:click={() => addToWatch(r)}
                  >
                    {#if watchState[r.code] === 'done'}✓ 已追蹤
                    {:else if watchState[r.code] === 'loading'}追蹤中…
                    {:else if watchState[r.code] === 'error'}✗ 重試
                    {:else}＋ 追蹤{/if}
                  </button>
                  <button class="btn-sim" title="加入模擬交易帳本" on:click={() => openSim(r)}>
                    模擬交易
                  </button>
                </td>
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
                <td class="code"><FavoriteToggle code={r.code} name={r.name} />{r.code}</td><td>{r.name}</td>
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

{#if simOpen && simRow}
  <div class="modal-backdrop" on:click={closeSim} on:keydown={() => {}} role="presentation">
    <div class="modal" on:click|stopPropagation on:keydown={() => {}} role="dialog">
      <h3>加入模擬交易帳本</h3>
      <p class="modal-stock">{simRow.code} {simRow.name}</p>

      <label>帳本
        <select bind:value={simLedgerId} disabled={!!simNewLedger.trim()}>
          {#if ledgers.length === 0}
            <option value="">（尚無帳本，將自動新建）</option>
          {/if}
          {#each ledgers as lg}
            <option value={lg.id}>{lg.name}（{lg.trade_count} 筆）</option>
          {/each}
        </select>
      </label>
      <label>或新建帳本
        <input type="text" placeholder="輸入新帳本名稱（留空則用現有）" bind:value={simNewLedger} />
      </label>

      <label>購入時價（{simQuoteNote}，可改）
        <input type="number" step="0.1" bind:value={simEntryPrice} />
      </label>
      {#if simQuoteNote.startsWith('最後收盤') && isPriceStale(simRow.gate2.price_date)}
        <p class="price-warn">⚠ 價格資料已是 {priceDateLabel(simRow.gate2.price_date)}，請先回 Dashboard 雲端同步再加入</p>
      {/if}
      <label>購入股數
        <input type="number" step="1" min="1" placeholder="必填" bind:value={simShares} />
      </label>
      <label>移動停損 N%（隔日收盤跌破 high_water×(1−N%) 出場，停損只升不降）
        <input type="number" step="0.5" min="0.5" bind:value={simStopPct} />
      </label>

      {#if simMsg}<p class="modal-msg">{simMsg}</p>{/if}
      <div class="modal-actions">
        <button class="btn-cancel" on:click={closeSim} disabled={simSaving}>取消</button>
        <button class="btn-confirm" on:click={confirmSim} disabled={simSaving}>
          {simSaving ? '加入中…' : '確認加入'}
        </button>
      </div>
    </div>
  </div>
{/if}

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
  .code { font-family: monospace; font-weight: 600; white-space: nowrap; }
  .code :global(.favorite-btn) { font-size: 16px; padding: 0 .35rem 0 0; vertical-align: middle; }
  .filer { max-width: 220px; }
  .cnt { color: #fbbf24; margin-left: .4rem; font-weight: 600; }
  /* 溢價配色：負＝便宜(綠)、零＝持平(灰)、正＝偏貴(橙)、無資料(暗灰) */
  td.prem-neg { color: #34d399; font-weight: 600; }
  td.prem-zero { color: #cbd5e1; }
  td.prem-pos { color: #fb923c; font-weight: 600; }
  td.prem-na { color: #64748b; }
  .actions { white-space: nowrap; }
  .actions button { font-size: .78rem; padding: .3rem .55rem; border: 0; border-radius: 5px; cursor: pointer; margin-right: .35rem; }
  .actions button:disabled { opacity: .6; cursor: default; }
  .btn-watch { background: #0e7490; color: #fff; }
  .btn-sim { background: #6d28d9; color: #fff; }
  .dim { opacity: .8; }

  /* popup */
  .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; z-index: 50; }
  .modal { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.4rem; width: 380px; max-width: 92vw; }
  .modal h3 { margin: 0 0 .3rem; font-size: 1.1rem; }
  .modal-stock { margin: 0 0 1rem; color: #93c5fd; font-family: monospace; font-weight: 600; }
  .modal label { display: block; font-size: .8rem; color: #cbd5e1; margin-bottom: .7rem; }
  .modal input, .modal select { width: 100%; margin-top: .25rem; padding: .4rem .5rem; background: #0f172a; color: #e2e8f0; border: 1px solid #475569; border-radius: 5px; box-sizing: border-box; }
  .modal-msg { font-size: .8rem; color: #fbbf24; margin: .2rem 0 .6rem; }
  .pdate { display: block; font-size: .68rem; color: #64748b; }
  .pdate.stale { color: #f87171; }
  .price-warn { font-size: .78rem; color: #f87171; margin: -.4rem 0 .8rem; line-height: 1.3; }
  .modal-actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: .4rem; }
  .modal-actions button { padding: .45rem .9rem; border: 0; border-radius: 6px; cursor: pointer; font-size: .85rem; }
  .btn-cancel { background: #475569; color: #fff; }
  .btn-confirm { background: #15803d; color: #fff; }
  .modal-actions button:disabled { opacity: .6; cursor: default; }
</style>
