# Sprint 9 — 通知通道抽象 + Email/LINE 推送

依賴：[MILESTONE_04.md](MILESTONE_04.md)

## 目的
建立 channel-agnostic 通知層，未來新增 Telegram / Discord 不用改 service。

## 檔案
- `api/notify/base.py` / `email_channel.py` / `line_channel.py` / `digest.py`
- `api/services/notification_service.py`
- `api/routers/notify.py`
- `api/schemas/notify.py`
- `data/notification_rules.json`
- `data/notification_log.csv`

## Channel 抽象

```python
# api/notify/base.py
class NotificationPayload(BaseModel):
    title: str
    body_text: str            # 純文字（LINE Notify、SMS 用）
    body_html: str | None     # HTML（Email 用；None = body_text 自動轉）
    severity: Literal["info", "warn", "critical"]
    tags: list[str]           # ["digest", "alert", "scheduler"...]
    metadata: dict

class ChannelResult(BaseModel):
    channel: str              # "email" / "line"
    ok: bool
    error: str | None
    sent_at: datetime
    recipient: str            # 收件人辨識（email or "line:default"）

class NotificationChannel(ABC):
    name: str
    @abstractmethod
    def send(self, payload: NotificationPayload, recipients: list[str]) -> list[ChannelResult]: ...
    @abstractmethod
    def health_check(self) -> bool: ...
```

## Email channel
- `smtplib.SMTP_SSL` (port 465) 或 `SMTP` + `starttls` (port 587)
- 發送時若 `body_html` 為 None，自動用 `markdown` lib 轉
- 測試環境：`SMTP_DRY_RUN=1` → 寫到 `data/.smtp_outbox/{ts}.eml`

## LINE channel
- `POST https://notify-api.line.me/api/notify`
- header `Authorization: Bearer {LINE_NOTIFY_TOKEN}`
- body: `message=...`（純文字最多 1000 字元，超過 truncate 並加 `…`）
- LINE Notify 自 2025 年起終止 → 偵測 `LINE_MESSAGING_TOKEN` 優先於 `LINE_NOTIFY_TOKEN`，改用 LINE Messaging API（`POST https://api.line.me/v2/bot/message/push`）

## NotificationService

```python
class NotificationService:
    def __init__(self, channels: dict[str, NotificationChannel]): ...

    def send(self, payload: NotificationPayload, channel_names: list[str], recipients_by_channel: dict[str, list[str]]) -> list[ChannelResult]:
        """同步送多通道，全部結果寫 notification_log.csv"""

    def test_channel(self, channel_name: str, recipients: list[str]) -> ChannelResult:
        """送測試訊息：title='[CapyStock] Test'"""

    def list_channels(self) -> list[dict]:
        """{name, configured, healthy}"""
```

## Router

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/notify/channels` | 列出所有 channel 與健康狀態 |
| POST | `/api/v1/notify/test` | body `{channel, recipients?}` |
| POST | `/api/v1/notify/send` | 通用發送（admin / 整合測試用） |
| GET | `/api/v1/notify/log?days=7&channel=email&severity=critical` | 推送歷史 |

## `notification_log.csv` 欄位
```
ts, channel, recipient, severity, title, ok, error, tags
```

## 驗收（自動化）
- Email：用 `aiosmtpd` 或 `smtpdfix` 起測試 SMTP server，斷言收到 message-id / from / to / subject / body
- Email DRY_RUN：`data/.smtp_outbox/` 出現 `.eml` 檔
- LINE：用 `responses` mock，斷言 header 與 body
- LINE truncate：1500 字元 input → 實際 ≤ 1000 字元並結尾 `…`
- NotificationService.send：同時兩 channel 一成一敗 → log.csv 兩列、HTTP 207 Multi-Status
- `/notify/test` API 真的呼叫 channel.send

## 給實作者
- `aiosmtpd` 在 Windows 有問題 → fallback 用 `smtpdfix`（pytest plugin）
