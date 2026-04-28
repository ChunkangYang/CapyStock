<script lang="ts">
  export let correlationMatrix: Record<string, Record<string, number>> = {};
  export let codes: string[] = [];

  function getColor(val: number | null | undefined): string {
    if (val == null || isNaN(val as number)) return '#333';
    if (val >= 0.7) return '#16a34a';
    if (val >= 0.3) return '#4ade80';
    if (val >= -0.3) return '#a1a1a1';
    if (val >= -0.7) return '#f97316';
    return '#ef4444';
  }

  function fmt(val: number | null | undefined): string {
    if (val == null || isNaN(val as number)) return 'N/A';
    return val.toFixed(2);
  }
</script>

<div class="compare-panel">
  <h4>相關性矩陣</h4>
  {#if codes.length > 0}
    <table class="matrix-table">
      <thead>
        <tr>
          <th></th>
          {#each codes as c}
            <th>{c}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each codes as c1}
          <tr>
            <td class="row-label">{c1}</td>
            {#each codes as c2}
              <td
                class="cell"
                style="background:{getColor(correlationMatrix[c1]?.[c2])}"
              >
                {fmt(correlationMatrix[c1]?.[c2])}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <p class="empty">無資料</p>
  {/if}
</div>

<style>
  .compare-panel {
    background: #1a1a1a;
    border-radius: 8px;
    padding: 16px;
  }
  h4 {
    color: #fff;
    margin: 0 0 12px 0;
    font-size: 14px;
  }
  .matrix-table {
    border-collapse: collapse;
    width: 100%;
    font-size: 13px;
  }
  th, td {
    border: 1px solid #333;
    padding: 8px 12px;
    text-align: center;
  }
  th {
    background: #111;
    color: #a1a1a1;
    font-weight: 600;
  }
  .row-label {
    background: #111;
    color: #a1a1a1;
    font-weight: 600;
  }
  .cell {
    color: #fff;
    font-weight: 500;
  }
  .empty {
    color: #666;
    font-size: 13px;
  }
</style>
