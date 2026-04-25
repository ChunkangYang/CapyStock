"""我的最愛服務測試。"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from api.services import favorite_service


class TestFavoriteService:
    """Favorite service 測試。"""

    def test_load_empty(self, tmp_data_dir, monkeypatch):
        """載入空最愛清單。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        result = favorite_service.load()
        assert result == {}

    def test_add_new_favorite(self, tmp_data_dir, monkeypatch):
        """加入新最愛。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        entry = favorite_service.add("7203", "dividend", name="トヨタ")
        assert entry["code"] == "7203"
        assert entry["name"] == "トヨタ"
        assert entry["tags"] == ["dividend"]
        assert "added_at" in entry
        assert entry["note"] == ""

        # 確認已儲存
        saved = favorite_service.load()
        assert "7203" in saved
        assert saved["7203"]["tags"] == ["dividend"]

    def test_add_multiple_tags_same_stock(self, tmp_data_dir, monkeypatch):
        """同一檔加多個 tag。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        favorite_service.add("9984", "speculative")
        entry = favorite_service.add("9984", "dividend")

        assert sorted(entry["tags"]) == ["dividend", "speculative"]

    def test_add_duplicate_tag_no_duplicate(self, tmp_data_dir, monkeypatch):
        """重複加同一 tag 不產生重複。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        favorite_service.add("7203", "dividend")
        entry = favorite_service.add("7203", "dividend")

        assert entry["tags"] == ["dividend"]
        assert len(entry["tags"]) == 1

    def test_set_note(self, tmp_data_dir, monkeypatch):
        """設定備註。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        favorite_service.add("7203", "dividend")
        entry = favorite_service.set_note("7203", "高配當+健全")

        assert entry["note"] == "高配當+健全"
        assert entry["tags"] == ["dividend"]  # note 不影響 tag

    def test_set_note_nonexistent(self, tmp_data_dir, monkeypatch):
        """設定不存在的股票備註。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        result = favorite_service.set_note("9999", "test")
        assert result is None

    def test_remove_entire_entry(self, tmp_data_dir, monkeypatch):
        """移除整個最愛項目。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        favorite_service.add("7203", "dividend")
        result = favorite_service.remove("7203")

        assert result is True
        saved = favorite_service.load()
        assert "7203" not in saved

    def test_remove_specific_tag(self, tmp_data_dir, monkeypatch):
        """只移除特定 tag。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        favorite_service.add("9984", "speculative")
        favorite_service.add("9984", "dividend")

        result = favorite_service.remove("9984", tag="speculative")
        assert result is True

        saved = favorite_service.load()
        assert "9984" in saved
        assert saved["9984"]["tags"] == ["dividend"]

    def test_remove_last_tag_deletes_entry(self, tmp_data_dir, monkeypatch):
        """移除最後一個 tag 則整筆刪除。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        favorite_service.add("7203", "dividend")
        result = favorite_service.remove("7203", tag="dividend")

        assert result is True
        saved = favorite_service.load()
        assert "7203" not in saved

    def test_remove_nonexistent_tag(self, tmp_data_dir, monkeypatch):
        """移除不存在的 tag。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        favorite_service.add("7203", "dividend")
        result = favorite_service.remove("7203", tag="speculative")

        assert result is False

    def test_remove_nonexistent_stock(self, tmp_data_dir, monkeypatch):
        """移除不存在的股票。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        result = favorite_service.remove("9999")
        assert result is False

    def test_list_all_favorites(self, tmp_data_dir, monkeypatch):
        """列出所有最愛。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        favorite_service.add("7203", "dividend", name="トヨタ")
        favorite_service.add("9984", "speculative", name="ソフトバンク")

        entries = favorite_service.list_favorites()
        assert len(entries) == 2
        # 應按 added_at 逆序
        assert entries[0]["code"] == "9984"
        assert entries[1]["code"] == "7203"

    def test_list_by_tag(self, tmp_data_dir, monkeypatch):
        """按 tag 過濾最愛。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        favorite_service.add("7203", "dividend")
        favorite_service.add("9984", "speculative")
        favorite_service.add("8306", "dividend")

        dividend_entries = favorite_service.list_favorites(tag="dividend")
        assert len(dividend_entries) == 2
        codes = {e["code"] for e in dividend_entries}
        assert codes == {"7203", "8306"}

        spec_entries = favorite_service.list_favorites(tag="speculative")
        assert len(spec_entries) == 1
        assert spec_entries[0]["code"] == "9984"

    def test_tags_always_sorted(self, tmp_data_dir, monkeypatch):
        """tag 順序固定（字母排序）。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        # 故意先加 dividend 再加 speculative
        favorite_service.add("9984", "dividend")
        favorite_service.add("9984", "speculative")

        entry = favorite_service.load()["9984"]
        assert entry["tags"] == ["dividend", "speculative"]

    def test_atomic_write_safety(self, tmp_data_dir, monkeypatch):
        """原子寫入安全性測試（模擬寫入中斷）。"""
        monkeypatch.setattr("capystock.config.DATA_DIR", tmp_data_dir)

        # 先寫入舊資料
        favorite_service.add("7203", "dividend")
        old_content = favorite_service.load()

        # 模擬寫入失敗（tempfile 建立失敗）
        with patch("tempfile.NamedTemporaryFile", side_effect=OSError("寫入失敗")):
            try:
                favorite_service.add("9984", "speculative")
            except OSError:
                pass

        # 確認舊資料未被污染
        current = favorite_service.load()
        assert current == old_content
        assert "9984" not in current
