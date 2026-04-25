<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import type {
    Simulation,
    SimulationConfig,
    CandidateEntry,
    EntryRule,
    ExitRule,
    PositionSizing,
    CostModel,
    SignalScanRow
  } from '$lib/types';

  let step = 1;
  let error = '';

  // Step 1: Basic settings
  let name = '';
  let kind: 'backtest' | 'paper' = 'backtest';
  let initialCapital = 1000000;
  let startDate = new Date().toISOString().split('T')[0];
  let endDate = new Date().toISOString().split('T')[0];

  // Step 2: Candidates
  let candidates: CandidateEntry[] = [];
  let candidateInput = '';
  let availableSignals: SignalScanRow[] = [];
  let loadingSignals = false;
  let selectedSignalCodes = new Set<string>();

  // Step 3: Rules
  let entryPriceBasis: 'signal_close' | 'next_open' | 'user_specified' = 'next_open';
  let userPrices: Record<string, number> = {};
  let requireSignal = true;

  let exitUseSignal = true;
  let exitUseStopLoss = true;
  let exitTakeProfitPct = 0.1;
  let exitMaxHoldDays = 30;
  let exitPriceBasis: 'signal_close' | 'next_open' = 'next_open';

  let positionMode: 'equal_weight' | 'fixed_jpy' | 'fixed_shares' = 'equal_weight';
  let positionFixedJpy = 100000;
  let positionFixedShares = 100;
  let maxConcurrentPositions = 10;

  let commissionPct = 0.001;
  let slippagePct = 0.001;
  let taxPct = 0.20315;

  async function loadSignals() {
    loadingSignals = true;
    try {
      availableSignals = await api<SignalScanRow[]>('/scan/signals');
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load signals';
    } finally {
      loadingSignals = false;
    }
  }

  function addCandidateFromSignal(code: string, name: string) {
    if (!candidates.some((c) => c.code === code)) {
      candidates = [
        ...candidates,
        {
          code,
          name,
          entry_signal_date: new Date().toISOString().split('T')[0],
          forced_entry_date: null
        }
      ];
    }
  }

  function addCandidateManual() {
    const code = candidateInput.trim().toUpperCase();
    if (code && !candidates.some((c) => c.code === code)) {
      candidates = [
        ...candidates,
        {
          code,
          name: code,
          entry_signal_date: null,
          forced_entry_date: null
        }
      ];
      candidateInput = '';
    }
  }

  function removeCandidate(code: string) {
    candidates = candidates.filter((c) => c.code !== code);
  }

  function nextStep() {
    if (step === 1) {
      if (!name) {
        error = '請輸入名稱';
        return;
      }
      if (kind === 'backtest' && !endDate) {
        error = '請選擇結束日期';
        return;
      }
    } else if (step === 2) {
      if (candidates.length === 0) {
        error = '請至少選擇一隻股票';
        return;
      }
    }
    error = '';
    step++;
  }

  function previousStep() {
    error = '';
    step--;
  }

  async function submit() {
    try {
      const entryRule: EntryRule = {
        price_basis: entryPriceBasis,
        user_price: entryPriceBasis === 'user_specified' ? userPrices[candidates[0]?.code] || 0 : null,
        require_signal: requireSignal
      };

      const exitRule: ExitRule = {
        use_exit_signal: exitUseSignal,
        use_stop_loss: exitUseStopLoss,
        take_profit_pct: exitTakeProfitPct || null,
        max_hold_days: exitMaxHoldDays || null,
        exit_price_basis: exitPriceBasis
      };

      const positionSizing: PositionSizing = {
        mode: positionMode,
        fixed_jpy: positionMode === 'fixed_jpy' ? positionFixedJpy : null,
        fixed_shares: positionMode === 'fixed_shares' ? positionFixedShares : null,
        max_concurrent_positions: maxConcurrentPositions
      };

      const costModel: CostModel = {
        commission_pct: commissionPct,
        slippage_pct: slippagePct,
        tax_pct: taxPct
      };

      const config: SimulationConfig = {
        kind,
        initial_capital: initialCapital,
        start_date: startDate,
        end_date: kind === 'backtest' ? endDate : null,
        candidates,
        entry_rule: entryRule,
        exit_rule: exitRule,
        position_sizing: positionSizing,
        cost_model: costModel
      };

      const sim = await api<Simulation>('/simulation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, config })
      });

      if (kind === 'backtest') {
        // Run backtest immediately
        await api(`/simulation/${sim.id}/run`, { method: 'POST' });
      }

      goto(`/simulation/${sim.id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to create simulation';
    }
  }

  $: if (step === 2 && availableSignals.length === 0) {
    loadSignals();
  }
</script>

<div class="wizard-page">
  <div class="wizard-container">
    <div class="steps-indicator">
      <div class={`step ${step >= 1 ? 'active' : ''}`}>
        <span>1</span>
        <p>基本設定</p>
      </div>
      <div class="step-line"></div>
      <div class={`step ${step >= 2 ? 'active' : ''}`}>
        <span>2</span>
        <p>候選股票</p>
      </div>
      <div class="step-line"></div>
      <div class={`step ${step >= 3 ? 'active' : ''}`}>
        <span>3</span>
        <p>規則設定</p>
      </div>
    </div>

    {#if error}
      <div class="error-message">{error}</div>
    {/if}

    <!-- Step 1: Basic Settings -->
    {#if step === 1}
      <div class="step-content">
        <h2>基本設定</h2>

        <div class="form-group">
          <label>名稱</label>
          <input type="text" bind:value={name} placeholder="例: Toyota 回測 2024" />
        </div>

        <div class="form-group">
          <label>類型</label>
          <div class="radio-group">
            <label>
              <input type="radio" bind:group={kind} value="backtest" />
              バックテスト
            </label>
            <label>
              <input type="radio" bind:group={kind} value="paper" />
              ペーパー
            </label>
          </div>
        </div>

        <div class="form-group">
          <label>初始資金 (JPY)</label>
          <input type="number" bind:value={initialCapital} min="100000" step="100000" />
        </div>

        <div class="form-group">
          <label>開始日期</label>
          <input type="date" bind:value={startDate} />
        </div>

        {#if kind === 'backtest'}
          <div class="form-group">
            <label>結束日期</label>
            <input type="date" bind:value={endDate} />
          </div>
        {/if}
      </div>
    {/if}

    <!-- Step 2: Candidates -->
    {#if step === 2}
      <div class="step-content">
        <h2>候選股票</h2>

        <div class="candidates-section">
          <div class="candidates-input">
            <h3>從訊號掃描選擇</h3>
            {#if loadingSignals}
              <div class="loading">讀取訊號中...</div>
            {:else}
              <div class="signal-grid">
                {#each availableSignals as signal (signal.code)}
                  <button
                    class={`signal-btn ${selectedSignalCodes.has(signal.code) ? 'selected' : ''}`}
                    on:click={() => {
                      if (selectedSignalCodes.has(signal.code)) {
                        selectedSignalCodes.delete(signal.code);
                        removeCandidate(signal.code);
                      } else {
                        selectedSignalCodes.add(signal.code);
                        addCandidateFromSignal(signal.code, signal.name);
                      }
                      selectedSignalCodes = selectedSignalCodes;
                    }}
                  >
                    {signal.code} {signal.name}
                  </button>
                {/each}
              </div>
            {/if}

            <h3 style="margin-top: 20px;">手動輸入</h3>
            <div class="manual-input">
              <input
                type="text"
                bind:value={candidateInput}
                placeholder="輸入股票代碼 (例: 7203)"
                on:keydown={(e) => e.key === 'Enter' && addCandidateManual()}
              />
              <button class="btn btn-secondary" on:click={addCandidateManual}>新增</button>
            </div>
          </div>

          <div class="candidates-list">
            <h3>已選候選</h3>
            {#if candidates.length === 0}
              <p class="empty-text">未選任何股票</p>
            {:else}
              <div class="candidate-items">
                {#each candidates as cand (cand.code)}
                  <div class="candidate-item">
                    <div>
                      <strong>{cand.code}</strong> {cand.name}
                    </div>
                    <button
                      class="btn-remove"
                      on:click={() => {
                        selectedSignalCodes.delete(cand.code);
                        removeCandidate(cand.code);
                        selectedSignalCodes = selectedSignalCodes;
                      }}
                    >
                      ✕
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      </div>
    {/if}

    <!-- Step 3: Rules -->
    {#if step === 3}
      <div class="step-content">
        <h2>規則設定</h2>

        <div class="rules-section">
          <div class="rule-group">
            <h3>進場規則</h3>
            <div class="form-group">
              <label>進場價</label>
              <div class="radio-group">
                <label>
                  <input type="radio" bind:group={entryPriceBasis} value="signal_close" />
                  訊號當日收盤
                </label>
                <label>
                  <input type="radio" bind:group={entryPriceBasis} value="next_open" />
                  隔日開盤
                </label>
                <label>
                  <input type="radio" bind:group={entryPriceBasis} value="user_specified" />
                  自訂價格
                </label>
              </div>
            </div>

            {#if entryPriceBasis === 'user_specified'}
              <div class="form-group">
                <label>進場價格</label>
                {#each candidates as cand (cand.code)}
                  <div class="inline-input">
                    <span>{cand.code}:</span>
                    <input
                      type="number"
                      bind:value={userPrices[cand.code]}
                      placeholder="價格"
                      step="0.01"
                    />
                  </div>
                {/each}
              </div>
            {/if}

            <div class="form-group">
              <label>
                <input type="checkbox" bind:checked={requireSignal} />
                要求當日仍有吃貨訊號才買
              </label>
            </div>
          </div>

          <div class="rule-group">
            <h3>出場規則</h3>
            <div class="form-group">
              <label>
                <input type="checkbox" bind:checked={exitUseSignal} />
                使用三選二出場訊號
              </label>
            </div>
            <div class="form-group">
              <label>
                <input type="checkbox" bind:checked={exitUseStopLoss} />
                使用停損 (-5% 連 2 日)
              </label>
            </div>
            <div class="form-group">
              <label>止盈 (%)</label>
              <input type="number" bind:value={exitTakeProfitPct} min="0" step="0.01" />
              <small>留空 = 不啟用</small>
            </div>
            <div class="form-group">
              <label>最大持有天數</label>
              <input type="number" bind:value={exitMaxHoldDays} min="1" />
              <small>留空 = 不限</small>
            </div>
            <div class="form-group">
              <label>出場價基準</label>
              <div class="radio-group">
                <label>
                  <input type="radio" bind:group={exitPriceBasis} value="signal_close" />
                  出場當日收盤
                </label>
                <label>
                  <input type="radio" bind:group={exitPriceBasis} value="next_open" />
                  隔日開盤
                </label>
              </div>
            </div>
          </div>

          <div class="rule-group">
            <h3>持倉管理</h3>
            <div class="form-group">
              <label>分配模式</label>
              <div class="radio-group">
                <label>
                  <input type="radio" bind:group={positionMode} value="equal_weight" />
                  等權
                </label>
                <label>
                  <input type="radio" bind:group={positionMode} value="fixed_jpy" />
                  定額 (JPY)
                </label>
                <label>
                  <input type="radio" bind:group={positionMode} value="fixed_shares" />
                  定股數
                </label>
              </div>
            </div>

            {#if positionMode === 'fixed_jpy'}
              <div class="form-group">
                <label>單檔金額 (JPY)</label>
                <input type="number" bind:value={positionFixedJpy} min="10000" step="10000" />
              </div>
            {/if}

            {#if positionMode === 'fixed_shares'}
              <div class="form-group">
                <label>單檔股數</label>
                <input type="number" bind:value={positionFixedShares} min="1" />
              </div>
            {/if}

            <div class="form-group">
              <label>最多同時持倉數</label>
              <input type="number" bind:value={maxConcurrentPositions} min="1" max="20" />
            </div>
          </div>

          <div class="rule-group">
            <h3>成本模型</h3>
            <div class="form-group">
              <label>手續費 (%)</label>
              <input type="number" bind:value={commissionPct} min="0" step="0.0001" />
            </div>
            <div class="form-group">
              <label>滑價 (%)</label>
              <input type="number" bind:value={slippagePct} min="0" step="0.0001" />
            </div>
            <div class="form-group">
              <label>稅率 (%)</label>
              <input type="number" bind:value={taxPct} min="0" step="0.0001" />
            </div>
          </div>
        </div>
      </div>
    {/if}

    <div class="button-group">
      {#if step > 1}
        <button class="btn btn-secondary" on:click={previousStep}>← 上一步</button>
      {/if}

      {#if step < 3}
        <button class="btn btn-primary" on:click={nextStep}>下一步 →</button>
      {:else}
        <button class="btn btn-primary" on:click={submit}>
          {kind === 'backtest' ? '建立並回測' : '建立模擬'}
        </button>
      {/if}
    </div>
  </div>
</div>

<style>
  .wizard-page {
    padding: 20px;
    max-width: 900px;
    margin: 0 auto;
  }

  .wizard-container {
    background-color: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 30px;
  }

  .steps-indicator {
    display: flex;
    align-items: center;
    margin-bottom: 40px;
    justify-content: center;
  }

  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .step span {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background-color: #333;
    color: #999;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 16px;
  }

  .step.active span {
    background-color: #4ade80;
    color: #1a1a1a;
  }

  .step p {
    font-size: 12px;
    color: #999;
    margin: 0;
  }

  .step.active p {
    color: #4ade80;
    font-weight: 500;
  }

  .step-line {
    width: 60px;
    height: 2px;
    background-color: #333;
    margin: 0 20px;
  }

  .error-message {
    background-color: #7f1d1d;
    color: #fca5a5;
    padding: 12px;
    border-radius: 4px;
    margin-bottom: 20px;
  }

  .step-content {
    margin-bottom: 30px;
  }

  h2 {
    color: #4ade80;
    margin: 0 0 20px 0;
    font-size: 20px;
  }

  h3 {
    color: #e5e5e5;
    margin: 20px 0 12px 0;
    font-size: 14px;
    font-weight: 600;
  }

  .form-group {
    margin-bottom: 16px;
  }

  label {
    display: block;
    color: #e5e5e5;
    margin-bottom: 6px;
    font-size: 14px;
  }

  input[type='text'],
  input[type='number'],
  input[type='date'] {
    width: 100%;
    padding: 8px 12px;
    background-color: #2a2a2a;
    color: #e5e5e5;
    border: 1px solid #444;
    border-radius: 4px;
    font-size: 14px;
  }

  input[type='text']:focus,
  input[type='number']:focus,
  input[type='date']:focus {
    outline: none;
    border-color: #4ade80;
    background-color: #222;
  }

  .radio-group {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .radio-group label {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 0;
  }

  input[type='radio'],
  input[type='checkbox'] {
    accent-color: #4ade80;
    cursor: pointer;
  }

  small {
    display: block;
    color: #999;
    font-size: 12px;
    margin-top: 4px;
  }

  .candidates-section {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }

  .candidates-input,
  .candidates-list {
    background-color: #0f0f0f;
    border: 1px solid #333;
    padding: 16px;
    border-radius: 4px;
  }

  .signal-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }

  .signal-btn {
    padding: 8px;
    background-color: #2a2a2a;
    color: #e5e5e5;
    border: 1px solid #444;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    text-align: left;
    transition: all 0.2s;
  }

  .signal-btn:hover {
    background-color: #333;
  }

  .signal-btn.selected {
    background-color: #4ade80;
    color: #1a1a1a;
    border-color: #3dd66f;
  }

  .manual-input {
    display: flex;
    gap: 8px;
    margin-top: 10px;
  }

  .manual-input input {
    flex: 1;
  }

  .candidate-items {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .candidate-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px;
    background-color: #2a2a2a;
    border-radius: 4px;
    border: 1px solid #444;
    color: #e5e5e5;
    font-size: 13px;
  }

  .btn-remove {
    background: none;
    border: none;
    color: #f87171;
    cursor: pointer;
    font-size: 16px;
  }

  .btn-remove:hover {
    color: #ef4444;
  }

  .empty-text {
    color: #999;
    text-align: center;
    padding: 20px 0;
    margin: 0;
  }

  .rules-section {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }

  .rule-group {
    background-color: #0f0f0f;
    border: 1px solid #333;
    padding: 16px;
    border-radius: 4px;
  }

  .inline-input {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 8px;
  }

  .inline-input span {
    min-width: 50px;
    color: #e5e5e5;
    font-size: 13px;
  }

  .inline-input input {
    flex: 1;
    margin: 0;
  }

  .btn {
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s;
  }

  .btn-primary {
    background-color: #4ade80;
    color: #1a1a1a;
  }

  .btn-primary:hover {
    background-color: #3dd66f;
  }

  .btn-secondary {
    background-color: #444;
    color: #e5e5e5;
  }

  .btn-secondary:hover {
    background-color: #555;
  }

  .button-group {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 30px;
    border-top: 1px solid #333;
    padding-top: 20px;
  }

  .loading {
    text-align: center;
    color: #999;
    padding: 20px;
  }
</style>
