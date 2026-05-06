<script lang="ts">
  export let size: 'sm' | 'md' | 'lg' = 'md';
  export let label = '載入中…';
</script>

<div class="spinner-wrap spinner-{size}">
  <div class="spinner"></div>
  {#if label}
    <span class="label">{label}</span>
  {/if}
</div>

<style>
  .spinner-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 40px;
    color: #a1a1a1;
  }

  .spinner-sm { padding: 16px; gap: 8px; }
  .spinner-lg { padding: 80px; gap: 16px; }

  .spinner {
    border: 3px solid #2a2a2a;
    border-top-color: #4ade80;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  .spinner-md .spinner { width: 36px; height: 36px; }
  .spinner-sm .spinner { width: 20px; height: 20px; border-width: 2px; }
  .spinner-lg .spinner { width: 56px; height: 56px; border-width: 4px; }

  .label {
    font-size: 13px;
    letter-spacing: 0.03em;
  }

  .spinner-sm .label { font-size: 12px; }
  .spinner-lg .label { font-size: 15px; }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
