<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$lib/api';

  // hidden = 不顯示；prompt = 詢問是否同步；syncing = 同步中（卡住系統）；
  // done = 同步完成（短暫顯示後 reload）；error = 失敗
  type Phase = 'hidden' | 'prompt' | 'syncing' | 'done' | 'error';

  let phase: Phase = 'hidden';
  let percent = 0;
  let message = '';
  let lastDate: string | null = null;
  let today = '';
  let jobId: string | null = null;
  let errorMsg = '';
  let poll: ReturnType<typeof setInterval> | null = null;

  const SKIP_KEY = 'capystock_sync_skip_date';

  onMount(async () => {
    try {
      const st = await api<any>('/data/cloud-sync/state');
      today = st.today;
      lastDate = st.last_date;
      if (st.synced_today) return; // 今天已同步，不打擾
      if (localStorage.getItem(SKIP_KEY) === today) return; // 今天已選擇跳過
      phase = 'prompt';
    } catch {
      // state 端點失敗就不打擾使用者
    }
  });

  onDestroy(stopPoll);

  function stopPoll() {
    if (poll) {
      clearInterval(poll);
      poll = null;
    }
  }

  async function startSync() {
    phase = 'syncing';
    percent = 0;
    message = '開始同步…';
    errorMsg = '';
    try {
      const res = await api<any>('/data/cloud-sync/start', {
        method: 'POST',
        body: JSON.stringify({ pull: true, rescan_after_sync: true }),
      });
      jobId = res.job_id;
      poll = setInterval(pollJob, 800);
    } catch (e) {
      phase = 'error';
      errorMsg = e instanceof Error ? e.message : '無法啟動同步';
    }
  }

  async function pollJob() {
    if (!jobId) return;
    try {
      const job = await api<any>(`/data/cloud-sync/jobs/${jobId}`);
      percent = job.percent ?? percent;
      message = job.message ?? message;
      if (job.status === 'completed') {
        stopPoll();
        percent = 100;
        phase = 'done';
        // 同步完成 → 整頁 reload，確保各頁都吃到最新資料
        setTimeout(() => location.reload(), 1200);
      } else if (job.status === 'error') {
        stopPoll();
        phase = 'error';
        errorMsg = job.error ?? '同步失敗';
      }
    } catch {
      // 暫時讀不到狀態就等下一次輪詢
    }
  }

  function retry() {
    startSync();
  }

  function skipToday() {
    if (today) localStorage.setItem(SKIP_KEY, today);
    phase = 'hidden';
  }

  function cancel() {
    phase = 'hidden';
  }
</script>

{#if phase !== 'hidden'}
  <!-- 全螢幕遮罩：同步中不提供關閉途徑，把系統卡住直到完成 -->
  <div class="sync-overlay">
    <div class="sync-modal">
      {#if phase === 'prompt'}
        <div class="sync-title">📡 同步今日行情</div>
        <p class="sync-text">
          今天（{today}）尚未同步最新行情。
          {#if lastDate}<br /><span class="sync-sub">上次同步：{lastDate}</span>{/if}
        </p>
        <p class="sync-text">是否現在從雲端同步、重算全市場訊號並把模擬交易推進到最新收盤？</p>
        <div class="sync-actions">
          <button class="btn btn-primary" on:click={startSync}>開始同步</button>
          <button class="btn" on:click={skipToday}>今天跳過</button>
          <button class="btn btn-ghost" on:click={cancel}>取消</button>
        </div>
      {:else if phase === 'syncing'}
        <div class="sync-title">⬇ 同步中…</div>
        <p class="sync-text sync-warn">同步完成前請勿操作，全部完成後畫面會自動重新整理。</p>
        <div class="progress-bar">
          <div class="progress-fill" style="width: {percent}%"></div>
        </div>
        <div class="progress-meta">
          <span>{percent}%</span>
          <span class="sync-sub">{message}</span>
        </div>
      {:else if phase === 'done'}
        <div class="sync-title done">✓ 同步完成</div>
        <p class="sync-text">正在重新整理畫面…</p>
        <div class="progress-bar">
          <div class="progress-fill" style="width: 100%"></div>
        </div>
      {:else if phase === 'error'}
        <div class="sync-title error">⚠ 同步失敗</div>
        <p class="sync-text sync-sub">{errorMsg}</p>
        <div class="sync-actions">
          <button class="btn btn-primary" on:click={retry}>重試</button>
          <button class="btn btn-ghost" on:click={cancel}>關閉</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .sync-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.72);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
  }

  .sync-modal {
    width: 440px;
    max-width: calc(100vw - 40px);
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 10px;
    padding: 24px;
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6);
  }

  .sync-title {
    font-size: 18px;
    font-weight: bold;
    color: #4ade80;
    margin-bottom: 12px;
  }

  .sync-title.error {
    color: #f87171;
  }

  .sync-title.done {
    color: #4ade80;
  }

  .sync-text {
    color: #e5e7eb;
    margin: 8px 0;
    line-height: 1.6;
  }

  .sync-warn {
    color: #fbbf24;
  }

  .sync-sub {
    color: #9ca3af;
    font-size: 13px;
  }

  .sync-actions {
    display: flex;
    gap: 10px;
    margin-top: 20px;
  }

  .btn {
    flex: 1;
    padding: 10px 14px;
    border-radius: 6px;
    border: 1px solid #444;
    background: #2a2a2a;
    color: #e5e7eb;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s ease;
  }

  .btn:hover {
    background: #333;
  }

  .btn-primary {
    background: #16a34a;
    border-color: #16a34a;
    color: #fff;
    font-weight: bold;
  }

  .btn-primary:hover {
    background: #15803d;
  }

  .btn-ghost {
    background: transparent;
  }

  .progress-bar {
    width: 100%;
    height: 12px;
    background: #2a2a2a;
    border-radius: 6px;
    overflow: hidden;
    margin-top: 16px;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #16a34a, #4ade80);
    transition: width 0.4s ease;
  }

  .progress-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    font-size: 13px;
    color: #e5e7eb;
  }
</style>
