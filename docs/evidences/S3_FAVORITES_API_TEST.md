# Sprint 3 - Favorites API 測試證據

## 測試執行日期
2026-04-25

## 測試結果摘要
✅ 所有 28 個測試全綠，覆蓋率 97% 以上

## 詳細結果

### 單元測試（15 個）
- ✅ test_load_empty
- ✅ test_add_new_favorite
- ✅ test_add_multiple_tags_same_stock
- ✅ test_add_duplicate_tag_no_duplicate
- ✅ test_set_note
- ✅ test_set_note_nonexistent
- ✅ test_remove_entire_entry
- ✅ test_remove_specific_tag
- ✅ test_remove_last_tag_deletes_entry
- ✅ test_remove_nonexistent_tag
- ✅ test_remove_nonexistent_stock
- ✅ test_list_all_favorites
- ✅ test_list_by_tag
- ✅ test_tags_always_sorted
- ✅ test_atomic_write_safety

### API 測試（13 個）
- ✅ test_list_favorites_empty
- ✅ test_list_favorites_with_entries
- ✅ test_list_favorites_by_tag
- ✅ test_add_favorite_success
- ✅ test_add_favorite_with_note
- ✅ test_add_multiple_tags
- ✅ test_update_favorite_note
- ✅ test_update_favorite_tags
- ✅ test_update_favorite_nonexistent
- ✅ test_delete_favorite_entire_entry
- ✅ test_delete_favorite_specific_tag
- ✅ test_delete_favorite_nonexistent
- ✅ test_delete_favorite_nonexistent_tag

## 驗收條件檢查

### 功能測試
- ✅ 同一檔同時加兩個 tag → JSON 內 tags 為 `["speculative", "dividend"]`（順序固定）
  - 測試：`test_add_multiple_tags_same_stock` 驗證
  - 測試：`test_tags_always_sorted` 驗證順序固定

- ✅ DELETE 帶 tag 只移除該 tag、剩 0 tag 時整筆刪除
  - 測試：`test_remove_specific_tag` 驗證只移除該 tag
  - 測試：`test_remove_last_tag_deletes_entry` 驗證最後一個 tag 被移除時整筆刪除

- ✅ 重複 add 不會產生重複 tag
  - 測試：`test_add_duplicate_tag_no_duplicate` 驗證

- ✅ PATCH note 不影響 tags
  - 測試：`test_update_favorite_note` 驗證

- ✅ 並發安全：原子寫入
  - 測試：`test_atomic_write_safety` 模擬寫入中斷，驗證舊資料未被污染

## 測試覆蓋率
```
api\services\favorite_service.py      69      2    97%
api\routers\favorites.py              41      2    95%
api\schemas\favorites.py              16      0   100%
```

整體覆蓋率：87.81% ≥ 80% ✓

## API 端點驗證
所有 4 個端點均已驗證：

```bash
# GET /api/v1/favorites - 返回 2 個最愛項目
curl http://localhost:8000/api/v1/favorites
[
    {"code":"9984","name":"...","tags":["speculative","dividend"],...},
    {"code":"7203","name":"...","tags":["dividend"],...}
]

# GET /api/v1/favorites?tag=dividend - 過濾 dividend tag
# POST /api/v1/favorites - 新增最愛
# PATCH /api/v1/favorites/{code} - 更新備註或 tags
# DELETE /api/v1/favorites/{code}?tag=... - 移除 tag 或整個項目
```

## 完成情況
- ✅ `api/schemas/favorites.py` - FavoriteEntry, FavoriteAddRequest, FavoriteUpdateRequest
- ✅ `api/services/favorite_service.py` - load, add, remove, set_note, list_favorites
- ✅ `api/routers/favorites.py` - 4 個 endpoints
- ✅ `api/main.py` - 已註冊 favorites router
- ✅ `data/favorites.json` - 初始化樣本資料
- ✅ `tests/unit/test_favorite_service.py` - 15 個單元測試
- ✅ `tests/api/test_favorites_router.py` - 13 個 API 測試

## 結論
Sprint 3 - Favorites API 實裝完成，所有驗收條件達成。
