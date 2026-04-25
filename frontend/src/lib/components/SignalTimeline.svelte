<script lang="ts">
  import type { Alert } from '$lib/types';

  export let alerts: Alert[] = [];

  const colorMap = {
    exit: '#f87171',
    stop_loss: '#f59e0b',
    accumulation: '#4ade80',
    info: '#60a5fa',
  };

  const iconMap = {
    exit: '↓',
    stop_loss: '⚠',
    accumulation: '📈',
    info: 'ℹ',
  };
</script>

<div class="timeline">
  {#if alerts.length === 0}
    <p>暫無訊號</p>
  {:else}
    <div class="timeline-content">
      {#each alerts as alert, i}
        <div class="timeline-item">
          <div
            class="marker"
            style="background-color: {colorMap[alert.alert_type]}"
            title={alert.alert_type}
          >
            {iconMap[alert.alert_type]}
          </div>
          <div class="content">
            <p class="message">{alert.message}</p>
            <p class="severity" class:critical={alert.severity === 'critical'}>
              [{alert.severity}]
            </p>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .timeline {
    width: 100%;
  }

  p {
    color: #a1a1a1;
    margin: 0;
  }

  .timeline-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 200px;
    overflow-y: auto;
  }

  .timeline-item {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .marker {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    flex-shrink: 0;
    color: #fff;
    font-weight: bold;
  }

  .content {
    flex: 1;
    min-width: 0;
  }

  .message {
    font-size: 12px;
    color: #fff;
    word-break: break-word;
  }

  .severity {
    font-size: 11px;
    color: #888;
    margin: 4px 0 0 0;
  }

  .severity.critical {
    color: #f87171;
  }
</style>
