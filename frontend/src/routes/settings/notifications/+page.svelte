<script lang="ts">
  import { onMount } from 'svelte';
  import { api, ApiError } from '$lib/api';
  import RuleForm from '$lib/components/RuleForm.svelte';

  type Channel = { name: string; configured: boolean; healthy: boolean };
  type Rule = {
    id: string;
    name: string;
    mode: 'digest' | 'realtime';
    trigger: { schedule?: string; time?: string; on_alert?: boolean };
    filters: { alert_types: string[]; min_severity: string; scope: string; codes: string[] };
    channels: string[];
    recipients_by_channel: Record<string, string[]>;
    enabled: boolean;
  };
  type LogEntry = {
    ts: string;
    channel: string;
    recipient: string;
    severity: string;
    title: string;
    ok: boolean;
    error: string | null;
    tags: string[];
  };

  let channels: Channel[] = [];
  let rules: Rule[] = [];
  let logs: LogEntry[] = [];
  let toast: { kind: 'ok' | 'err'; text: string } | null = null;

  let logFilterChannel = '';
  let logFilterSeverity = '';

  let editing: Rule | null = null;
  let creatingNew = false;
  let preview: { open: boolean; html: string; title: string } = {
    open: false,
    html: '',
    title: '',
  };

  let loading = true;
  let errorMsg = '';

  async function loadAll() {
    loading = true;
    errorMsg = '';
    try {
      [channels, rules, logs] = await Promise.all([
        api<Channel[]>('/notify/channels'),
        api<Rule[]>('/notify/rules'),
        loadLogs(),
      ]);
    } catch (e) {
      errorMsg = e instanceof ApiError ? e.detail : String(e);
    } finally {
      loading = false;
    }
  }

  async function loadLogs(): Promise<LogEntry[]> {
    const params = new URLSearchParams({ days: '7' });
    if (logFilterChannel) params.set('channel', logFilterChannel);
    if (logFilterSeverity) params.set('severity', logFilterSeverity);
    return api<LogEntry[]>(`/notify/log?${params.toString()}`);
  }

  async function refreshLogs() {
    try {
      logs = await loadLogs();
    } catch (e) {
      errorMsg = e instanceof ApiError ? e.detail : String(e);
    }
  }

  function showToast(kind: 'ok' | 'err', text: string) {
    toast = { kind, text };
    setTimeout(() => (toast = null), 3000);
  }

  async function testChannel(name: string) {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE || '/api/v1'}/notify/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel: name }),
      });
      const body = await res.json();
      if (res.ok) showToast('ok', `${name} 測試送出`);
      else showToast('err', `${name} 失敗（${res.status}）`);
      return body;
    } catch (e) {
      showToast('err', `${name} 失敗：${e}`);
    }
  }

  async function toggleRule(rule: Rule) {
    try {
      const updated = await api<Rule>(`/notify/rules/${rule.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      rules = rules.map((r) => (r.id === rule.id ? updated : r));
      showToast('ok', `${rule.name} ${updated.enabled ? '啟用' : '停用'}`);
    } catch (e) {
      showToast('err', `更新失敗：${e}`);
    }
  }

  async function deleteRule(rule: Rule) {
    if (!confirm(`刪除規則「${rule.name}」？`)) return;
    try {
      await api(`/notify/rules/${rule.id}`, { method: 'DELETE' });
      rules = rules.filter((r) => r.id !== rule.id);
      showToast('ok', '已刪除');
    } catch (e) {
      showToast('err', `刪除失敗：${e}`);
    }
  }

  async function runRule(rule: Rule) {
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_BASE || '/api/v1'}/notify/rules/${rule.id}/run`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dry_run: false }),
        },
      );
      if (res.ok) showToast('ok', '已觸發');
      else showToast('err', `失敗（${res.status}）`);
      await refreshLogs();
    } catch (e) {
      showToast('err', `觸發失敗：${e}`);
    }
  }

  async function previewRule(rule: Rule) {
    try {
      const payload = await api<{ title: string; body_html: string | null; body_text: string }>(
        '/notify/digest/preview',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rule_id: rule.id }),
        },
      );
      preview = {
        open: true,
        title: payload.title || rule.name,
        html: payload.body_html || `<pre>${escapeHtml(payload.body_text)}</pre>`,
      };
    } catch (e) {
      showToast('err', `預覽失敗：${e}`);
    }
  }

  function escapeHtml(s: string) {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  async function onRuleSubmit(payload: any) {
    try {
      if (editing) {
        const updated = await api<Rule>(`/notify/rules/${editing.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        rules = rules.map((r) => (r.id === editing!.id ? updated : r));
        showToast('ok', '已更新');
      } else {
        const created = await api<Rule>('/notify/rules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        rules = [...rules, created];
        showToast('ok', '已建立');
      }
      editing = null;
      creatingNew = false;
    } catch (e) {
      showToast('err', `儲存失敗：${e}`);
    }
  }

  function summary(rule: Rule) {
    if (rule.mode === 'digest') {
      return `digest @ ${rule.trigger.time ?? '–'}`;
    }
    const parts = [
      rule.filters.alert_types.length ? rule.filters.alert_types.join('/') : 'any',
      rule.filters.min_severity,
    ];
    return `realtime · ${parts.join(' · ')}`;
  }

  onMount(loadAll);
</script>

<div class="page" data-testid="notifications-page">
  <h2>通知設定</h2>

  {#if errorMsg}
    <div class="error">{errorMsg}</div>
  {/if}

  <section>
    <h3>Channels</h3>
    <div class="channel-grid" data-testid="channel-grid">
      {#each channels as ch}
        <div class="channel-card" data-testid={`channel-${ch.name}`}>
          <div class="head">
            <span class="dot" class:ok={ch.configured && ch.healthy} class:warn={ch.configured && !ch.healthy} class:off={!ch.configured}></span>
            <strong>{ch.name}</strong>
          </div>
          <div class="meta">
            configured: {ch.configured ? '✔' : '✘'} · healthy: {ch.healthy ? '✔' : '✘'}
          </div>
          <button on:click={() => testChannel(ch.name)} data-testid={`test-${ch.name}`}>
            測試發送
          </button>
        </div>
      {/each}
      {#if !loading && channels.length === 0}
        <p class="empty">尚未設定任何通道</p>
      {/if}
    </div>
  </section>

  <section>
    <div class="section-head">
      <h3>Rules</h3>
      <button class="primary" on:click={() => { creatingNew = true; editing = null; }} data-testid="new-rule">
        + 新規則
      </button>
    </div>
    <table class="rules-table" data-testid="rules-table">
      <thead>
        <tr>
          <th>啟用</th>
          <th>Name</th>
          <th>Mode</th>
          <th>Summary</th>
          <th>Channels</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {#each rules as r (r.id)}
          <tr data-testid={`rule-row-${r.id}`}>
            <td>
              <input
                type="checkbox"
                checked={r.enabled}
                on:change={() => toggleRule(r)}
                data-testid={`toggle-${r.id}`}
              />
            </td>
            <td>{r.name}</td>
            <td>{r.mode}</td>
            <td>{summary(r)}</td>
            <td>{r.channels.join(', ')}</td>
            <td>
              <button on:click={() => { editing = r; creatingNew = false; }}>編輯</button>
              <button on:click={() => runRule(r)}>立即執行</button>
              <button on:click={() => previewRule(r)} data-testid={`preview-${r.id}`}>Preview</button>
              <button on:click={() => deleteRule(r)} class="danger">刪除</button>
            </td>
          </tr>
        {/each}
        {#if !loading && rules.length === 0}
          <tr><td colspan="6" class="empty">尚無規則</td></tr>
        {/if}
      </tbody>
    </table>
  </section>

  <section>
    <div class="section-head">
      <h3>最近 7 日推送 log</h3>
      <div class="filters">
        <select bind:value={logFilterChannel} on:change={refreshLogs}>
          <option value="">all channels</option>
          <option value="email">email</option>
          <option value="line">line</option>
        </select>
        <select bind:value={logFilterSeverity} on:change={refreshLogs}>
          <option value="">all severities</option>
          <option value="info">info</option>
          <option value="warn">warn</option>
          <option value="critical">critical</option>
        </select>
      </div>
    </div>
    <table class="log-table" data-testid="log-table">
      <thead>
        <tr>
          <th>Time</th>
          <th>Channel</th>
          <th>Recipient</th>
          <th>Severity</th>
          <th>Title</th>
          <th>OK</th>
        </tr>
      </thead>
      <tbody>
        {#each logs as l}
          <tr>
            <td>{new Date(l.ts).toLocaleString()}</td>
            <td>{l.channel}</td>
            <td>{l.recipient}</td>
            <td>{l.severity}</td>
            <td>{l.title}</td>
            <td>{l.ok ? '✔' : '✘'}</td>
          </tr>
        {/each}
        {#if !loading && logs.length === 0}
          <tr><td colspan="6" class="empty">尚無紀錄</td></tr>
        {/if}
      </tbody>
    </table>
  </section>
</div>

{#if creatingNew || editing}
  <div class="modal-backdrop" on:click|self={() => { creatingNew = false; editing = null; }}>
    <div class="modal" data-testid="rule-modal">
      <h3>{editing ? '編輯規則' : '新規則'}</h3>
      <RuleForm
        initial={editing}
        on:submit={(e) => onRuleSubmit(e.detail)}
        on:cancel={() => { creatingNew = false; editing = null; }}
      />
    </div>
  </div>
{/if}

{#if preview.open}
  <div class="modal-backdrop" on:click|self={() => (preview = { ...preview, open: false })}>
    <div class="modal preview-modal" data-testid="preview-modal">
      <h3>{preview.title}</h3>
      <iframe srcdoc={preview.html} title="digest preview" data-testid="preview-iframe"></iframe>
      <div class="actions">
        <button on:click={() => (preview = { ...preview, open: false })}>關閉</button>
      </div>
    </div>
  </div>
{/if}

{#if toast}
  <div class="toast" class:ok={toast.kind === 'ok'} class:err={toast.kind === 'err'} data-testid="toast">
    {toast.text}
  </div>
{/if}

<style>
  .page { display: flex; flex-direction: column; gap: 24px; }
  h2 { margin: 0; }
  h3 { margin: 0 0 8px; color: #e5e7eb; }
  section { background: #161616; border: 1px solid #2a2a2a; border-radius: 8px; padding: 16px; }
  .section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .channel-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
  .channel-card { background: #111; border: 1px solid #333; border-radius: 6px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
  .channel-card .head { display: flex; align-items: center; gap: 8px; }
  .channel-card .meta { font-size: 12px; color: #9ca3af; }
  .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; background: #555; }
  .dot.ok { background: #4ade80; }
  .dot.warn { background: #facc15; }
  .dot.off { background: #555; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 8px; border-bottom: 1px solid #2a2a2a; font-size: 13px; }
  th { color: #9ca3af; font-weight: 500; }
  td.empty, p.empty { color: #6b7280; font-size: 13px; padding: 16px; }
  button { background: #1f2937; color: #e5e7eb; border: 1px solid #333; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 4px; }
  button.primary { background: #4ade80; color: #052e16; border: none; }
  button.danger { background: #7f1d1d; }
  .filters { display: flex; gap: 8px; }
  select { background: #111; color: #e5e7eb; border: 1px solid #333; padding: 4px 8px; border-radius: 4px; }
  .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 50; }
  .modal { background: #111; border: 1px solid #333; border-radius: 8px; padding: 20px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto; }
  .preview-modal iframe { width: 100%; height: 400px; background: #fff; border: none; border-radius: 4px; }
  .actions { display: flex; justify-content: flex-end; margin-top: 12px; }
  .toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 16px; border-radius: 6px; z-index: 100; }
  .toast.ok { background: #064e3b; color: #d1fae5; border: 1px solid #4ade80; }
  .toast.err { background: #7f1d1d; color: #fee2e2; border: 1px solid #ef4444; }
  .error { background: #7f1d1d; color: #fee2e2; padding: 8px 12px; border-radius: 4px; }
</style>
