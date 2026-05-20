<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, ApiError } from '$lib/api';
  import DataTable from '$lib/components/DataTable.svelte';
  import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
  import { cacheGet, cacheSet, cacheClear, cacheTimestamp, formatCacheAge, clearAllSignalsCache } from '$lib/utils/signalsCache';
  import { favorites, loadFavorites } from '$lib/stores/favorites';
  import { get } from 'svelte/store';
  import type { SignalScanRow, SignalResult } from '$lib/types';

  const TABS = ['market', 'favorites', 'portfolio', 'watchlist'] as const;
  type Tab = (typeof TABS)[number];

  let activeTab: Tab = 'market';
  let data: SignalScanRow[] = [];
  let loading = true;
  let refreshingAll = false;
  let refreshingCodes = new Set<string>();
  let error = '';
  let noSnapshot = false;
  let cacheTs: number | null = null;
  let autoReloadInterval: number | null = null;
  let scanInProgress = false;

  // 分頁參數（client-side：market tab 一次抓全部，過濾/排序/分頁都在前端）
  const LIMIT = 50;
  let currentPage = 1;
  let totalCount = 0;          // 全部抓回來的筆數
  let filteredTotal = 0;       // 經過過濾後的筆數（由 DataTable 回報）

  let _loadSeq = 0;
  let favoriteSignals: SignalScanRow[] = [];

  // market tab 用：$favorites が変わったら現在値を引数で渡して signal を fetch
  $: fetchFavoriteSignals($favorites);

  async function fetchFavoriteSignals(favMap: Record<string, unknown>) {
    const codes = Object.keys(favMap);
    if (codes.length === 0) { favoriteSignals = []; return; }
    try {
      const results: SignalResult[] = await Promise.all(
        codes.map(code => api<SignalResult>(`/signals/${code}`))
      );
      favoriteSignals = results.map(toScanRow);
    } catch {}
  }

  function listCacheKey(tab: Tab) {
    return `signals_list:${tab}`;
  }

  function checkScanStatus() {
    try {
      const savedScanState = localStorage.getItem('scan_state');
      if (savedScanState) {
        const state = JSON.parse(savedScanState);
        scanInProgress = state.isRunning === true;
        return scanInProgress;
      }
    } catch {}
    scanInProgress = false;
    return false;
  }

  function startAutoReload() {
    if (autoReloadInterval !== null) return;

    autoReloadInterval = window.setInterval(async () => {
      // 檢查掃描是否仍在進行
      if (!checkScanStatus()) {
        if (autoReloadInterval !== null) {
          clearInterval(autoReloadInterval);
          autoReloadInterval = null;
        }
        return;
      }

      // 只在 market tab 自動重新整理
      if (activeTab === 'market') {
        const key = listCacheKey('market');
        cacheClear(key);
        try {
          const resp = await api(`/scan/signals?limit=100000&offset=0`);
          if (_loadSeq > 0) {  // 避免第一次載入時覆蓋
            cacheSet(key, { rows: resp.data, total: resp.total });
            data = resp.data;
            totalCount = resp.total;
            cacheTs = cacheTimestamp(key);
          }
        } catch {}
      }
    }, 10000);  // 每 10 秒重新整理一次
  }

  onMount(async () => {
    await loadData();

    // 檢查是否有掃描在進行中
    if (checkScanStatus()) {
      startAutoReload();
    }
  });

  $: if (autoReloadInterval !== null && !scanInProgress) {
    clearInterval(autoReloadInterval);
    autoReloadInterval = null;
  }

  onDestroy(() => {
    if (autoReloadInterval !== null) {
      clearInterval(autoReloadInterval);
    }
  });

  async function loadData(forceRefresh = false) {
    const seq = ++_loadSeq;
    loading = true;
    error = '';
    noSnapshot = false;

    const key = listCacheKey(activeTab);

    if (forceRefresh) {
      // 強制更新：清除所有訊號快取
      clearAllSignalsCache();
    } else if (activeTab === 'market') {
      // Market tab 全量快取（永遠優先用 cache，使用者按「全部更新」才重抓）
      const cachedEntry = cacheGet<{ rows: SignalScanRow[]; total: number }>(key);
      if (cachedEntry && cachedEntry.rows && typeof cachedEntry.total === 'number') {
        if (seq !== _loadSeq) return;
        data = cachedEntry.rows;
        totalCount = cachedEntry.total;
        cacheTs = cacheTimestamp(key);
        loading = false;
        return;
      }
    }

    try {
      let result: SignalScanRow[] = [];

      if (activeTab === 'market') {
        const resp = await api(`/scan/signals?limit=100000&offset=0`);
        result = resp.data;
        totalCount = resp.total;
        cacheSet(key, { rows: result, total: resp.total });
      } else {
        // watchlist / portfolio / favorites：cache 永遠優先，不打 API 比對
        if (!forceRefresh) {
          const cached = cacheGet<SignalScanRow[]>(key);
          if (cached) {
            if (seq !== _loadSeq) return;
            data = cached;
            totalCount = cached.length;
            cacheTs = cacheTimestamp(key);
            loading = false;
            return;
          }
        }

        // cache miss 或 forceRefresh：先抓 list 再逐個 fetch signal
        let listEntries: { code: string }[] = [];
        if (activeTab === 'watchlist') {
          listEntries = await api('/watchlist');
        } else if (activeTab === 'portfolio') {
          listEntries = await api('/portfolio');
        } else if (activeTab === 'favorites') {
          listEntries = await api('/favorites');
        }

        const results: SignalResult[] = await Promise.all(
          listEntries.map(e => api(`/signals/${e.code}`))
        );
        result = results.map(r => toScanRow(r));
        totalCount = result.length;
        cacheSet(key, result);
      }

      if (seq !== _loadSeq) return;
      cacheTs = cacheTimestamp(key);

      // market tab：favorite シグナル取得を await して table 表示前に揃える
      if (activeTab === 'market') {
        if (Object.keys(get(favorites)).length === 0) {
          await loadFavorites();
        }
        await fetchFavoriteSignals(get(favorites));
        if (seq !== _loadSeq) return;
      }

      data = result;
    } catch (e) {
      if (seq !== _loadSeq) return;
      if (e instanceof ApiError && e.status === 404 && activeTab === 'market') {
        noSnapshot = true;
      } else {
        error = e instanceof Error ? e.message : '讀取資料失敗';
      }
    } finally {
      if (seq === _loadSeq) loading = false;
    }
  }

  async function refreshAll() {
    refreshingAll = true;
    clearAllSignalsCache();
    totalCount = 0;
    currentPage = 1;
    await loadData(true);
    refreshingAll = false;
  }

  function goToPage(pageNum: unknown) {
    // 嚴格防護：只接受正整數，攔截 NaN / '...' / 字串 / 浮點數
    if (typeof pageNum !== 'number' || !Number.isInteger(pageNum) || pageNum < 1) return;
    const total = filteredTotal > 0 ? filteredTotal : totalCount;
    if (!Number.isFinite(total) || total <= 0) return;
    const totalPages = Math.ceil(total / LIMIT);
    if (!Number.isFinite(totalPages) || totalPages < 1) return;
    if (pageNum > totalPages) return;
    currentPage = pageNum;
    // 平滑滾回頂端方便看新分頁的列
    if (typeof window !== 'undefined') window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // 過濾條件變動時 filteredTotal 會由 DataTable 推回，若當前頁超出範圍要拉回最後一頁
  $: {
    const total = filteredTotal > 0 ? filteredTotal : totalCount;
    if (total > 0) {
      const totalPages = Math.max(1, Math.ceil(total / LIMIT));
      if (currentPage > totalPages) currentPage = totalPages;
    }
  }

  function getPageNumbers() {
    const total = filteredTotal > 0 ? filteredTotal : totalCount;
    // 防護：total 未就緒時不產出任何頁碼
    if (!Number.isFinite(total) || total <= 0) return [];
    const totalPages = Math.ceil(total / LIMIT);
    if (!Number.isFinite(totalPages) || totalPages < 1) return [];
    if (totalPages === 1) return [1];

    const pages: (number | string)[] = [];

    const range = 2; // 當前頁前後顯示多少頁
    const start = Math.max(1, currentPage - range);
    const end = Math.min(totalPages, currentPage + range);

    if (start > 1) {
      pages.push(1);
      if (start > 2) pages.push('...');
    }

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (end < totalPages) {
      if (end < totalPages - 1) pages.push('...');
      pages.push(totalPages);
    }

    return pages;
  }

  async function refreshRow(code: string) {
    refreshingCodes = new Set([...refreshingCodes, code]);
    // 清除個股快取（detail 頁面會重新抓）
    cacheClear(`signals_detail:${code}`);
    try {
      const result: SignalResult = await api(`/signals/${code}`);
      const updated = toScanRow(result);
      data = data.map(row => row.code === code ? updated : row);
      // 更新 list 快取
      const cacheKey = listCacheKey(activeTab);
      if (activeTab === 'market') {
        cacheSet(cacheKey, { rows: data, total: totalCount });
      } else {
        cacheSet(cacheKey, data);
      }
      cacheTs = cacheTimestamp(cacheKey);
    } catch {}
    refreshingCodes = new Set([...refreshingCodes].filter(c => c !== code));
  }

  function toScanRow(r: SignalResult): SignalScanRow {
    return {
      code: r.code,
      name: r.name,
      latest_price: r.latest_price ?? 0,
      has_accumulation: r.accumulation_signal,
      has_exit: (r.alerts ?? []).some(a => a.alert_type === 'exit'),
      has_stop_loss: r.stop_loss_triggered,
      edinet_recent_count: 0,
      score: r.technical_score ?? 0,
      generated_at: new Date().toISOString(),
    };
  }

  function handleTabChange(tab: Tab) {
    if (tab === activeTab) return;
    activeTab = tab;
    currentPage = 1;
    filteredTotal = 0;
    data = [];  // タブ切替時は前タブのデータを消去
    loadData();
  }

  function handleTabKeydown(e: KeyboardEvent, idx: number) {
    let next = idx;
    if (e.key === 'ArrowRight') next = (idx + 1) % TABS.length;
    else if (e.key === 'ArrowLeft') next = (idx - 1 + TABS.length) % TABS.length;
    else return;
    e.preventDefault();
    handleTabChange(TABS[next]);
    const tabEls = document.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    tabEls[next]?.focus();
  }

  function handleRowClick(code: string) {
    goto(`/signals/${code}`);
  }

  const TAB_LABELS: Record<Tab, string> = {
    market: '全市場訊號',
    favorites: '我的最愛',
    portfolio: '我的持倉',
    watchlist: '追蹤清單',
  };
</script>

<div class="signals-page">
  <div class="header">
    <div class="title-row">
      <h1>投機訊號</h1>
      <div class="header-actions">
        {#if scanInProgress && activeTab === 'market'}
          <span class="auto-reload-indicator">🔄 自動更新中...</span>
        {/if}
        {#if cacheTs !== null}
          <span class="cache-age">上次更新：{formatCacheAge(cacheTs)}</span>
        {/if}
        <button
          class="btn-refresh"
          disabled={refreshingAll || loading}
          title="清除快取，重新抓取全部資料"
          on:click={refreshAll}
        >
          <span class="refresh-icon" class:spinning={refreshingAll}>↻</span>
          <span class="refresh-text">全部更新</span>
        </button>
      </div>
    </div>
    <div class="tabs" role="tablist" aria-label="訊號分類">
      {#each TABS as tab, i}
        <button
          role="tab"
          class="tab"
          class:active={activeTab === tab}
          aria-selected={activeTab === tab}
          tabindex={activeTab === tab ? 0 : -1}
          on:click={() => handleTabChange(tab)}
          on:keydown={e => handleTabKeydown(e, i)}
        >
          {TAB_LABELS[tab]}
        </button>
      {/each}
    </div>
  </div>

  {#if loading && data.length === 0}
    <LoadingSpinner />
  {:else if error}
    <p class="error">{error}</p>
  {:else if noSnapshot}
    <div class="empty-state">
      <p>尚無投機訊號掃描快照。請至 <a href="/data">資料管理</a> 或執行掃描排程後再回來。</p>
    </div>
  {:else if data.length === 0}
    <div class="empty-state">
      <p>暫無資料。</p>
    </div>
  {:else}
    <DataTable
      {data}
      extraRows={activeTab === 'market' ? favoriteSignals : []}
      onRowClick={handleRowClick}
      onRefreshRow={refreshRow}
      {refreshingCodes}
      pageSize={activeTab === 'market' ? LIMIT : null}
      {currentPage}
      on:filteredTotal={(e) => (filteredTotal = e.detail)}
      on:pageReset={() => { currentPage = 1; }}
    />

    {#if activeTab === 'market' && (filteredTotal || totalCount) > LIMIT}
      <div class="pagination">
        {#if currentPage > 1}
          <button class="btn-page" on:click={() => goToPage(currentPage - 1)}>← 上一頁</button>
        {:else}
          <button class="btn-page" disabled>← 上一頁</button>
        {/if}

        <div class="page-numbers">
          {#each getPageNumbers() as page, idx (typeof page === 'number' ? `p-${page}` : `e-${idx}`)}
            {#if typeof page !== 'number'}
              <span class="page-ellipsis">...</span>
            {:else}
              <button
                class="page-num"
                class:active={currentPage === page}
                on:click={() => goToPage(page)}
              >
                {page}
              </button>
            {/if}
          {/each}
        </div>

        {#if currentPage < Math.ceil((filteredTotal || totalCount) / LIMIT)}
          <button class="btn-page" on:click={() => goToPage(currentPage + 1)}>下一頁 →</button>
        {:else}
          <button class="btn-page" disabled>下一頁 →</button>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .signals-page {
    padding: 24px;
  }

  .header {
    margin-bottom: 24px;
  }

  .title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .signals-page h1 {
    color: #4ade80;
    font-size: 28px;
    margin: 0;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .cache-age {
    font-size: 12px;
    color: #666;
  }

  .auto-reload-indicator {
    font-size: 12px;
    color: #4ade80;
    animation: pulse 1s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }

  .btn-refresh {
    background: #1a1a1a;
    border: 1px solid #444;
    color: #ccc;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: color 0.2s, border-color 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .btn-refresh:hover:not(:disabled) {
    color: #4ade80;
    border-color: #4ade80;
  }

  .btn-refresh:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .refresh-icon.spinning {
    animation: spin 0.7s linear infinite;
    display: inline-block;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .tabs {
    display: flex;
    gap: 8px;
    border-bottom: 1px solid #333;
  }

  .tab {
    background: none;
    border: none;
    padding: 8px 16px;
    color: #a1a1a1;
    cursor: pointer;
    font-size: 14px;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
  }

  .tab:hover {
    color: #fff;
  }

  .tab:focus-visible {
    outline: 2px solid #4ade80;
    outline-offset: 2px;
    border-radius: 2px;
  }

  .tab.active {
    color: #4ade80;
    border-bottom-color: #4ade80;
  }

  .error {
    color: #f87171;
    text-align: center;
    padding: 24px;
  }

  .empty-state {
    text-align: center;
    color: #aaa;
    padding: 60px 20px;
    background: #1d1d1d;
    border: 1px dashed #333;
    border-radius: 8px;
  }

  .empty-state a {
    color: #4ade80;
  }

  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-top: 24px;
    padding: 16px;
    background: #0a0a0a;
    border-radius: 4px;
    flex-wrap: wrap;
  }

  .page-numbers {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .page-num {
    background: #1a1a1a;
    border: 1px solid #444;
    color: #ccc;
    padding: 6px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s;
    min-width: 32px;
    text-align: center;
  }

  .page-num:hover {
    color: #4ade80;
    border-color: #4ade80;
  }

  .page-num.active {
    background: #4ade80;
    color: #000;
    border-color: #4ade80;
    font-weight: bold;
  }

  .page-ellipsis {
    color: #666;
    font-size: 12px;
    padding: 0 2px;
  }

  .btn-page {
    background: #1a1a1a;
    border: 1px solid #444;
    color: #ccc;
    padding: 8px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
  }

  .btn-page:hover:not(:disabled) {
    color: #4ade80;
    border-color: #4ade80;
  }

  .btn-page:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }
</style>
