<script lang="ts">
  import type { SignalConditions } from '$lib/types';

  export let conditions: SignalConditions;
  export let exitAlert: { message: string } | undefined = undefined;

  const conditionLabels = {
    cond_inst_sell: '機構連售',
    cond_margin_surge: '融資暴增',
    cond_price_rise: '股價飆升',
  };

  const conditionTooltips = {
    cond_inst_sell: '外資或法人連續 3 日賣超，且累計賣超量 ≥ 前 10 日買超量的 20%',
    cond_margin_surge: '融資餘額連續 3 週增加，且本週增幅 ≥ 近 8 週均值的 2 倍',
    cond_price_rise: '股價高於近 30 日低點 30% 以上（或已達目標價）',
  };

  type CondKey = 'cond_inst_sell' | 'cond_margin_surge' | 'cond_price_rise';
  const condKeys: CondKey[] = ['cond_inst_sell', 'cond_margin_surge', 'cond_price_rise'];

  $: matchedCount = conditions.matched ?? 0;
  $: isMatched = matchedCount >= 2;
</script>

<div class="gauge-card">
  <h4>三選二條件</h4>
  <div class="conditions">
    {#each condKeys as key}
      <div
        class="condition"
        class:active={conditions[key]}
        title={conditionTooltips[key]}
      >
        <div class="light" class:on={conditions[key]} />
        <div class="cond-text">
          <span class="cond-label">{conditionLabels[key]}</span>
          <span class="cond-hint">{conditionTooltips[key]}</span>
        </div>
      </div>
    {/each}
  </div>
  <div class="status">
    <div class="counter">
      <span class="number">{matchedCount}</span>
      <span class="label">/ 3</span>
    </div>
    <p class="alert-text" class:warning={isMatched}>
      {#if isMatched}
        ⚠ 出場警告
      {:else}
        ✓ 正常
      {/if}
    </p>
  </div>
  {#if exitAlert}
    <p class="exit-detail">{exitAlert.message}</p>
  {/if}
</div>

<style>
  .gauge-card {
    background: #1a1a1a;
    padding: 16px;
    border-radius: 8px;
  }

  .gauge-card h4 {
    color: #fff;
    margin: 0 0 12px 0;
    font-size: 13px;
  }

  .conditions {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
  }

  .condition {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 4px;
    background: #0a0a0a;
    transition: background-color 0.2s;
  }

  .condition.active {
    background: rgba(248, 113, 113, 0.1);
  }

  .light {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #444;
    transition: background-color 0.2s;
  }

  .light.on {
    background: #f87171;
    box-shadow: 0 0 4px rgba(248, 113, 113, 0.5);
  }

  .cond-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .cond-label {
    font-size: 12px;
    color: #a1a1a1;
  }

  .cond-hint {
    font-size: 10px;
    color: #555;
    line-height: 1.3;
  }

  .status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px;
    background: #0a0a0a;
    border-radius: 4px;
  }

  .counter {
    display: flex;
    align-items: baseline;
    gap: 4px;
  }

  .number {
    font-size: 20px;
    font-weight: bold;
    color: #4ade80;
  }

  .label {
    font-size: 12px;
    color: #888;
  }

  .alert-text {
    font-size: 12px;
    margin: 0;
    color: #888;
  }

  .alert-text.warning {
    color: #f87171;
    font-weight: bold;
  }

  .exit-detail {
    font-size: 11px;
    color: #f87171;
    margin: 8px 0 0 0;
    padding: 8px;
    background: rgba(248, 113, 113, 0.05);
    border-radius: 4px;
    line-height: 1.5;
  }
</style>
