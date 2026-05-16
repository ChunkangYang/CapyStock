// 30 天 — 使用者不要即時，永遠用 cache 顯示，直到手動點「更新」
const TTL = 30 * 24 * 60 * 60 * 1000;

interface CacheEntry<T> {
  data: T;
  ts: number;
}

export function cacheGet<T>(key: string): T | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const entry: CacheEntry<T> = JSON.parse(raw);
    if (Date.now() - entry.ts > TTL) {
      localStorage.removeItem(key);
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

export function cacheSet<T>(key: string, data: T): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify({ data, ts: Date.now() }));
  } catch {}
}

export function cacheClear(key: string): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(key);
}

/** 回傳快取存入時的 ms 時間戳，沒有快取回傳 null */
export function cacheTimestamp(key: string): number | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const entry = JSON.parse(raw);
    return typeof entry.ts === 'number' ? entry.ts : null;
  } catch {
    return null;
  }
}

/** 清除指定 prefix 開頭的快取 */
export function clearCacheByPrefix(prefix: string): void {
  if (typeof localStorage === 'undefined') return;
  Object.keys(localStorage)
    .filter(k => k.startsWith(prefix))
    .forEach(k => localStorage.removeItem(k));
}

/** 清除所有 signals_ 開頭的快取（向後相容） */
export function clearAllSignalsCache(): void {
  clearCacheByPrefix('signals_');
}

/** 帶 cache 的 fetch 包裝：cache 有就用 cache，否則打 API 並 cache */
export async function cachedFetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  forceRefresh = false,
): Promise<{ data: T; fromCache: boolean; ts: number }> {
  if (!forceRefresh) {
    const cached = cacheGet<T>(key);
    if (cached !== null) {
      return { data: cached, fromCache: true, ts: cacheTimestamp(key) ?? Date.now() };
    }
  }
  const data = await fetcher();
  cacheSet(key, data);
  return { data, fromCache: false, ts: Date.now() };
}

/** 格式化快取年齡為人類可讀字串 */
export function formatCacheAge(ts: number): string {
  const ms = Date.now() - ts;
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return '剛剛';
  if (mins < 60) return `${mins} 分鐘前`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} 小時前`;
  return `${Math.floor(hrs / 24)} 天前`;
}
