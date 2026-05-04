<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import type { PortfolioEntry, PortfolioLot } from '$lib/types';

  let portfolio: PortfolioEntry[] = [];
  let loading = true;
  let error: string | null = null;

  // 新增 lot 表單
  let addCode = '';
  let addEntryPrice = '';
  let addQuantity = '';
  let addNote = '';
  let addLoading = false;
  let addMsg = '';

  async function loadPortfolio() {
    try {
      portfolio = await api<PortfolioEntry[]>('/portfolio?open_only=true');
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load portfolio';
    } finally {
      loading = false;
    }
  }

  async function handleAdd() {
    if (!addCode || !addEntryPrice || !addQuantity) return;
    addLoading = true;
    addMsg = '';
    try {
      await api('/portfolio', {
        method: 'POST',
        body: JSON.stringify({
          code: addCode.trim(),
          entry_price: parseFloat(addEntryPrice),
          quantity: parseInt(addQuantity),
          note: addNote,
        }),
      });
      addMsg = `✓ 新增成功：${addCode}`;
      addCode = ''; addEntryPrice = ''; addQuantity = ''; addNote = '';
      await loadPortfolio();
    } catch (e) {
      addMsg = `✗ ${e instanceof Error ? e.message : '新增失敗'}`;
    } finally {
      addLoading = false;
    }
  }

  async function handleClose(code: string, lotId: string) {
    const priceStr = prompt(`平倉 ${code}，請輸入賣出價：`);
    if (!priceStr) return;
    const exitPrice = parseFloat(priceStr);
    if (isNaN(exitPrice)) { alert('無效價格'); return; }
    try {
      await api(`/portfolio/${code}/${lotId}/close`, {
        method: 'POST',
        body: JSON.stringify({ exit_price: exitPrice }),
      });
      await loadPortfolio();
    } catch (e) {
      alert(`平倉失敗：${e instanceof Error ? e.message : String(e)}`);
    }
  }

  function pnlClass(v: number | null): string {
    if (v === null) return '';
    return v >= 0 ? 'positive' : 'negative';
  }

  onMount(loadPortfolio);
</script>

<div class="portfolio-page">
  <h1>持倉管理</h1>

  <!-- 新增買入 -->
  <section class="add-section">
    <h2>新增買入</h2>
    <div class="add-form">
      <input class="inp" bind:value={addCode} placeholder="股票代號（e.g. 7203）" />
      <input class="inp" bind:value={addEntryPrice} placeholder="買入價（円）" type="number" />
      <input class="inp" bind:value={addQuantity} placeholder="數量（股）" type="number" />
      <input class="inp" bind:value={addNote} placeholder="備注（可省略）" />
      <button class="btn-add" on:click={handleAdd} disabled={addLoading}>
        {addLoading ? '新增中…' : '＋ 買入'}
      </button>
    </div>
    {#if addMsg}
      <p class="msg" class:error-msg={addMsg.startsWith('✗')}>{addMsg}</p>
    {/if}
  </section>

  <!-- 持倉清單 -->
  <section class="positions-section">
    <h2>持倉清單（未平倉）</h2>

    {#if loading}
      <p class="empty">載入中…</p>
    {:else if error}
      <p class="empty error-msg">{error}</p>
    {:else if portfolio.length === 0}
      <p class="empty">目前無持倉。請使用上方表單新增買入紀錄。</p>
    {:else}
      {#each portfolio as entry}
        <div class="stock-card">
          <div class="stock-header">
            <span class="code">{entry.code}</span>
            <span class="name">{entry.name}</span>
            <span class="total-cost">總成本 ¥{entry.total_cost.toLocaleString()}</span>
            {#if entry.total_unrealized_pnl !== null}
              <span class="pnl {pnlClass(entry.total_unrealized_pnl)}">
                {entry.total_unrealized_pnl >= 0 ? '+' : ''}{entry.total_unrealized_pnl.toLocaleString()}
              </span>
            {/if}
          </div>

          <table class="lot-table">
            <thead>
              <tr>
                <th>買入日</th>
                <th>買入價</th>
                <th>數量</th>
                <th>現價</th>
                <th>未實現損益</th>
                <th>報酬率</th>
                <th>備注</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each entry.lots as lot}
                <tr>
                  <td>{lot.entry_date}</td>
                  <td>¥{lot.entry_price.toLocaleString()}</td>
                  <td>{lot.quantity.toLocaleString()}</td>
                  <td>{lot.current_price !== null ? `¥${lot.current_price.toLocaleString()}` : '—'}</td>
                  <td class={pnlClass(lot.unrealized_pnl)}>
                    {lot.unrealized_pnl !== null
                      ? `${lot.unrealized_pnl >= 0 ? '+' : ''}¥${lot.unrealized_pnl.toLocaleString()}`
                      : '—'}
                  </td>
                  <td class={pnlClass(lot.return_pct)}>
                    {lot.return_pct !== null
                      ? `${lot.return_pct >= 0 ? '+' : ''}${lot.return_pct.toFixed(2)}%`
                      : '—'}
                  </td>
                  <td class="note">{lot.note || '—'}</td>
                  <td>
                    <button class="btn-close" on:click={() => handleClose(lot.code, lot.id)}>
                      平倉
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/each}
    {/if}
  </section>
</div>

<style>
  .portfolio-page {
    max-width: 1100px;
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
    width: 160px;
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

  .msg {
    margin: 8px 0 0;
    font-size: 13px;
    color: #4ade80;
  }

  .error-msg {
    color: #f87171;
  }

  .positions-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .empty {
    color: #6b7280;
    text-align: center;
    padding: 32px;
  }

  .stock-card {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 16px;
  }

  .stock-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .code {
    font-weight: 700;
    font-size: 18px;
    color: #fff;
  }

  .name {
    color: #a1a1a1;
    flex: 1;
  }

  .total-cost {
    color: #6b7280;
    font-size: 13px;
  }

  .pnl {
    font-weight: 600;
    font-size: 14px;
  }

  .positive { color: #4ade80; }
  .negative { color: #f87171; }

  .lot-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .lot-table th {
    text-align: left;
    padding: 8px 10px;
    color: #6b7280;
    border-bottom: 1px solid #333;
    font-weight: 500;
  }

  .lot-table td {
    padding: 8px 10px;
    border-bottom: 1px solid #222;
    color: #e5e7eb;
  }

  .lot-table tr:last-child td {
    border-bottom: none;
  }

  .note {
    color: #6b7280;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .btn-close {
    background: transparent;
    border: 1px solid #ef4444;
    color: #f87171;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
    cursor: pointer;
  }

  .btn-close:hover {
    background: #7f1d1d;
  }
</style>
