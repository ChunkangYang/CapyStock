<script lang="ts">
  import { onMount } from 'svelte';

  let loading = true;

  onMount(() => {
    loading = false;
  });
</script>

<div class="simulation-page">
  <h1>模擬交易</h1>
  <p>模擬交易功能將在 Sprint 7-8 實現</p>
</div>

<style>
  .simulation-page h1 {
    color: #4ade80;
    margin: 0 0 20px 0;
  }

  p {
    color: #a1a1a1;
  }
</style>
