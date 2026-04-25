<script lang="ts">
  import { favorites } from '$lib/stores/favorites';

  $: favoriteList = Object.values($favorites);
</script>

<div class="favorites-page">
  <h1>我的最愛</h1>

  {#if favoriteList.length === 0}
    <p class="empty">還沒有任何最愛股票</p>
  {:else}
    <div class="favorite-list">
      {#each favoriteList as fav (fav.code)}
        <div class="favorite-item">
          <div class="header">
            <span class="code">{fav.code}</span>
            <span class="name">{fav.name}</span>
          </div>
          <div class="tags">
            {#each fav.tags as tag}
              <span class="tag">{tag}</span>
            {/each}
          </div>
          {#if fav.note}
            <p class="note">{fav.note}</p>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .favorites-page h1 {
    color: #4ade80;
    margin: 0 0 30px 0;
  }

  .empty {
    color: #6b7280;
    text-align: center;
    padding: 40px 20px;
  }

  .favorite-list {
    display: grid;
    gap: 16px;
  }

  .favorite-item {
    background-color: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 16px;
    transition: border-color 0.3s ease;
  }

  .favorite-item:hover {
    border-color: #4ade80;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .code {
    font-weight: 600;
    color: #4ade80;
    font-size: 16px;
  }

  .name {
    color: #a1a1a1;
    font-size: 14px;
  }

  .tags {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }

  .tag {
    background-color: #2a2a2a;
    color: #e5e7eb;
    padding: 4px 8px;
    border-radius: 3px;
    font-size: 12px;
  }

  .note {
    color: #9ca3af;
    margin: 8px 0 0 0;
    font-size: 13px;
  }
</style>
