const TTL = 24 * 60 * 60 * 1000; // 24 h

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

/** 清除所有 signals_ 開頭的快取 */
export function clearAllSignalsCache(): void {
  if (typeof localStorage === 'undefined') return;
  Object.keys(localStorage)
    .filter(k => k.startsWith('signals_'))
    .forEach(k => localStorage.removeItem(k));
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
