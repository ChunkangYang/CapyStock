<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let value: string = '0 8 * * *';
  export let inline = false;

  const dispatch = createEventDispatcher<{ change: string }>();

  function describeCron(expr: string): { ok: boolean; text: string } {
    const trimmed = expr.trim();
    const parts = trimmed.split(/\s+/);
    if (parts.length !== 5) return { ok: false, text: '無效（需 5 欄）' };
    const [m, h, dom, mon, dow] = parts;

    const isInt = (s: string) => /^\d+$/.test(s);
    const inRange = (s: string, lo: number, hi: number) =>
      isInt(s) && Number(s) >= lo && Number(s) <= hi;

    const isStep = (s: string) => /^\*\/\d+$/.test(s);
    if (!(m === '*' || inRange(m, 0, 59) || isStep(m))) return { ok: false, text: '分無效' };
    if (!(h === '*' || inRange(h, 0, 23) || isStep(h))) return { ok: false, text: '時無效' };

    const pad = (n: string) => n.padStart(2, '0');
    const time = isInt(h) && isInt(m) ? `${pad(h)}:${pad(m)}` : null;

    if (dom === '*' && mon === '*' && dow === '*' && time) {
      return { ok: true, text: `每日 ${time}` };
    }
    if (dom === '*' && mon === '*' && /^[0-6](-[0-6])?$/.test(dow) && time) {
      const map = ['週日', '週一', '週二', '週三', '週四', '週五', '週六'];
      if (dow === '1-5') return { ok: true, text: `平日 ${time}` };
      const single = Number(dow);
      if (!Number.isNaN(single)) return { ok: true, text: `${map[single]} ${time}` };
    }
    if (m === '0' && h === '*' && dom === '*' && mon === '*' && dow === '*') {
      return { ok: true, text: '每小時整點' };
    }
    if (/^\*\/\d+$/.test(m) && h === '*' && dom === '*' && mon === '*' && dow === '*') {
      const n = m.split('/')[1];
      return { ok: true, text: `每 ${n} 分鐘` };
    }
    return { ok: true, text: trimmed };
  }

  $: parsed = describeCron(value);

  function onInput(e: Event) {
    const target = e.target as HTMLInputElement;
    value = target.value;
    dispatch('change', value);
  }
</script>

<div class="cron" class:inline data-testid="cron-editor">
  <input
    type="text"
    bind:value
    on:input={onInput}
    placeholder="0 8 * * *"
    class:invalid={!parsed.ok}
    aria-label="cron expression"
  />
  <span class="hint" class:err={!parsed.ok} data-testid="cron-hint">{parsed.text}</span>
</div>

<style>
  .cron {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .cron.inline {
    flex-direction: row;
    align-items: center;
    gap: 8px;
  }
  input {
    background: #111;
    border: 1px solid #333;
    color: #e5e7eb;
    padding: 6px 8px;
    border-radius: 4px;
    font-family: ui-monospace, monospace;
    font-size: 13px;
    min-width: 140px;
  }
  input.invalid {
    border-color: #ef4444;
  }
  .hint {
    font-size: 12px;
    color: #9ca3af;
  }
  .hint.err {
    color: #ef4444;
  }
</style>
