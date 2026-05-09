<script lang="ts">
  import { page } from '$app/stores';
  $: path = $page.url.pathname;
</script>

<div class="settings-shell">
  <header class="subnav">
    <h1>設定</h1>
    <nav>
      <a href="/settings/notifications" class:active={path.startsWith('/settings/notifications')}>
        通知
      </a>
      <a href="/settings/scheduler" class:active={path.startsWith('/settings/scheduler')}>
        排程
      </a>
      <a href="/settings/health" class:active={path.startsWith('/settings/health')}>
        健康
      </a>
    </nav>
  </header>

  <section class="body">
    <slot />
  </section>
</div>

<style>
  .settings-shell {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .subnav {
    display: flex;
    align-items: center;
    gap: 24px;
    border-bottom: 1px solid #333;
    padding-bottom: 12px;
  }
  .subnav h1 {
    font-size: 18px;
    margin: 0;
    color: #4ade80;
  }
  .subnav nav {
    display: flex;
    gap: 12px;
  }
  .subnav a {
    color: #a1a1a1;
    text-decoration: none;
    padding: 6px 12px;
    border-radius: 6px;
  }
  .subnav a:hover {
    background: #2a2a2a;
    color: #e5e7eb;
  }
  .subnav a.active {
    background: #2a2a2a;
    color: #4ade80;
  }
</style>
