# Sprint 3 — Favorites API + watchlist 整合

依賴：[MILESTONE_03.md](MILESTONE_03.md)

## 目的
- 「我的最愛」與 `watchlist.json`（持倉追蹤）**分離**：watchlist 是真有部位的、需要 start_price；favorites 只是觀察名單
- favorites 同時涵蓋「投機 / 金雞」兩類，用 tag 區分

## 資料結構（`data/favorites.json`）

```json
{
  "7203": {
    "code": "7203",
    "name": "トヨタ自動車",
    "tags": ["dividend"],
    "added_at": "2026-04-25T10:00:00",
    "note": "高配當+健全"
  },
  "9984": {
    "code": "9984",
    "name": "ソフトバンクG",
    "tags": ["speculative", "dividend"],
    "added_at": "2026-04-25T10:01:00",
    "note": ""
  }
}
```

## 檔案
- `api/services/favorite_service.py`：`load`, `add(code, tag)`, `remove(code, tag=None)`, `set_note(code, note)`, `list(tag=None)`
- `api/routers/favorites.py`
- `api/schemas/favorites.py`

## Endpoints

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/v1/favorites?tag=dividend` | 列出（可選 tag 過濾） |
| POST | `/api/v1/favorites` | body `{code, tag: "speculative"|"dividend", note?}`；已存在則合併 tag |
| PATCH | `/api/v1/favorites/{code}` | body `{tags?, note?}` |
| DELETE | `/api/v1/favorites/{code}?tag=speculative` | 移除單一 tag；無 tag 參數則整筆刪 |

## 驗收（自動化）
- `pytest tests/unit/test_favorite_service.py tests/api/test_favorites_router.py -v` 全綠
- 必測情境：
  - 同一檔同時加兩個 tag → JSON 內 tags 為 `["speculative", "dividend"]`（順序固定）
  - DELETE 帶 tag 只移除該 tag、剩 0 tag 時整筆刪除
  - 重複 add 不會產生重複 tag
  - PATCH note 不影響 tags
  - 並發安全：用 file lock 或 atomic write（測試以 monkeypatch 模擬中斷寫入仍能保留舊資料）
