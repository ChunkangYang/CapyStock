import { writable } from 'svelte/store';
import { api } from '$lib/api';
import type { FavoriteEntry } from '$lib/types';

export const favorites = writable<Record<string, FavoriteEntry>>({});

export async function loadFavorites() {
  try {
    const data = await api<FavoriteEntry[] | Record<string, FavoriteEntry>>('/favorites');
    if (Array.isArray(data)) {
      const map: Record<string, FavoriteEntry> = {};
      for (const entry of data) map[entry.code] = entry;
      favorites.set(map);
    } else {
      favorites.set(data || {});
    }
  } catch (error) {
    console.error('Failed to load favorites:', error);
    favorites.set({});
  }
}

export async function addFavorite(
  code: string,
  tag: string,
  name?: string,
  note?: string,
) {
  try {
    const result = await api<FavoriteEntry>('/favorites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, tag, name, note }),
    });
    favorites.update((f) => ({ ...f, [code]: result }));
  } catch (error) {
    console.error('Failed to add favorite:', error);
    throw error;
  }
}

export async function removeFavorite(code: string, tag?: string) {
  try {
    await api(`/favorites/${code}${tag ? `?tag=${tag}` : ''}`, {
      method: 'DELETE',
    });
    favorites.update((f) => {
      const updated = { ...f };
      if (tag) {
        const entry = updated[code];
        if (entry) {
          entry.tags = entry.tags.filter((t) => t !== tag);
          if (entry.tags.length === 0) {
            delete updated[code];
          }
        }
      } else {
        delete updated[code];
      }
      return updated;
    });
  } catch (error) {
    console.error('Failed to remove favorite:', error);
    throw error;
  }
}

export async function updateFavoriteNote(code: string, note: string) {
  try {
    const result = await api<FavoriteEntry>(`/favorites/${code}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    });
    favorites.update((f) => ({ ...f, [code]: result }));
  } catch (error) {
    console.error('Failed to update favorite note:', error);
    throw error;
  }
}
