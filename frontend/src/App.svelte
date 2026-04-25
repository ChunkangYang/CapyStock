<script>
  let currentPath = '/';

  function navigate(path) {
    currentPath = path;
    window.history.pushState(null, '', path);
  }
</script>

<div class="layout">
  <nav class="sidebar">
    <div class="logo">CapyStock</div>
    <ul class="nav-links">
      <li>
        <a href="/" on:click={() => navigate('/')} class:active={currentPath === '/'}>
          Dashboard
        </a>
      </li>
      <li>
        <a
          href="/signals"
          on:click={() => navigate('/signals')}
          class:active={currentPath.startsWith('/signals')}
        >
          投機訊號
        </a>
      </li>
      <li>
        <a
          href="/dividend"
          on:click={() => navigate('/dividend')}
          class:active={currentPath.startsWith('/dividend')}
        >
          金雞高股息
        </a>
      </li>
      <li>
        <a
          href="/favorites"
          on:click={() => navigate('/favorites')}
          class:active={currentPath.startsWith('/favorites')}
        >
          我的最愛
        </a>
      </li>
      <li>
        <a
          href="/simulation"
          on:click={() => navigate('/simulation')}
          class:active={currentPath.startsWith('/simulation')}
        >
          模擬交易
        </a>
      </li>
    </ul>
  </nav>

  <main class="content">
    {#if currentPath === '/'}
      <div class="dashboard">
        <h1>Dashboard</h1>
        <p>首頁內容將在此顯示</p>
      </div>
    {/if}
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

  .dashboard h1 {
    color: #4ade80;
    margin: 0 0 20px 0;
  }

  .dashboard p {
    color: #a1a1a1;
  }
</style>
