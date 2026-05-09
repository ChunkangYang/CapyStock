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

  const FLOW_KEYWORDS = ['foreign_net', 'institution_net', 'individual_net', '外資', '外国人', '機関', '個人', 'Foreign', 'Institution', 'Individual'];
  const MARGIN_KEYWORDS = ['margin_long', 'margin_short', 'ratio', '買残', '売残', '融資', '融券', '信用倍率', '倍率'];

  function detectKind(headers: string[]): 'margin' | 'flow' | null {
    const joined = headers.join(',');
    const flowScore = FLOW_KEYWORDS.filter(k => joined.includes(k)).length;
    const marginScore = MARGIN_KEYWORDS.filter(k => joined.includes(k)).length;
    if (flowScore > marginScore) return 'flow';
    if (marginScore > flowScore) return 'margin';
    return null;
  }

  function loadFile(f: File) {
    file = f;
    result = null;
    error = '';
    const m = f.name.match(/^(\d{4,6})/);
    if (m && !code) code = m[1];

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

      // 自動偵測種類
      const detected = detectKind(previewHeaders);
      if (detected) kind = detected;
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

<div class="page">
  <div class="page-header">
    <a href="/data" class="back-link">← 資料管理</a>
    <h1>上傳資料</h1>
  </div>

  <!-- 拖拉上傳區 -->
  <div
    class="drop-zone"
    class:drag-over={dragOver}
    on:dragover|preventDefault={() => (dragOver = true)}
    on:dragleave={() => (dragOver = false)}
    on:drop={handleDrop}
    role="region"
    aria-label="拖拉上傳"
  >
    <p class="drop-hint">拖拉 CSV / XLSX 到此，或</p>
    <label class="file-btn">
      選擇檔案
      <input type="file" accept=".csv,.xlsx,.xls" class="hidden-input" on:change={handleFileChange} />
    </label>
    {#if file}
      <p class="file-name">✓ {file.name}</p>
    {/if}
  </div>

  <div class="card">
    <div class="form-row">
      <div class="field">
        <label>股票代碼</label>
        <input class="inp" bind:value={code} placeholder="7203" />
      </div>
      <div class="field">
        <label>資料種類</label>
        <select class="sel" bind:value={kind}>
          <option value="margin">信用残 (margin)</option>
          <option value="flow">投資部門別 (flow)</option>
        </select>
      </div>
    </div>

    {#if previewRows.length > 0}
      <div class="preview-block">
        <p class="preview-title">前 {previewRows.length} 列預覽</p>
        <div class="preview-wrap">
          <table class="preview-table">
            <thead>
              <tr>
                {#each previewHeaders as h}
                  <th>{h}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each previewRows as row}
                <tr>
                  {#each previewHeaders as h}
                    <td>{row[h]}</td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <button class="btn-primary" on:click={doUpload} disabled={uploading || !file}>
      {uploading ? '上傳中…' : '確認上傳'}
    </button>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if result}
    <div class="success-banner">
      <p class="success-title">✓ 上傳成功</p>
      <p>來源：{result.source}，寫入 {result.rows_fetched} 筆</p>
      {#if result.written_path}
        <p class="success-path">{result.written_path}</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .page { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }

  .page-header { display: flex; align-items: baseline; gap: 16px; }

  .back-link { color: #4ade80; text-decoration: none; font-size: 13px; }
  .back-link:hover { text-decoration: underline; }

  h1 { color: #4ade80; font-size: 28px; margin: 0; }

  .drop-zone {
    border: 2px dashed #333;
    border-radius: 8px;
    padding: 32px;
    text-align: center;
    transition: border-color 0.2s, background 0.2s;
  }
  .drop-zone.drag-over {
    border-color: #4ade80;
    background: #0a2a1a;
  }

  .drop-hint { color: #6b7280; font-size: 14px; margin: 0 0 12px 0; }

  .file-btn {
    display: inline-block;
    background: #2a2a2a;
    color: #e5e7eb;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 13px;
    cursor: pointer;
  }
  .file-btn:hover { background: #333; border-color: #4a4a4a; }

  .hidden-input { display: none; }

  .file-name { color: #4ade80; font-size: 13px; margin: 10px 0 0 0; }

  .card {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

  .field { display: flex; flex-direction: column; gap: 6px; }

  label { color: #a1a1a1; font-size: 13px; }

  .inp, .sel {
    background: #0f0f0f;
    border: 1px solid #333;
    border-radius: 4px;
    color: #e5e7eb;
    padding: 8px 12px;
    font-size: 14px;
    width: 100%;
  }
  .inp:focus, .sel:focus { outline: none; border-color: #4ade80; }

  .preview-block { display: flex; flex-direction: column; gap: 8px; }
  .preview-title { color: #a1a1a1; font-size: 13px; margin: 0; }
  .preview-wrap { overflow: auto; border: 1px solid #333; border-radius: 4px; }

  .preview-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .preview-table th {
    padding: 6px 10px;
    background: #111;
    color: #6b7280;
    border-bottom: 1px solid #333;
    text-align: left;
    white-space: nowrap;
  }
  .preview-table td {
    padding: 6px 10px;
    border-bottom: 1px solid #222;
    color: #e5e7eb;
  }
  .preview-table tr:last-child td { border-bottom: none; }

  .btn-primary {
    background: #4ade80;
    color: #0f0f0f;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    align-self: flex-start;
  }
  .btn-primary:hover { background: #22c55e; }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

  .error-banner {
    background: #7f1d1d;
    border: 1px solid #ef4444;
    color: #fca5a5;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 13px;
  }

  .success-banner {
    background: #064e3b;
    border: 1px solid #4ade80;
    color: #d1fae5;
    border-radius: 6px;
    padding: 14px 16px;
    font-size: 13px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .success-title { font-weight: 600; font-size: 14px; margin: 0; }
  .success-path { color: #6ee7b7; font-size: 12px; margin: 0; }
</style>
