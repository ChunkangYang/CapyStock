# Sprint 10 — 通知規則 + 警報 → 推送整合

依賴：[MILESTONE_04.md](MILESTONE_04.md)

## 目的
- 不是每次有 alert 就轟炸；要可訂閱 / 過濾
- 兩種模式並存：**digest（每日彙總）** vs **realtime（critical 即時）**

## 資料結構（`data/notification_rules.json`）

```json
{
  "rules": [
    {
      "id": "rule-default-digest",
      "name": "每日彙總",
      "mode": "digest",
      "trigger": { "schedule": "daily", "time": "08:00" },
      "filters": {
        "alert_types": ["exit", "stop_loss", "accumulation"],
        "min_severity": "info",
        "scope": "watchlist"
      },
      "channels": ["email"],
      "recipients_by_channel": { "email": ["cky1983@gmail.com"] },
      "enabled": true
    },
    {
      "id": "rule-stop-loss-realtime",
      "name": "停損即時警報",
      "mode": "realtime",
      "trigger": { "on_alert": true },
      "filters": {
        "alert_types": ["stop_loss"],
        "min_severity": "critical",
        "scope": "watchlist"
      },
      "channels": ["email", "line"],
      "recipients_by_channel": { "email": ["cky1983@gmail.com"] },
      "enabled": true
    }
  ]
}
```

## 檔案
- `api/services/notification_service.py`：擴 `process_alerts()`、`build_digest()`、`evaluate_rules()`
- `api/notify/digest.py`
- `api/routers/notify.py`：擴 rules CRUD endpoints

## Digest 組裝（digest.py）

```python
def build_digest(date: date, alerts_by_code: dict[str, list[Alert]], snapshot_summary: dict, scope: Literal["watchlist","favorites","all"]) -> NotificationPayload:
    """
    產出 HTML：
      ## CapyStock 每日彙總 — 2026-04-26
      ### 持倉警示（N） / ### 停損警示（N） / ### 吃貨訊號（N） / ### EDINET 5%申報（N）
      ### 模擬交易摘要：- paper-foo：當前權益 1,234,567（+5.2%）
    """
```

## 整合點

```python
def process_daily_digest(today: date, dry_run: bool=False) -> list[ChannelResult]:
    """1. 對所有 enabled mode=digest rule，依 trigger.time 判斷
       2. 用 scope 過濾 watchlist / favorites / all
       3. analyze_watchlist + scan_service.load_latest_snapshot('signals')
       4. build_digest → channels.send"""

def process_realtime_alert(alert: Alert, code: str) -> list[ChannelResult]:
    """1. 對所有 enabled mode=realtime rule
       2. filters 命中即送
       3. 送之前 dedupe：notification_log.csv 中過去 24h 同 (rule_id, code, alert_type) 已送過 → skip"""
```

## Router 擴充

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/notify/rules` | 列表 |
| POST | `/api/v1/notify/rules` | 新增 |
| PATCH | `/api/v1/notify/rules/{id}` | 修改 |
| DELETE | `/api/v1/notify/rules/{id}` | 刪除 |
| POST | `/api/v1/notify/rules/{id}/run` | 立即執行（body `{dry_run?: true}`） |
| POST | `/api/v1/notify/digest/preview` | body `{rule_id?, date?}`：回 NotificationPayload（不發送） |

## 驗收（自動化）

- Digest：給定 alerts dict + snapshot → 產出 HTML 含預期 H2 / row
- 規則命中：給 5 個 alert，rule filter 留 2 → channel.send 被呼叫 1 次
- 即時 dedupe：同 alert 連送兩次，第二次空（log 只一筆）
- Rule CRUD：POST/PATCH/DELETE 各 happy + 4xx
- preview：不真送，但回 body_html 內容正確
- 排程時間判定：daily 08:00，給 `now=07:59` 不跑；`now=08:00` 跑；`now=08:30` 但今日尚未跑過 → catch-up
