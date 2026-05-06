<script lang="ts">
  import { onMount } from 'svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

  const API = '/api/v1';

  interface OverviewRow {
    code: string;
    name: string;
    price_age_days: number | null;
    margin_age_days: number | null;
    flow_age_days: number | null;
    fundamental_age_days: number | null;
  }

  let rows: OverviewRow[] = [];
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      const res = await fetch(`${API}/data/overview`);
      if (!res.ok) throw new Error(res.statusText);
      rows = await res.json();
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  });

  function ageCellClass(days: number | null): string {
    if (days === null) return 'text-gray-400';
    if (days > 30) return 'bg-red-100 text-red-700 font-semibold';
    if (days > 7) return 'bg-yellow-100 text-yellow-700';
    return 'text-green-700';
  }

  function ageLabel(days: number | null): string {
    if (days === null) return '—';
    return `${days}d`;
  }
</script>

<div class="p-6 max-w-5xl mx-auto">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold">資料管理</h1>
    <div class="flex gap-3">
      <a href="/data/ingest" class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">批量抓取</a>
      <a href="/data/upload" class="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700">上傳資料</a>
    </div>
  </div>

  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <div class="p-3 bg-red-50 text-red-700 rounded border border-red-200">{error}</div>
  {:else}
    <div class="mb-4 flex gap-4 text-sm">
      <span class="flex items-center gap-1"><span class="w-3 h-3 bg-green-200 rounded-sm inline-block"></span> 最新（≤7日）</span>
      <span class="flex items-center gap-1"><span class="w-3 h-3 bg-yellow-200 rounded-sm inline-block"></span> 偏舊（7-30日）</span>
      <span class="flex items-center gap-1"><span class="w-3 h-3 bg-red-200 rounded-sm inline-block"></span> 過舊（>30日）</span>
    </div>

    <div class="bg-white border rounded-xl shadow-sm overflow-auto">
      <table class="w-full text-sm">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-left">代碼</th>
            <th class="px-4 py-3 text-left">名稱</th>
            <th class="px-4 py-3 text-center">股價</th>
            <th class="px-4 py-3 text-center">信用残</th>
            <th class="px-4 py-3 text-center">投資部門別</th>
            <th class="px-4 py-3 text-center">基本面</th>
            <th class="px-4 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row}
            <tr class="border-t hover:bg-gray-50">
              <td class="px-4 py-3 font-mono font-semibold">{row.code}</td>
              <td class="px-4 py-3 text-gray-700">{row.name}</td>
              <td class="px-4 py-3 text-center rounded {ageCellClass(row.price_age_days)}">{ageLabel(row.price_age_days)}</td>
              <td class="px-4 py-3 text-center {ageCellClass(row.margin_age_days)}">{ageLabel(row.margin_age_days)}</td>
              <td class="px-4 py-3 text-center {ageCellClass(row.flow_age_days)}">{ageLabel(row.flow_age_days)}</td>
              <td class="px-4 py-3 text-center {ageCellClass(row.fundamental_age_days)}">{ageLabel(row.fundamental_age_days)}</td>
              <td class="px-4 py-3 text-center">
                <a href="/data/ingest?code={row.code}" class="text-blue-600 hover:underline text-xs mr-2">重抓</a>
                <a href="/data/upload?code={row.code}" class="text-green-600 hover:underline text-xs">上傳</a>
              </td>
            </tr>
          {/each}
          {#if rows.length === 0}
            <tr><td colspan="7" class="px-4 py-8 text-center text-gray-400">追蹤清單為空</td></tr>
          {/if}
        </tbody>
      </table>
    </div>
  {/if}
</div>
