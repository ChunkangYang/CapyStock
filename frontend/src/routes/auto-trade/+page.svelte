<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
  import EquityChart from '$lib/components/EquityChart.svelte';
  import TradePriceChart from '$lib/components/TradePriceChart.svelte';

  interface Holding {
    trade_id: string; code: string; name: string; entry_date: string; entry_price: number;
    shares: number; last_close: number; last_close_date: string | null;
    stop_line: number; high_water: number; market_value_jpy: number;
    unrealized_pnl_jpy: number; unrealized_pnl_pct: number;
  }
  interface ClosedTrade {
    code: string; name: string; entry_date: string; entry_price: number;
    exit_date: string | null; exit_price: number | null; shares: number;
    pnl_jpy: number; pnl_pct: number | null; exit_reason: string | null;
    exit_reason_label?: string | null;
  }
  interface Summary {
    ledger_id: string; ledger_name: string; as_of: string;
    last_log_date: string | null; log_count: number;
    cash_jpy: number; market_value_jpy: number; equity_jpy: number; initial_cash_jpy: number;
    realized_pnl_jpy: number; unrealized_pnl_jpy: number; total_return_pct: number;
    open_count: number; closed_count: number; win_rate: number | null;
    avg_win_jpy: number; avg_loss_jpy: number;
    holdings: Holding[]; closed_trades: ClosedTrade[];
  }
  interface EquityCurve {
    dates: string[]; equity: number[]; cash: number[]; market_value: number[];
    initial_cash_jpy: number; start: string | null; end: string;
  }
  interface DailyLog {
    date: string; equity_jpy: number; cash_jpy: number; realized_pnl_jpy: number;
    unrealized_pnl_jpy: number; total_return_pct: number; open_count: number;
    pocket_candidates: number;
    opened: { code: string; name: string; shares: number; entry_price: number; reason: string }[];
    closed: { code: string; name: string; pnl_jpy: number; pnl_pct: number | null;
              exit_price: number | null; exit_reason: string | null }[];
    missed?: { code: string; name: string; rank: number; drop_pct: number | null;
               reason: string }[];
  }

  // 出場理由中文標籤（後端也會給 exit_reason_label，這裡是 log 端的備援）
  const EXIT_LABEL: Record<string, string> = {
    trailing_stop: '移動停損', time_stop: '時間停損',
    off_list: '訊號失效', manual: '手動平倉'
  };
  const exitLabel = (r: string | null | undefined) => (r ? (EXIT_LABEL[r] ?? r) : '');

  let summary: Summary | null = null;
  let curve: EquityCurve | null = null;
  let logs: DailyLog[] = [];
  let loading = true;
  let error: string | null = null;
  let expanded: string | null = null;

  // 單筆交易價格走勢 modal
  let chartTrade: { code: string; name: string } | null = null;
  let chartData: any = null;

  async function load() {
    loading = true; error = null;
    try {
      [summary, curve, logs] = await Promise.all([
        api<Summary>('/auto-trade/summary'),
        api<EquityCurve>('/auto-trade/equity'),
        api<DailyLog[]>('/auto-trade/logs?days=60'),
      ]);
    } catch (e) {
      error = e instanceof Error ? e.message : '載入失敗';
    } finally {
      loading = false;
    }
  }

  onMount(load);

  async function openChart(h: Holding) {
    chartTrade = { code: h.code, name: h.name };
    chartData = null;
    try {
      chartData = await api(`/ledgers/${summary!.ledger_id}/trades/${h.trade_id}/price`);
    } catch (e) {
      chartData = { error: e instanceof Error ? e.message : '載入失敗' };
    }
  }

  const yen = (v: number | null | undefined) => `¥${Math.round(v ?? 0).toLocaleString()}`;
  const pct = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(2)}%`);
  const sign = (v: number | null | undefined) => ((v ?? 0) >= 0 ? 'pos' : 'neg');
</script>

<div class="page">
  <header>
    <h1>🤖 自動模擬交易</h1>
    <p class="sub">
      每個交易日收盤後由 GitHub Actions 自動執行：進場＝三盤口袋名單（純門檻，無 LLM 判斷），
      出場＝棘輪式移動停損。此頁唯讀，帳本不可手動修改。
      {#if summary}<span class="asof">資料日 {summary.as_of}｜最後交易 log {summary.last_log_date ?? '—'}（共 {summary.log_count} 日）</span>{/if}
    </p>
  </header>

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <div class="error">⚠ {error}</div>
  {:else if summary}
    <div class="tiles">
      <div class="tile">
        <span class="label">總權益</span>
        <span class="value">{yen(summary.equity_jpy)}</span>
        <span class={`delta ${sign(summary.total_return_pct)}`}>{pct(summary.total_return_pct)}</span>
      </div>
      <div class="tile">
        <span class="label">已實現損益</span>
        <span class={`value ${sign(summary.realized_pnl_jpy)}`}>{yen(summary.realized_pnl_jpy)}</span>
        <span class="delta">{summary.closed_count} 筆結算</span>
      </div>
      <div class="tile">
        <span class="label">未實現（暫定）</span>
        <span class={`value ${sign(summary.unrealized_pnl_jpy)}`}>{yen(summary.unrealized_pnl_jpy)}</span>
        <span class="delta">{summary.open_count} 檔持倉</span>
      </div>
      <div class="tile">
        <span class="label">現金 / 持倉市值</span>
        <span class="value small">{yen(summary.cash_jpy)}<br />{yen(summary.market_value_jpy)}</span>
        <span class="delta">起始 {yen(summary.initial_cash_jpy)}</span>
      </div>
      <div class="tile">
        <span class="label">勝率</span>
        <span class="value">{summary.win_rate == null ? '—' : `${Math.round(summary.win_rate * 100)}%`}</span>
        <span class="delta">均賺 {yen(summary.avg_win_jpy)}／均賠 {yen(summary.avg_loss_jpy)}</span>
      </div>
    </div>

    <section>
      <h2>資金曲線</h2>
      {#if curve && curve.dates.length}
        <EquityChart
          dates={curve.dates}
          equity={curve.equity}
          cash={curve.cash}
          marketValue={curve.market_value}
          initialCash={curve.initial_cash_jpy}
        />
      {:else}
        <p class="empty">尚無交易，曲線待第一筆進場後產生。</p>
      {/if}
    </section>

    <section>
      <h2>持倉中（暫定收益）</h2>
      {#if summary.holdings.length === 0}
        <p class="empty">目前無持倉。</p>
      {:else}
        <table>
          <thead>
            <tr>
              <th>代碼</th><th>名稱</th><th>進場日</th><th>進場價</th><th>股數</th>
              <th>現價(收盤)</th><th>市值</th><th>暫定損益</th><th>%</th><th>停損線</th><th></th>
            </tr>
          </thead>
          <tbody>
            {#each summary.holdings as h}
              <tr>
                <td><a href={`/signals/${h.code}`}>{h.code}</a></td>
                <td>{h.name}</td>
                <td class="ts">{h.entry_date}</td>
                <td>{yen(h.entry_price)}</td>
                <td>{h.shares}</td>
                <td>{yen(h.last_close)}<span class="ts"> {h.last_close_date ?? ''}</span></td>
                <td>{yen(h.market_value_jpy)}</td>
                <td class={sign(h.unrealized_pnl_jpy)}>{yen(h.unrealized_pnl_jpy)}</td>
                <td class={sign(h.unrealized_pnl_pct)}>{pct(h.unrealized_pnl_pct)}</td>
                <td class="ts">{yen(h.stop_line)}</td>
                <td><button class="btn-chart" on:click={() => openChart(h)}>📈 圖</button></td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>

    <section>
      <h2>已結算交易</h2>
      {#if summary.closed_trades.length === 0}
        <p class="empty">尚無已結算交易。</p>
      {:else}
        <table>
          <thead>
            <tr>
              <th>代碼</th><th>名稱</th><th>進場日</th><th>進場價</th>
              <th>出場日</th><th>出場價</th><th>股數</th><th>實現損益</th><th>%</th><th>原因</th>
            </tr>
          </thead>
          <tbody>
            {#each summary.closed_trades as c}
              <tr>
                <td><a href={`/signals/${c.code}`}>{c.code}</a></td>
                <td>{c.name}</td>
                <td class="ts">{c.entry_date}</td>
                <td>{yen(c.entry_price)}</td>
                <td class="ts">{c.exit_date ?? '—'}</td>
                <td>{yen(c.exit_price)}</td>
                <td>{c.shares}</td>
                <td class={sign(c.pnl_jpy)}>{yen(c.pnl_jpy)}</td>
                <td class={sign(c.pnl_pct)}>{pct(c.pnl_pct)}</td>
                <td class="ts">{c.exit_reason_label ?? exitLabel(c.exit_reason)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>

    <section>
      <h2>每日交易 log</h2>
      {#if logs.length === 0}
        <p class="empty">尚無 log（第一次 Actions 執行後產生）。</p>
      {:else}
        <table>
          <thead>
            <tr><th>日期</th><th>權益</th><th>報酬</th><th>持倉</th><th>進場</th><th>出場</th><th>口袋候選</th><th></th></tr>
          </thead>
          <tbody>
            {#each logs as lg}
              <tr>
                <td class="ts">{lg.date}</td>
                <td>{yen(lg.equity_jpy)}</td>
                <td class={sign(lg.total_return_pct)}>{pct(lg.total_return_pct)}</td>
                <td>{lg.open_count}</td>
                <td class="pos">{lg.opened.length}</td>
                <td class="neg">{lg.closed.length}</td>
                <td class="ts">{lg.pocket_candidates}</td>
                <td>
                  <button class="btn-chart" on:click={() => (expanded = expanded === lg.date ? null : lg.date)}>
                    {expanded === lg.date ? '收合' : '明細'}
                  </button>
                </td>
              </tr>
              {#if expanded === lg.date}
                <tr class="detail">
                  <td colspan="8">
                    {#if lg.opened.length}
                      <div class="d-title pos">🟢 進場</div>
                      {#each lg.opened as o}
                        <div class="d-row">{o.code} {o.name}　{o.shares} 股 @{yen(o.entry_price)}　<span class="ts">{o.reason}</span></div>
                      {/each}
                    {/if}
                    {#if lg.closed.length}
                      <div class="d-title neg">🔴 出場</div>
                      {#each lg.closed as c}
                        <div class="d-row">{c.code} {c.name}　@{yen(c.exit_price)}
                          <span class={sign(c.pnl_jpy)}>{yen(c.pnl_jpy)}（{pct(c.pnl_pct)}）</span>
                          <span class="ts"> {exitLabel(c.exit_reason)}</span></div>
                      {/each}
                    {/if}
                    {#if lg.missed?.length}
                      <div class="d-title warn">⚠️ 額度滿錯過的合格候選</div>
                      {#each lg.missed as m}
                        <div class="d-row">#{m.rank} {m.code} {m.name}
                          <span class="ts">　融資降 {m.drop_pct != null ? (m.drop_pct * 100).toFixed(0) + '%' : '—'}　{m.reason}</span></div>
                      {/each}
                    {/if}
                    {#if !lg.opened.length && !lg.closed.length}
                      <div class="d-row ts">當日無進出場</div>
                    {/if}
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      {/if}
    </section>
  {/if}
</div>

{#if chartTrade}
  <div
    class="modal-bg"
    role="button"
    tabindex="0"
    on:click={() => (chartTrade = null)}
    on:keydown={(e) => e.key === 'Escape' && (chartTrade = null)}
  >
    <div class="modal" role="dialog" tabindex="-1" on:click|stopPropagation on:keydown|stopPropagation>
      <h3>{chartTrade.code} {chartTrade.name}　進場至今走勢</h3>
      {#if !chartData}
        <LoadingSpinner />
      {:else if chartData.error}
        <div class="error">⚠ {chartData.error}</div>
      {:else}
        <TradePriceChart
          dates={chartData.dates}
          closes={chartData.closes}
          entryPrice={chartData.entry_price}
          stopLine={chartData.stop_line}
          exitDate={chartData.exit_date}
          exitPrice={chartData.exit_price}
        />
      {/if}
      <button class="btn-close" on:click={() => (chartTrade = null)}>關閉</button>
    </div>
  </div>
{/if}

<style>
  .page { padding: 1.5rem; max-width: 1200px; }
  h1 { margin: 0 0 .25rem; font-size: 1.5rem; }
  h2 { font-size: 1.05rem; margin: 1.6rem 0 .6rem; color: #cbd5e1; }
  .sub { margin: 0 0 1rem; color: #888; font-size: .85rem; line-height: 1.6; }
  .asof { display: block; color: #64748b; }
  .error { color: #f87171; padding: 1rem; }
  .empty { color: #777; font-style: italic; }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .8rem; }
  .tile { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: .8rem .9rem;
          display: flex; flex-direction: column; gap: .25rem; }
  .tile .label { color: #94a3b8; font-size: .78rem; }
  .tile .value { font-size: 1.35rem; font-weight: 700; color: #e2e8f0; }
  .tile .value.small { font-size: .95rem; font-weight: 600; line-height: 1.4; }
  .tile .delta { font-size: .75rem; color: #64748b; }
  table { width: 100%; border-collapse: collapse; font-size: .86rem; }
  th, td { text-align: left; padding: .45rem .55rem; border-bottom: 1px solid #1e293b; }
  th { color: #94a3b8; font-weight: 600; }
  td a { color: #93c5fd; text-decoration: none; }
  td a:hover { text-decoration: underline; }
  .ts { color: #64748b; font-size: .78rem; }
  .pos { color: #34d399; }
  .neg { color: #f87171; }
  .warn { color: #fbbf24; }
  .btn-chart { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; padding: .22rem .5rem;
               border-radius: 5px; cursor: pointer; font-size: .76rem; }
  .detail td { background: #0b1220; }
  .d-title { font-size: .8rem; margin: .3rem 0 .15rem; }
  .d-row { font-size: .82rem; color: #cbd5e1; padding: .1rem 0 .1rem .8rem; }
  .modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex;
              align-items: center; justify-content: center; z-index: 50; }
  .modal { background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 1rem;
           width: min(880px, 92vw); }
  .modal h3 { margin: 0 0 .6rem; font-size: 1rem; color: #e2e8f0; }
  .btn-close { margin-top: .6rem; background: #334155; color: #e2e8f0; border: 0; padding: .35rem .9rem;
               border-radius: 6px; cursor: pointer; }
</style>
