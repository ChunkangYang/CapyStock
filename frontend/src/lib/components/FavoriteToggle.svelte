<script lang="ts">
  import { favorites } from '$lib/stores/favorites';
  import { api } from '$lib/api';

  export let code: string;
  export let name: string;
  export let tag: string = 'speculative';

  let isFavorite = false;
  let loading = false;

  $: isFavorite = $favorites.some(f => f.code === code && f.tags.includes(tag));

  async function toggle() {
    if (loading) return;
    loading = true;

    try {
      if (isFavorite) {
        await api(`/favorites/${code}?tag=${tag}`, { method: 'DELETE' });
        favorites.update(fav => fav.filter(f => f.code !== code || !f.tags.includes(tag)));
      } else {
        await api('/favorites', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, name, tag }),
        });
        if (!$favorites.some(f => f.code === code)) {
          favorites.update(fav => [...fav, { code, name, tags: [tag], added_at: new Date().toISOString(), note: '' }]);
        } else {
          favorites.update(fav => fav.map(f =>
            f.code === code ? { ...f, tags: [...new Set([...f.tags, tag])] } : f
          ));
        }
      }
    } catch (e) {
      console.error('Failed to toggle favorite:', e);
    } finally {
      loading = false;
    }
  }
</script>

<button
  class="favorite-btn"
  class:active={isFavorite}
  on:click={toggle}
  disabled={loading}
  title={isFavorite ? '移除最愛' : '加入最愛'}
>
  {#if isFavorite}
    ★
  {:else}
    ☆
  {/if}
</button>

<style>
  .favorite-btn {
    background: none;
    border: none;
    font-size: 20px;
    color: #888;
    cursor: pointer;
    padding: 4px 8px;
    transition: color 0.2s;
  }

  .favorite-btn:hover {
    color: #f59e0b;
  }

  .favorite-btn.active {
    color: #f59e0b;
  }

  .favorite-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
