<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';

  const API = '/api/v1';

  let selectedCodes = '';
  let selectedKinds: string[] = ['margin'];
  let running = false;
  let jobId = '';
  let progress = 0;
  let total = 0;
  let status = '';
  let results: any[] = [];
  let error = '';

  const kindOptions = [
    { value: 'margin', label: '信用残' },
    { value: 'flow', label: '投資部門別' },
  ];

  onMount(() => {
    const code = $page.url.searchParams.get('code');
    if (code) selectedCodes = code;
  });

  function toggleKind(kind: string) {
    if (selectedKinds.includes(kind)) {
      selectedKinds = selectedKinds.filter(k => k !== kind);
    } else {
      selectedKinds = [...selectedKinds, kind];
    }
  }

  async function startIngest() {
    error = '';
    results = [];
    const codes = selectedCodes.split(/[\s,]+/).filter(Boolean);
    if (!codes.length || !selectedKinds.length) {
      error = '請選擇代碼和資料種類';
      return;
    }

    running = true;
    progress = 0;

    const res = await fetch(`${API}/data/batch-ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codes, kinds: selectedKinds }),
    });

    if (!res.ok) {
      error = (await res.json()).detail || res.statusText;
      running = false;
      return;
    }

    const info = await res.json();
    jobId = info.job_id;
    total = info.total;

    // SSE 進度
    const evtSource = new EventSource(`${API}/data/batch-ingest/${jobId}/stream`);
    evtSource.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      progress = data.done;
      total = data.total;
      status = data.status;
      if (data.status === 'completed') {
        evtSource.close();
        fetchResults();
        running = false;
      }
    };
    evtSource.onerror = () => {
      evtSource.close();
      running = false;
      fetchResults();
    };
  }

  async function fetchResults() {
    if (!jobId) return;
    const res = await fetch(`${API}/data/batch-ingest/${jobId}`);
    if (res.ok) {
      const job = await res.json();
      results = job.results || [];
    }
  }
</script>

<div class="p-6 max-w-3xl mx-auto">
  <div class="flex items-center gap-3 mb-6">
    <a href="/data" class="text-blue-600 hover:underline text-sm">← 資料管理</a>
    <h1 class="text-xl font-bold">批量抓取</h1>
  </div>

  <div class="bg-white border rounded-xl p-5 shadow-sm mb-6">
    <div class="mb-4">
      <label class="block text-sm font-medium text-gray-700 mb-1">股票代碼（逗號或空白分隔）</label>
      <input
        bind:value={selectedCodes}
        class="w-full border rounded px-3 py-2 text-sm"
        placeholder="7203, 9984, 6758"
      />
    </div>

    <div class="mb-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">資料種類</label>
      <div class="flex gap-3">
        {#each kindOptions as opt}
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={selectedKinds.includes(opt.value)}
              on:change={() => toggleKind(opt.value)}
              class="rounded"
            />
            <span class="text-sm">{opt.label}</span>
          </label>
        {/each}
      </div>
    </div>

    <button
      on:click={startIngest}
      disabled={running}
      class="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold disabled:opacity-50 hover:bg-blue-700"
    >
      {running ? '抓取中...' : '執行'}
    </button>
  </div>

  {#if error}
    <div class="mb-4 p-3 bg-red-50 text-red-700 rounded border border-red-200 text-sm">{error}</div>
  {/if}

  {#if running || total > 0}
    <div class="mb-6">
      <div class="flex justify-between text-sm text-gray-600 mb-1">
        <span>進度</span>
        <span>{progress} / {total}</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-2">
        <div
          class="bg-blue-600 h-2 rounded-full transition-all"
          style="width: {total > 0 ? (progress / total * 100) : 0}%"
        ></div>
      </div>
    </div>
  {/if}

  {#if results.length > 0}
    <div class="bg-white border rounded-xl shadow-sm overflow-auto">
      <table class="w-full text-sm">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-2 text-left">代碼</th>
            <th class="px-4 py-2 text-left">種類</th>
            <th class="px-4 py-2 text-left">來源</th>
            <th class="px-4 py-2 text-right">筆數</th>
            <th class="px-4 py-2 text-center">狀態</th>
            <th class="px-4 py-2 text-left">錯誤</th>
          </tr>
        </thead>
        <tbody>
          {#each results as r}
            <tr class="border-t">
              <td class="px-4 py-2 font-mono">{r.code}</td>
              <td class="px-4 py-2">{r.kind}</td>
              <td class="px-4 py-2 text-gray-500 text-xs">{r.source}</td>
              <td class="px-4 py-2 text-right">{r.rows}</td>
              <td class="px-4 py-2 text-center">
                {#if r.ok}
                  <span class="text-green-600 font-semibold">✓</span>
                {:else}
                  <span class="text-red-500 font-semibold">✗</span>
                {/if}
              </td>
              <td class="px-4 py-2 text-xs text-red-500">{r.error || ''}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
