<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';

  interface ExitStrategy {
    atr_period: number;
    initial_stop_atr_mult: number;
    chandelier_atr_mult: number;
    chandelier_high_window: number;
    stage2_threshold_pct: number;
    stage3_threshold_pct: number;
    sma_break_period: number;
    volume_dry_days: number;
    volume_dry_ratio: number;
  }

  let cfg: ExitStrategy | null = null;
  let loading = true;
  let saving = false;
  let msg = '';
  let err = '';

  async function load() {
    loading = true;
    err = '';
    try {
      cfg = await api<ExitStrategy>('/config/exit-strategy');
    } catch (e) {
      err = e instanceof Error ? e.message : '讀取失敗';
    } finally {
      loading = false;
    }
  }

  async function save() {
    if (!cfg) return;
    saving = true;
    msg = '';
    err = '';
    try {
      cfg = await api<ExitStrategy>('/config/exit-strategy', {
        method: 'PUT',
        body: JSON.stringify(cfg),
      });
      msg = '✓ 已儲存';
      setTimeout(() => (msg = ''), 3000);
    } catch (e) {
      err = e instanceof Error ? e.message : '儲存失敗';
    } finally {
      saving = false;
    }
  }

  async function reset() {
    if (!confirm('還原為系統預設？')) return;
    saving = true;
    try {
      cfg = await api<ExitStrategy>('/config/exit-strategy', { method: 'DELETE' });
      msg = '✓ 已還原預設';
      setTimeout(() => (msg = ''), 3000);
    } catch (e) {
      err = e instanceof Error ? e.message : '還原失敗';
    } finally {
      saving = false;
    }
  }

  onMount(load);
</script>

<div class="exit-strategy-page">
  <div class="intro">
    <h2>三階段移動停損策略</h2>
    <p class="desc">
      隨著持倉獲利變化，自動調整停損點位以鎖定獲利。
      <strong>修改後，所有股票的訊號分析會立即套用新參數</strong>（不需重啟）。
    </p>
    <div class="stages-vis">
      <div class="stage s1">
        <h4>Stage 1</h4>
        <p class="trigger">獲利 &lt; {cfg ? (cfg.stage2_threshold_pct * 100).toFixed(0) : 10}%</p>
        <p class="desc-small">初始停損：max(進場 ×95%, 進場 - {cfg ? cfg.initial_stop_atr_mult : 3.0}×ATR)</p>
      </div>
      <div class="arrow">→</div>
      <div class="stage s2">
        <h4>Stage 2</h4>
        <p class="trigger">獲利 ≥ {cfg ? (cfg.stage2_threshold_pct * 100).toFixed(0) : 10}%</p>
        <p class="desc-small">保本：停損移到進場價</p>
      </div>
      <div class="arrow">→</div>
      <div class="stage s3">
        <h4>Stage 3</h4>
        <p class="trigger">獲利 ≥ {cfg ? (cfg.stage3_threshold_pct * 100).toFixed(0) : 25}%</p>
        <p class="desc-small">Chandelier：近 {cfg ? cfg.chandelier_high_window : 20} 日高 - {cfg ? cfg.chandelier_atr_mult : 2.5}×ATR</p>
      </div>
    </div>
  </div>

  {#if loading}
    <p>載入中…</p>
  {:else if err}
    <p class="error">{err}</p>
  {:else if cfg}
    <form on:submit|preventDefault={save} class="form">
      <fieldset>
        <legend>ATR 參數</legend>
        <label>
          <span>ATR 週期</span>
          <input type="number" min="5" max="60" bind:value={cfg.atr_period} />
          <em>典型 14；更短 → 對近期波動更敏感</em>
        </label>
      </fieldset>

      <fieldset>
        <legend>Stage 1 — 初始停損</legend>
        <label>
          <span>ATR 倍數</span>
          <input type="number" step="0.1" min="1" max="10" bind:value={cfg.initial_stop_atr_mult} />
          <em>典型 3.0；越大越寬鬆（避免短期震盪掃出）</em>
        </label>
      </fieldset>

      <fieldset>
        <legend>Stage 2 — 保本門檻</legend>
        <label>
          <span>進入保本獲利 %</span>
          <input type="number" step="0.01" min="0.01" max="1" bind:value={cfg.stage2_threshold_pct} />
          <em>典型 0.10（+10%）；獲利達此值時停損移到進場價</em>
        </label>
      </fieldset>

      <fieldset>
        <legend>Stage 3 — Chandelier Exit</legend>
        <label>
          <span>啟動獲利 %</span>
          <input type="number" step="0.01" min="0.05" max="2" bind:value={cfg.stage3_threshold_pct} />
          <em>典型 0.25（+25%）；必須大於 Stage 2 門檻</em>
        </label>
        <label>
          <span>高點看回天數</span>
          <input type="number" min="5" max="60" bind:value={cfg.chandelier_high_window} />
          <em>典型 20；計算 N 日最高價作 Chandelier 起算點</em>
        </label>
        <label>
          <span>ATR 倍數</span>
          <input type="number" step="0.1" min="1" max="10" bind:value={cfg.chandelier_atr_mult} />
          <em>典型 2.5；越大越寬鬆（讓利潤跑更久但回吐更多）</em>
        </label>
      </fieldset>

      <fieldset>
        <legend>減碼警示（不強制砍倉）</legend>
        <label>
          <span>SMA 跌破週期</span>
          <input type="number" min="5" max="200" bind:value={cfg.sma_break_period} />
          <em>典型 20；收盤跌破且均線走平/向下時警示</em>
        </label>
        <label>
          <span>量能萎縮連續日數</span>
          <input type="number" min="2" max="20" bind:value={cfg.volume_dry_days} />
          <em>典型 5</em>
        </label>
        <label>
          <span>量能萎縮比率</span>
          <input type="number" step="0.05" min="0.1" max="1" bind:value={cfg.volume_dry_ratio} />
          <em>典型 0.5；連 N 日量 &lt; 5 日均量 × 此比率 → 警示</em>
        </label>
      </fieldset>

      <div class="actions">
        <button type="submit" disabled={saving}>{saving ? '儲存中…' : '儲存'}</button>
        <button type="button" class="reset" on:click={reset} disabled={saving}>還原預設</button>
        {#if msg}<span class="msg">{msg}</span>{/if}
      </div>
    </form>
  {/if}
</div>

<style>
  .exit-strategy-page { max-width: 800px; }
  .intro { background: #1a1a1a; padding: 16px; border-radius: 8px; margin-bottom: 24px; }
  .intro h2 { color: #4ade80; margin: 0 0 8px 0; font-size: 18px; }
  .desc { color: #aaa; font-size: 13px; line-height: 1.6; margin: 0 0 16px 0; }
  .desc strong { color: #facc15; }

  .stages-vis { display: flex; align-items: stretch; gap: 12px; margin-top: 16px; }
  .stage { flex: 1; padding: 12px; border-radius: 6px; background: #0a0a0a; border-left: 3px solid; }
  .stage.s1 { border-left-color: #f87171; }
  .stage.s2 { border-left-color: #facc15; }
  .stage.s3 { border-left-color: #4ade80; }
  .stage h4 { margin: 0 0 4px 0; color: #ccc; font-size: 13px; }
  .stage .trigger { margin: 0 0 6px 0; font-size: 12px; color: #888; font-weight: bold; }
  .stage .desc-small { margin: 0; font-size: 11px; color: #aaa; line-height: 1.5; }
  .arrow { color: #555; font-size: 20px; align-self: center; }

  .form { display: flex; flex-direction: column; gap: 16px; }
  fieldset { border: 1px solid #2a2a2a; border-radius: 6px; padding: 12px 16px; background: #1a1a1a; }
  legend { color: #4ade80; font-size: 13px; padding: 0 8px; font-weight: bold; }
  label { display: grid; grid-template-columns: 180px 120px 1fr; gap: 12px; align-items: center; margin-bottom: 8px; }
  label span { color: #ccc; font-size: 13px; }
  label em { color: #666; font-size: 11px; font-style: normal; }
  input[type="number"] { background: #0a0a0a; border: 1px solid #444; color: #fff; padding: 6px 8px; border-radius: 4px; font-size: 13px; }
  input[type="number"]:focus { border-color: #4ade80; outline: none; }

  .actions { display: flex; gap: 12px; align-items: center; margin-top: 16px; }
  button { background: #4ade80; color: #000; border: none; padding: 8px 24px; border-radius: 4px; cursor: pointer; font-weight: bold; }
  button:hover:not(:disabled) { background: #22c55e; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  button.reset { background: #2a2a2a; color: #aaa; }
  button.reset:hover:not(:disabled) { background: #3a3a3a; color: #fff; }
  .msg { color: #4ade80; font-size: 13px; }
  .error { color: #f87171; padding: 12px; background: rgba(248, 113, 113, 0.1); border-radius: 4px; }
</style>
