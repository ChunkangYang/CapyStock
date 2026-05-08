<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import CronEditor from './CronEditor.svelte';

  export let initial: any = null;

  type Mode = 'digest' | 'realtime';
  type Severity = 'info' | 'warn' | 'critical';
  type Scope = 'watchlist' | 'favorites' | 'all';

  const ALERT_TYPES = ['exit', 'stop_loss', 'accumulation', 'info'] as const;
  const ALERT_TYPE_LABELS: Record<string, string> = {
    exit: '出場警告',
    stop_loss: '停損觸發',
    accumulation: '吃貨訊號',
    info: '一般資訊',
  };
  const CHANNELS = ['email', 'line'] as const;

  let name: string = initial?.name ?? '';
  let mode: Mode = (initial?.mode as Mode) ?? 'digest';
  let cron: string = initial?.trigger?.time
    ? cronFromHHMM(initial.trigger.time)
    : '0 8 * * *';
  let alertTypes: string[] = initial?.filters?.alert_types ?? ['exit', 'stop_loss'];
  let minSeverity: Severity = (initial?.filters?.min_severity as Severity) ?? 'info';
  let scope: Scope = (initial?.filters?.scope as Scope) ?? 'watchlist';
  let channels: string[] = initial?.channels ?? ['email'];
  let recipientsByChannel: Record<string, string> = mapRecipients(
    initial?.recipients_by_channel ?? {},
  );
  let enabled: boolean = initial?.enabled ?? true;

  function cronFromHHMM(t: string): string {
    const m = /^(\d{1,2}):(\d{2})$/.exec(t);
    if (!m) return '0 8 * * *';
    return `${Number(m[2])} ${Number(m[1])} * * *`;
  }
  function hhmmFromCron(expr: string): string | null {
    const parts = expr.trim().split(/\s+/);
    if (parts.length !== 5) return null;
    const [mm, hh] = parts;
    if (!/^\d+$/.test(mm) || !/^\d+$/.test(hh)) return null;
    return `${hh.padStart(2, '0')}:${mm.padStart(2, '0')}`;
  }
  function mapRecipients(rec: Record<string, string[]>): Record<string, string> {
    const out: Record<string, string> = {};
    for (const k of Object.keys(rec)) out[k] = (rec[k] ?? []).join(', ');
    return out;
  }

  function toggle(arr: string[], val: string): string[] {
    return arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val];
  }

  const dispatch = createEventDispatcher<{ submit: any; cancel: void }>();

  function buildPayload() {
    const recipients_by_channel: Record<string, string[]> = {};
    for (const ch of channels) {
      const raw = (recipientsByChannel[ch] ?? '').trim();
      recipients_by_channel[ch] = raw
        ? raw
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean)
        : [];
    }
    const trigger =
      mode === 'digest'
        ? { schedule: 'daily', time: hhmmFromCron(cron) ?? '08:00' }
        : { on_alert: true };
    const filters: any = {
      min_severity: minSeverity,
      scope,
      codes: [],
    };
    if (mode === 'realtime') filters.alert_types = alertTypes;
    else filters.alert_types = [];

    return {
      name,
      mode,
      trigger,
      filters,
      channels,
      recipients_by_channel,
      enabled,
    };
  }

  function onSubmit() {
    if (!name.trim()) return;
    if (channels.length === 0) return;
    dispatch('submit', buildPayload());
  }
</script>

<form class="rule-form" data-testid="rule-form" on:submit|preventDefault={onSubmit}>
  <label class="row">
    <span>名稱</span>
    <input bind:value={name} required data-testid="rule-name" />
  </label>

  <fieldset class="row">
    <legend>模式</legend>
    <label>
      <input type="radio" bind:group={mode} value="digest" data-testid="mode-digest" />
      Digest（每日彙總）
    </label>
    <label>
      <input type="radio" bind:group={mode} value="realtime" data-testid="mode-realtime" />
      Realtime（即時警報）
    </label>
  </fieldset>

  {#if mode === 'digest'}
    <div class="row" data-testid="digest-fields">
      <span>排程</span>
      <CronEditor bind:value={cron} inline />
    </div>
  {:else}
    <fieldset class="row" data-testid="realtime-fields">
      <legend>警報類型</legend>
      {#each ALERT_TYPES as t}
        <label>
          <input
            type="checkbox"
            checked={alertTypes.includes(t)}
            on:change={() => (alertTypes = toggle(alertTypes, t))}
          />
          {ALERT_TYPE_LABELS[t] ?? t}
        </label>
      {/each}
    </fieldset>
    <fieldset class="row">
      <legend>最低嚴重度</legend>
      <label><input type="radio" bind:group={minSeverity} value="info" /> 一般</label>
      <label><input type="radio" bind:group={minSeverity} value="warn" /> 警告</label>
      <label><input type="radio" bind:group={minSeverity} value="critical" /> 嚴重</label>
    </fieldset>
  {/if}

  <fieldset class="row">
    <legend>適用範圍</legend>
    <label><input type="radio" bind:group={scope} value="watchlist" /> 追蹤清單</label>
    <label><input type="radio" bind:group={scope} value="favorites" /> 自選股</label>
    <label><input type="radio" bind:group={scope} value="all" /> 全部</label>
  </fieldset>

  <fieldset class="row">
    <legend>通知管道</legend>
    {#each CHANNELS as ch}
      <div class="channel-line">
        <label>
          <input
            type="checkbox"
            checked={channels.includes(ch)}
            on:change={() => (channels = toggle(channels, ch))}
          />
          {ch}
        </label>
        {#if channels.includes(ch)}
          <input
            type="text"
            placeholder="收件人（逗號分隔，留空用預設）"
            bind:value={recipientsByChannel[ch]}
          />
        {/if}
      </div>
    {/each}
  </fieldset>

  <label class="row">
    <input type="checkbox" bind:checked={enabled} /> 啟用
  </label>

  <div class="actions">
    <button type="button" on:click={() => dispatch('cancel')}>取消</button>
    <button type="submit" data-testid="rule-submit">儲存</button>
  </div>
</form>

<style>
  .rule-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
  }
  fieldset {
    border: 1px solid #333;
    border-radius: 6px;
    padding: 8px 12px;
  }
  legend {
    color: #9ca3af;
    font-size: 12px;
    padding: 0 4px;
  }
  input[type='text'] {
    background: #111;
    border: 1px solid #333;
    color: #e5e7eb;
    padding: 6px 8px;
    border-radius: 4px;
    min-width: 200px;
  }
  .channel-line {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }
  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
  button[type='submit'] {
    background: #4ade80;
    color: #052e16;
    border: none;
    padding: 8px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
  }
  button[type='button'] {
    background: #1f2937;
    color: #e5e7eb;
    border: 1px solid #333;
    padding: 8px 14px;
    border-radius: 4px;
    cursor: pointer;
  }
</style>
