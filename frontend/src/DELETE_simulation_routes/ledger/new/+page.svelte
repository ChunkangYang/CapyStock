<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import type { Simulation, SimulationConfig } from '$lib/types';

  let name = '';
  let initialCapital = 1000000;
  let startDate = new Date().toISOString().split('T')[0];

  // 出場規則（個股套用）
  let stopLossPct = 0.05;        // 跌 5% 停損
  let takeProfitPct = 0.10;      // 漲 10% 停利
  let maxHoldDays = 30;          // 最長持有 30 天
  let useExitSignal = true;      // 訊號出場（matched >= 2）

  // 成本
  let commissionPct = 0.001;
  let slippagePct = 0.001;
  let taxPct = 0.20315;

  let saving = false;
  let error = '';

  async function submit() {
    if (!name.trim()) {
      error = '請輸入帳本名稱';
      return;
    }
    if (initialCapital <= 0) {
      error = '初始資金必須 > 0';
      return;
    }

    saving = true;
    error = '';

    const config: SimulationConfig = {
      kind: 'paper',
      initial_capital: initialCapital,
      start_date: startDate,
      end_date: null,
      candidates: [],
      entry_rule: {
        price_basis: 'user_specified',
        user_price: null,
        require_signal: false,
        indicator_entry: [],
        indicator_entry_logic: 'or',
      },
      exit_rule: {
        use_exit_signal: useExitSignal,
        use_stop_loss: true,
        stop_loss_pct: stopLossPct,
        take_profit_pct: takeProfitPct || null,
        max_hold_days: maxHoldDays || null,
        exit_price_basis: 'next_open',
        indicator_exit: [],
        indicator_exit_logic: 'or',
      },
      position_sizing: {
        mode: 'fixed_jpy',
        fixed_jpy: null,
        fixed_shares: null,
        max_concurrent_positions: 100,
      },
      cost_model: {
        commission_pct: commissionPct,
        slippage_pct: slippagePct,
        tax_pct: taxPct,
      },
    };

    try {
      const sim = await api<Simulation>(`/simulation?name=${encodeURIComponent(name)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      goto(`/simulation/${sim.id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : '建立失敗';
      saving = false;
    }
  }
</script>

<div class="page">
  <div class="header">
    <h1>建立模擬交易帳本</h1>
    <a href="/simulation" class="btn-link">← 返回列表</a>
  </div>

  <p class="hint">
    建立後，從訊號頁面 (<a href="/signals">/signals</a>) 找到看好的標的，按「進場到帳本」即可手動下單。
    每日由排程自動以真實股價更新；觸發停損/停利會自動平倉。
  </p>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  <div class="form">
    <div class="field">
      <label for="name">帳本名稱</label>
      <input id="name" type="text" bind:value={name} placeholder="例: 2026 訊號跟單" />
    </div>

    <div class="field">
      <label for="capital">初始資金 (JPY)</label>
      <input id="capital" type="number" bind:value={initialCapital} min="0" step="100000" />
    </div>

    <div class="field">
      <label for="start">起始日</label>
      <input id="start" type="date" bind:value={startDate} />
    </div>

    <h2>出場規則</h2>

    <div class="field">
      <label for="sl">停損 %（entry 跌破此 % 自動賣出）</label>
      <input id="sl" type="number" bind:value={stopLossPct} step="0.01" min="0" max="1" />
      <small>0.05 = -5%</small>
    </div>

    <div class="field">
      <label for="tp">停利 %（entry 漲過此 % 自動賣出）</label>
      <input id="tp" type="number" bind:value={takeProfitPct} step="0.01" min="0" max="2" />
      <small>0.10 = +10%；填 0 不停利</small>
    </div>

    <div class="field">
      <label for="mh">最長持有天數</label>
      <input id="mh" type="number" bind:value={maxHoldDays} min="0" step="1" />
      <small>到期自動賣出；填 0 不限</small>
    </div>

    <div class="field checkbox">
      <label>
        <input type="checkbox" bind:checked={useExitSignal} />
        系統出場訊號觸發時自動賣出（任 2 個條件成立）
      </label>
    </div>

    <h2>成本模型</h2>

    <div class="field-row">
      <div class="field">
        <label for="com">手續費 %</label>
        <input id="com" type="number" bind:value={commissionPct} step="0.0001" />
      </div>
      <div class="field">
        <label for="slip">滑價 %</label>
        <input id="slip" type="number" bind:value={slippagePct} step="0.0001" />
      </div>
      <div class="field">
        <label for="tax">獲利稅 %</label>
        <input id="tax" type="number" bind:value={taxPct} step="0.0001" />
        <small>日股 0.20315</small>
      </div>
    </div>

    <div class="actions">
      <button class="btn btn-primary" on:click={submit} disabled={saving}>
        {saving ? '建立中...' : '建立帳本'}
      </button>
      <a href="/simulation/new" class="btn-link">使用進階精靈（含 backtest / 指標規則）→</a>
    </div>
  </div>
</div>

<style>
  .page { padding: 20px; max-width: 720px; }
  .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
  h1 { color: #4ade80; font-size: 22px; margin: 0; }
  h2 { color: #4ade80; font-size: 16px; margin: 24px 0 8px; border-top: 1px solid #333; padding-top: 16px; }
  .hint { color: #a1a1a1; font-size: 13px; line-height: 1.6; background: #1a1a1a; padding: 12px; border-radius: 4px; border-left: 3px solid #4ade80; }
  .hint a { color: #4ade80; }
  .error { background: #7f1d1d; color: #fca5a5; padding: 12px; border-radius: 4px; margin: 16px 0; }
  .form { background: #1a1a1a; padding: 20px; border-radius: 6px; border: 1px solid #333; margin-top: 16px; }
  .field { margin-bottom: 14px; }
  .field label { display: block; color: #e5e5e5; font-size: 13px; margin-bottom: 6px; }
  .field input[type="text"], .field input[type="number"], .field input[type="date"] {
    width: 100%; padding: 8px 10px; background: #0a0a0a; color: #fff; border: 1px solid #333; border-radius: 4px; font-size: 14px;
  }
  .field small { display: block; color: #6b7280; font-size: 11px; margin-top: 4px; }
  .field.checkbox label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
  .field-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  .actions { margin-top: 24px; display: flex; align-items: center; gap: 16px; }
  .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
  .btn-primary { background: #4ade80; color: #1a1a1a; font-weight: 500; }
  .btn-primary:hover { background: #3dd66f; }
  .btn-primary:disabled { opacity: 0.5; cursor: wait; }
  .btn-link { color: #4ade80; text-decoration: none; font-size: 13px; }
  .btn-link:hover { text-decoration: underline; }
</style>
