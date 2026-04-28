<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';

  const API = '/api/v1';

  let code = '';
  let kind = 'margin';
  let file: File | null = null;
  let previewRows: any[] = [];
  let previewHeaders: string[] = [];
  let dragOver = false;
  let uploading = false;
  let result: any = null;
  let error = '';

  onMount(() => {
    const c = $page.url.searchParams.get('code');
    if (c) code = c;
  });

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    const f = e.dataTransfer?.files[0];
    if (f) loadFile(f);
  }

  function handleFileChange(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (f) loadFile(f);
  }

  function loadFile(f: File) {
    file = f;
    // 從檔名自動猜測 code
    const m = f.name.match(/^(\d{4,6})/);
    if (m && !code) code = m[1];

    // 讀取前 10 行預覽
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      const lines = text.split('\n').filter(Boolean).slice(0, 11);
      if (!lines.length) return;
      previewHeaders = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
      previewRows = lines.slice(1).map(l => {
        const vals = l.split(',').map(v => v.trim().replace(/"/g, ''));
        const row: any = {};
        previewHeaders.forEach((h, i) => row[h] = vals[i] || '');
        return row;
      });
    };
    reader.readAsText(f);
  }

  async function doUpload() {
    if (!file || !code || !kind) {
      error = '請選擇檔案、填入代碼與種類';
      return;
    }
    uploading = true;
    error = '';
    result = null;
    const form = new FormData();
    form.append('file', file);
    form.append('code', code);
    form.append('kind', kind);

    try {
      const res = await fetch(`${API}/ingest/upload`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || res.statusText);
      }
      result = await res.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      uploading = false;
    }
  }
</script>

<div class="p-6 max-w-3xl mx-auto">
  <div class="flex items-center gap-3 mb-6">
    <a href="/data" class="text-blue-600 hover:underline text-sm">← 資料管理</a>
    <h1 class="text-xl font-bold">上傳資料</h1>
  </div>

  <!-- 拖拉上傳區 -->
  <div
    class="border-2 border-dashed rounded-xl p-8 text-center mb-6 transition-colors {dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}"
    on:dragover|preventDefault={() => (dragOver = true)}
    on:dragleave={() => (dragOver = false)}
    on:drop={handleDrop}
    role="region"
    aria-label="拖拉上傳"
  >
    <p class="text-gray-500 mb-3">拖拉 CSV / XLSX 到此，或</p>
    <label class="cursor-pointer px-4 py-2 bg-white border rounded-lg text-sm hover:bg-gray-50">
      選擇檔案
      <input type="file" accept=".csv,.xlsx,.xls" class="hidden" on:change={handleFileChange} />
    </label>
    {#if file}
      <p class="mt-3 text-green-700 font-medium text-sm">{file.name}</p>
    {/if}
  </div>

  <div class="bg-white border rounded-xl p-5 shadow-sm mb-6">
    <div class="grid grid-cols-2 gap-4 mb-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">股票代碼</label>
        <input bind:value={code} class="w-full border rounded px-3 py-2 text-sm" placeholder="7203" />
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">資料種類</label>
        <select bind:value={kind} class="w-full border rounded px-3 py-2 text-sm">
          <option value="margin">信用残 (margin)</option>
          <option value="flow">投資部門別 (flow)</option>
        </select>
      </div>
    </div>

    {#if previewRows.length > 0}
      <div class="mb-4">
        <h3 class="text-sm font-semibold text-gray-600 mb-2">前 {previewRows.length} 列預覽</h3>
        <div class="overflow-auto border rounded">
          <table class="w-full text-xs">
            <thead class="bg-gray-50">
              <tr>
                {#each previewHeaders as h}
                  <th class="px-2 py-1 text-left">{h}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each previewRows as row}
                <tr class="border-t">
                  {#each previewHeaders as h}
                    <td class="px-2 py-1">{row[h]}</td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <button
      on:click={doUpload}
      disabled={uploading || !file}
      class="px-5 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold disabled:opacity-50 hover:bg-green-700"
    >
      {uploading ? '上傳中...' : '確認上傳'}
    </button>
  </div>

  {#if error}
    <div class="p-3 bg-red-50 text-red-700 rounded border border-red-200 text-sm">{error}</div>
  {/if}

  {#if result}
    <div class="p-4 bg-green-50 border border-green-200 rounded-xl">
      <p class="font-semibold text-green-700 mb-1">✓ 上傳成功</p>
      <p class="text-sm text-green-600">來源：{result.source}，寫入 {result.rows_fetched} 筆</p>
      {#if result.written_path}
        <p class="text-xs text-gray-500 mt-1">{result.written_path}</p>
      {/if}
    </div>
  {/if}
</div>
