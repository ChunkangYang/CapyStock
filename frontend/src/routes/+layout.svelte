<script lang="ts">
  import { onMount } from 'svelte';
  import { loadFavorites } from '$lib/stores/favorites';
  import './styles.css';

  let currentPath = '/';

  onMount(() => {
    loadFavorites();
  });
</script>

<div class="layout">
  <nav class="sidebar">
    <div class="logo">CapyStock</div>
    <ul class="nav-links">
      <li>
        <a href="/" class:active={currentPath === '/'}>Dashboard</a>
      </li>
      <li>
        <a href="/signals" class:active={currentPath.startsWith('/signals') && !currentPath.startsWith('/signals/compare')}>
          投機訊號
        </a>
      </li>
      <li>
        <a href="/compare" class:active={currentPath.startsWith('/compare')}>
          投機對比
        </a>
      </li>
      <li>
        <a href="/dividend" class:active={currentPath.startsWith('/dividend') && !currentPath.startsWith('/dividend/compare')}>
          金雞高股息
        </a>
      </li>
      <li>
        <a href="/dividend/compare" class:active={currentPath.startsWith('/dividend/compare')}>
          金雞對比
        </a>
      </li>
      <li>
        <a href="/portfolio" class:active={currentPath.startsWith('/portfolio')}>
          持倉管理
        </a>
      </li>
      <li>
        <a href="/favorites" class:active={currentPath.startsWith('/favorites')}>
          我的最愛
        </a>
      </li>
      <li>
        <a
          href="/simulation"
          class:active={currentPath.startsWith('/simulation')}
        >
          模擬交易
        </a>
      </li>
      <li>
        <a href="/settings/notifications" class:active={currentPath.startsWith('/settings')}>
          設定
        </a>
      </li>
    </ul>
  </nav>

  <main class="content">
    <slot />
  </main>
</div>

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    background-color: #0f0f0f;
    color: #e5e7eb;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
      Ubuntu, Cantarell, sans-serif;
  }

  .layout {
    display: flex;
    height: 100vh;
  }

  .sidebar {
    width: 250px;
    background-color: #1a1a1a;
    border-right: 1px solid #333;
    padding: 20px 0;
    overflow-y: auto;
  }

  .logo {
    padding: 20px;
    font-size: 24px;
    font-weight: bold;
    color: #4ade80;
    border-bottom: 1px solid #333;
    margin-bottom: 20px;
  }

  .nav-links {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .nav-links li {
    margin: 0;
  }

  .nav-links a {
    display: block;
    padding: 12px 20px;
    color: #a1a1a1;
    text-decoration: none;
    transition: all 0.3s ease;
    border-left: 3px solid transparent;
  }

  .nav-links a:hover {
    background-color: #2a2a2a;
    color: #e5e7eb;
  }

  .nav-links a.active {
    background-color: #2a2a2a;
    color: #4ade80;
    border-left-color: #4ade80;
  }

  .content {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
  }
</style>
