# Sprint 22 — 策略參數 Sweep（網格回測）

依賴：[MILESTONE_06.md](MILESTONE_06.md)

## 目的
- 模擬交易目前一次只跑一組參數
- Sweep：給定參數網格 → 跑 N 組 backtest → 回傳排名 + 熱圖資料
- 用途：找最佳停損 % / take profit / max_hold_days

## 檔案
- `api/services/strategy_sweep_service.py`
- `api/routers/sweep.py`
- `api/schemas/sweep.py`
- `frontend/src/routes/simulation/sweep/+page.svelte`

## Schema

```python
class ParamGrid(BaseModel):
    """每欄位 list[value]；笛卡兒積"""
    stop_loss_pct: list[float] | None = None
    take_profit_pct: list[float] | None = None
    max_hold_days: list[int] | None = None
    indicator_entry_combos: list[list[str]] | None = None

class SweepRequest(BaseModel):
    base_config: SimulationConfig
    grid: ParamGrid
    metric: Literal["total_return", "sharpe", "profit_factor", "win_rate", "max_drawdown"] = "total_return"
    top_n: int = 20

class SweepRow(BaseModel):
    params: dict
    total_return: float
    annualized: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    n_trades: int

class SweepResult(BaseModel):
    request: SweepRequest
    rows: list[SweepRow]
    started_at: datetime
    finished_at: datetime
    n_combinations: int
```

## Service

```python
class StrategySweepService:
    def run(self, req: SweepRequest, on_progress: Callable[[int, int], None] | None=None) -> SweepResult:
        """
        1. 笛卡兒積展開 grid
        2. 對每組複製 base_config，覆蓋對應欄位
        3. 呼叫 backtest_engine.run_backtest（使用快取資料）
        4. 收集 metrics → 排序
        """
```

## 性能限制
- combinations > 200 → 拒絕（422）
- 預設使用 `concurrent.futures.ProcessPoolExecutor`，max_workers = `min(8, os.cpu_count())`
- 進度透過 SSE 回前端：`GET /api/v1/sweep/{job_id}/stream`

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| POST | `/api/v1/sweep/run` | 啟動 job，回 `{job_id}` |
| GET | `/api/v1/sweep/{job_id}` | 查狀態 + 結果 |
| GET | `/api/v1/sweep/{job_id}/stream` | SSE 進度 |
| DELETE | `/api/v1/sweep/{job_id}` | 取消 |

## Sweep UI

### `/simulation/sweep`
- 參數網格表單：每欄位可輸入 list（chip input）
- 進場名單：與 `/simulation/new` Step 2 共用元件
- 「估算 N 組合」即時顯示
- 「執行」→ 進度條（SSE）+ 預估剩餘
- 完成顯示：
  - **熱圖**（2 維 sweep 時）：x = stop_loss, y = take_profit, 色 = total_return
  - **排行榜表格**：top_n
  - **點 row → 跳完整 simulation 詳情頁**（自動建一筆模擬保存結果）

## 驗收（自動化）

- 網格 stop_loss=[0.03,0.05] × take_profit=[0.10,0.15] = 4 組合 → rows 4 列
- 排序：metric=total_return desc，第 1 列 ≥ 第 2 列
- 過大網格：500 組合 → 422
- 並行正確性：並行跑 4 組 vs 序列跑，rows 完全相同
- SSE：模擬 mock 進度 → 收到 5 個事件依序 (0/4)..(4/4)
- DELETE 中途：剩餘任務不執行，status=cancelled

`npm run test:e2e` 通過 `e2e/sweep.spec.ts`：
1. `/simulation/sweep`：填三個欄位 → 「估算 N 組合」顯示 = 預期數
2. 執行 → 進度條動 → 完成顯示熱圖 + 表格
3. 點 top 1 → 跳 `/simulation/{id}`，配置欄位 = sweep 該組合
4. 截圖回歸：2 張
