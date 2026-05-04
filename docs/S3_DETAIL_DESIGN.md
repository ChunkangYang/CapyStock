# S3 Detail Design — Favorites API（實作紀錄）

依賴：[SPRINT_03.md](SPRINT_03.md)
完成日：2026-04-25

## 實裝產出
- ✅ `data/favorites.json`：我的最愛清單（分離於 watchlist）
- ✅ `api/schemas/favorites.py`：FavoriteEntry、FavoriteAddRequest、FavoriteUpdateRequest Pydantic models
- ✅ `api/services/favorite_service.py`：最愛服務
  - `load()` — 載入 favorites.json
  - `add(code, tag, name)` — 加入最愛（合併 tag、去重、固定排序）
  - `remove(code, tag=None)` — 移除最愛（可指定 tag）
  - `set_note(code, note)` — 設定備註
  - `list_favorites(tag=None)` — 列表（可選 tag 過濾）
  - 原子寫入（tempfile + replace）確保並發安全
- ✅ `api/routers/favorites.py`：4 個 favorites endpoints
  - `GET /api/v1/favorites?tag=...`
  - `POST /api/v1/favorites`
  - `PATCH /api/v1/favorites/{code}`
  - `DELETE /api/v1/favorites/{code}?tag=...`

## 自動化測試
- `tests/unit/test_favorite_service.py` — 15 個單元測試（add/remove/list/tag 管理、並發安全）
- `tests/api/test_favorites_router.py` — 13 個 API 測試（全 4 個 endpoints）
- 總計 28 個測試全綠，覆蓋率 97%
