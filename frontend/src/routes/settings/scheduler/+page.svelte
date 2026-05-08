<script lang="ts">
  import { onMount } from 'svelte';
  import { api, ApiError } from '$lib/api';
  import CronEditor from '$lib/components/CronEditor.svelte';

  type Job = {
    id: string;
    name: string;
    cron: string;
    handler: string;
    enabled: boolean;
    timeout_seconds: number;
    max_instances: number;
    next_run_time: string | null;
  };
  type Run = {
    run_id: string;
    job_id: string;
    started_at: string;
    finished_at: string | null;
    status: 'running' | 'success' | 'failed' | 'timeout' | 'skipped';
    duration_seconds: number | null;
    error: string | null;
    output_summary: string | null;
  };

  let jobs: Job[] = [];
  let runsByJob: Record<string, Run[]> = {};
  let expanded: Record<string, boolean> = {};
  let detailRun: Run | null = null;
  let toast: { kind: 'ok' | 'err'; text: string } | null = null;
  let loading = true;
  let errorMsg = '';

  let cronEdits: Record<string, string> = {};

  async function loadJobs() {
    loading = true;
    errorMsg = '';
    try {
      const res = await api<{ jobs: Job[] }>('/scheduler/jobs');
      jobs = res.jobs;
      cronEdits = Object.fromEntries(jobs.map((j) => [j.id, j.cron]));
    } catch (e) {
      errorMsg = e instanceof ApiError ? e.detail : String(e);
    } finally {
      loading = false;
    }
  }

  async function loadRunsFor(jobId: string) {
    try {
      const res = await api<{ runs: Run[] }>(`/scheduler/runs?job_id=${jobId}&days=7`);
      runsByJob = { ...runsByJob, [jobId]: res.runs.slice(0, 10) };
    } catch (e) {
      showToast('err', `讀取 runs 失敗：${e}`);
    }
  }

  function showToast(kind: 'ok' | 'err', text: string) {
    toast = { kind, text };
    setTimeout(() => (toast = null), 3000);
  }

  async function patchJob(job: Job, fields: Partial<Job>) {
    try {
      const updated = await api<Job>(`/scheduler/jobs/${job.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fields),
      });
      jobs = jobs.map((j) => (j.id === job.id ? updated : j));
      cronEdits[job.id] = updated.cron;
      showToast('ok', `${job.name} 已更新`);
    } catch (e) {
      showToast('err', `更新失敗：${e}`);
    }
  }

  function applyCron(job: Job) {
    const next = (cronEdits[job.id] ?? '').trim();
    if (!next || next === job.cron) return;
    patchJob(job, { cron: next });
  }

  async function runNow(job: Job) {
    try {
      const res = await api<{ run_id: string; status: string }>(
        `/scheduler/jobs/${job.id}/run`,
        { method: 'POST' },
      );
      showToast('ok', `${job.name} 已觸發 (${res.status})`);
      setTimeout(() => loadRunsFor(job.id), 1500);
    } catch (e) {
      showToast('err', `觸發失敗：${e}`);
    }
  }

  function toggleExpanded(jobId: string) {
    expanded[jobId] = !expanded[jobId];
    expanded = { ...expanded };
    if (expanded[jobId] && !runsByJob[jobId]) loadRunsFor(jobId);
  }

  const STATUS_LABELS: Record<string, string> = {
    success: '成功',
    running: '執行中',
    failed: '失敗',
    timeout: '逾時',
    skipped: '略過',
  };

  function statusColor(s: Run['status']) {
    switch (s) {
      case 'success': return '#4ade80';
      case 'running': return '#60a5fa';
      case 'failed': return '#ef4444';
      case 'timeout': return '#f97316';
      case 'skipped': return '#9ca3af';
      default: return '#555';
    }
  }

  function fmtTime(iso: string | null) {
    if (!iso) return '–';
    return new Date(iso).toLocaleString();
  }

  function lastRunSummary(jobId: string): { ts: string; status: string } | null {
    const list = runsByJob[jobId] ?? [];
    return list[0] ? { ts: list[0].started_at, status: list[0].status } : null;
  }

  onMount(async () => {
    await loadJobs();
    await Promise.all(jobs.map((j) => loadRunsFor(j.id)));
  });
</script>

<div class="page" data-testid="scheduler-page">
  <h2>排程器</h2>
  {#if errorMsg}<div class="error">{errorMsg}</div>{/if}

  <table class="jobs-table" data-testid="jobs-table">
    <thead>
      <tr>
        <th></th>
        <th>名稱</th>
        <th>排程</th>
        <th>啟用</th>
        <th>上次執行</th>
        <th>下次執行</th>
        <th>狀態</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>
      {#each jobs as job (job.id)}
        {@const last = lastRunSummary(job.id)}
        <tr data-testid={`job-row-${job.id}`}>
          <td>
            <button class="expand" on:click={() => toggleExpanded(job.id)}>
              {expanded[job.id] ? '▾' : '▸'}
            </button>
          </td>
          <td>
            <div>{job.name}</div>
            <div class="job-id">{job.id}</div>
          </td>
          <td>
            <CronEditor bind:value={cronEdits[job.id]} inline />
            {#if cronEdits[job.id] !== job.cron}
              <button on:click={() => applyCron(job)} data-testid={`apply-cron-${job.id}`}>套用</button>
            {/if}
          </td>
          <td>
            <input
              type="checkbox"
              checked={job.enabled}
              on:change={() => patchJob(job, { enabled: !job.enabled })}
            />
          </td>
          <td>{last ? fmtTime(last.ts) : '–'}</td>
          <td>{fmtTime(job.next_run_time)}</td>
          <td>
            {#if last}
              <span class="badge" style="background: {statusColor(last.status)};">{STATUS_LABELS[last.status] ?? last.status}</span>
            {:else}
              <span class="badge" style="background: #555;">–</span>
            {/if}
          </td>
          <td>
            <button on:click={() => runNow(job)} data-testid={`run-now-${job.id}`}>立即執行</button>
            <button on:click={() => toggleExpanded(job.id)}>執行紀錄</button>
          </td>
        </tr>
        {#if expanded[job.id]}
          <tr class="runs-row">
            <td colspan="8">
              <div class="runs-detail">
                <div class="timeline" data-testid={`timeline-${job.id}`}>
                  {#each (runsByJob[job.id] ?? []) as r}
                    <button
                      class="block"
                      title={`${r.status} · ${fmtTime(r.started_at)}`}
                      style="background: {statusColor(r.status)};"
                      on:click={() => (detailRun = r)}
                      data-testid={`run-block-${r.run_id}`}
                    ></button>
                  {/each}
                  {#if (runsByJob[job.id] ?? []).length === 0}
                    <span class="muted">無紀錄</span>
                  {/if}
                </div>
              </div>
            </td>
          </tr>
        {/if}
      {/each}
      {#if !loading && jobs.length === 0}
        <tr><td colspan="8" class="muted">尚無排程</td></tr>
      {/if}
    </tbody>
  </table>
</div>

{#if detailRun}
  <div class="modal-backdrop" on:click|self={() => (detailRun = null)}>
    <div class="modal" data-testid="run-detail-modal">
      <h3>Run {detailRun.run_id.slice(0, 8)}</h3>
      <dl>
        <dt>排程</dt><dd>{detailRun.job_id}</dd>
        <dt>狀態</dt><dd>{STATUS_LABELS[detailRun.status] ?? detailRun.status}</dd>
        <dt>開始</dt><dd>{fmtTime(detailRun.started_at)}</dd>
        <dt>結束</dt><dd>{fmtTime(detailRun.finished_at)}</dd>
        <dt>耗時</dt><dd>{detailRun.duration_seconds?.toFixed(2) ?? '–'} 秒</dd>
        <dt>輸出</dt>
        <dd><pre>{detailRun.output_summary ?? '–'}</pre></dd>
        <dt>錯誤</dt>
        <dd><pre class="err">{detailRun.error ?? '–'}</pre></dd>
      </dl>
      <div class="actions"><button on:click={() => (detailRun = null)}>關閉</button></div>
    </div>
  </div>
{/if}

{#if toast}
  <div class="toast" class:ok={toast.kind === 'ok'} class:err={toast.kind === 'err'}>{toast.text}</div>
{/if}

<style>
  .page { display: flex; flex-direction: column; gap: 16px; }
  h2 { margin: 0; }
  table { width: 100%; border-collapse: collapse; background: #161616; border: 1px solid #2a2a2a; border-radius: 8px; overflow: hidden; }
  th, td { text-align: left; padding: 10px; border-bottom: 1px solid #2a2a2a; font-size: 13px; vertical-align: top; }
  th { color: #9ca3af; font-weight: 500; }
  .job-id { font-size: 11px; color: #6b7280; font-family: monospace; }
  .badge { padding: 2px 8px; border-radius: 4px; color: #052e16; font-size: 11px; font-weight: 600; }
  button { background: #1f2937; color: #e5e7eb; border: 1px solid #333; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
  button.expand { background: transparent; border: none; color: #e5e7eb; padding: 0 6px; font-size: 18px; line-height: 1; }
  .runs-row td { background: #0d0d0d; }
  .runs-detail { padding: 8px; }
  .timeline { display: flex; gap: 4px; align-items: center; }
  .block { width: 18px; height: 18px; border-radius: 3px; border: none; padding: 0; cursor: pointer; }
  .muted { color: #6b7280; font-size: 12px; }
  .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 50; }
  .modal { background: #111; border: 1px solid #333; border-radius: 8px; padding: 20px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; }
  dl { display: grid; grid-template-columns: 80px 1fr; gap: 6px 16px; font-size: 13px; }
  dt { color: #9ca3af; }
  dd { margin: 0; }
  pre { white-space: pre-wrap; word-break: break-word; background: #0a0a0a; padding: 6px; border-radius: 4px; font-size: 12px; max-height: 200px; overflow: auto; }
  pre.err { color: #fca5a5; }
  .actions { display: flex; justify-content: flex-end; margin-top: 12px; }
  .toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 16px; border-radius: 6px; z-index: 100; }
  .toast.ok { background: #064e3b; color: #d1fae5; border: 1px solid #4ade80; }
  .toast.err { background: #7f1d1d; color: #fee2e2; border: 1px solid #ef4444; }
  .error { background: #7f1d1d; color: #fee2e2; padding: 8px 12px; border-radius: 4px; }
</style>
