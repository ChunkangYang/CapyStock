import { describe, it, expect, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import {
  favorites,
  loadFavorites,
  addFavorite,
  removeFavorite,
  updateFavoriteNote,
} from '$lib/stores/favorites';
import * as api from '$lib/api';

vi.mock('$lib/api');

describe('favorites store', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    favorites.set({});
  });

  it('should load favorites from API', async () => {
    const mockFavs = {
      '7203': {
        code: '7203',
        name: 'Toyota',
        tags: ['dividend'],
        added_at: '2026-04-25T10:00:00',
        note: 'Dividend play',
      },
    };

    vi.spyOn(api, 'api').mockResolvedValueOnce(mockFavs);

    await loadFavorites();

    expect(get(favorites)).toEqual(mockFavs);
  });

  it('should handle API errors gracefully', async () => {
    vi.spyOn(api, 'api').mockRejectedValueOnce(new Error('Network error'));

    await loadFavorites();

    expect(get(favorites)).toEqual({});
  });

  it('should add favorite and merge tags', async () => {
    const newFav = {
      code: '9984',
      name: 'SoftBank',
      tags: ['speculative'],
      added_at: '2026-04-25T10:01:00',
      note: '',
    };

    vi.spyOn(api, 'api').mockResolvedValueOnce(newFav);

    await addFavorite('9984', 'speculative', 'SoftBank');

    const store = get(favorites);
    expect(store['9984']).toEqual(newFav);
  });

  it('should handle tags merging on add', async () => {
    const existing = {
      code: '7203',
      name: 'Toyota',
      tags: ['dividend'],
      added_at: '2026-04-25T10:00:00',
      note: '',
    };

    const merged = {
      code: '7203',
      name: 'Toyota',
      tags: ['dividend', 'speculative'],
      added_at: '2026-04-25T10:00:00',
      note: '',
    };

    favorites.set({ '7203': existing });
    vi.spyOn(api, 'api').mockResolvedValueOnce(merged);

    await addFavorite('7203', 'speculative');

    expect(get(favorites)['7203'].tags).toContain('speculative');
    expect(get(favorites)['7203'].tags).toContain('dividend');
  });

  it('should remove favorite entirely', async () => {
    const fav = {
      code: '7203',
      name: 'Toyota',
      tags: ['dividend'],
      added_at: '2026-04-25T10:00:00',
      note: '',
    };

    favorites.set({ '7203': fav });

    vi.spyOn(api, 'api').mockResolvedValueOnce(undefined);

    await removeFavorite('7203');

    expect(get(favorites)['7203']).toBeUndefined();
  });

  it('should remove single tag and keep entry if other tags exist', async () => {
    const fav = {
      code: '7203',
      name: 'Toyota',
      tags: ['dividend', 'speculative'],
      added_at: '2026-04-25T10:00:00',
      note: '',
    };

    favorites.set({ '7203': fav });

    vi.spyOn(api, 'api').mockResolvedValueOnce(undefined);

    await removeFavorite('7203', 'speculative');

    const store = get(favorites);
    expect(store['7203']).toBeDefined();
    expect(store['7203'].tags).toEqual(['dividend']);
  });

  it('should update favorite note', async () => {
    const fav = {
      code: '7203',
      name: 'Toyota',
      tags: ['dividend'],
      added_at: '2026-04-25T10:00:00',
      note: '',
    };

    const updated = {
      ...fav,
      note: 'Strong dividend+buyback',
    };

    favorites.set({ '7203': fav });
    vi.spyOn(api, 'api').mockResolvedValueOnce(updated);

    await updateFavoriteNote('7203', 'Strong dividend+buyback');

    expect(get(favorites)['7203'].note).toBe('Strong dividend+buyback');
  });
});
