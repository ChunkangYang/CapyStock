<script lang="ts">
  import type { SignalConditions } from '$lib/types';

  export let conditions: SignalConditions;

  const conditionLabels = {
    cond_inst_sell: '機構連售',
    cond_margin_surge: '融資暴增',
    cond_price_rise: '股價飆升',
  };

  $: matchedCount = conditions.matched ?? 0;
  $: isMatched = matchedCount >= 2;
</script>

<div class="gauge-card">
  <h4>三選二條件</h4>
  <div class="conditions">
    <div class="condition" class:active={conditions.cond_inst_sell}>
      <div class="light" class:on={conditions.cond_inst_sell} />
      <span>{conditionLabels.cond_inst_sell}</span>
    </div>
    <div class="condition" class:active={conditions.cond_margin_surge}>
      <div class="light" class:on={conditions.cond_margin_surge} />
      <span>{conditionLabels.cond_margin_surge}</span>
    </div>
    <div class="condition" class:active={conditions.cond_price_rise}>
      <div class="light" class:on={conditions.cond_price_rise} />
      <span>{conditionLabels.cond_price_rise}</span>
    </div>
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

  .condition span {
    font-size: 12px;
    color: #a1a1a1;
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
</style>
