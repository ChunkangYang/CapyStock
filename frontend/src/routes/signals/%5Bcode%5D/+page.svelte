<script lang="ts">
  import { page } from '$app/stores';

  const code = $page.params.code;
</script>

<div class="signal-detail">
  <h1>{code} 訊號詳細</h1>
  <p>詳細頁面將在 Sprint 5 實現</p>
</div>

<style>
  .signal-detail h1 {
    color: #4ade80;
    margin: 0 0 20px 0;
  }

  p {
    color: #a1a1a1;
  }
</style>
