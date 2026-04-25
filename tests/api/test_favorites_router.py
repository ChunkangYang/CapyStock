"""我的最愛 API 測試。"""
import pytest
from unittest.mock import patch


class TestFavoritesEndpoints:
    """Favorites endpoints 測試。"""

    def test_list_favorites_empty(self, test_client, mock_requests):
        """列出空最愛清單。"""
        with patch("api.services.favorite_service.load", return_value={}):
            response = test_client.get("/api/v1/favorites")
            assert response.status_code == 200
            assert response.json() == []

    def test_list_favorites_with_entries(self, test_client, mock_requests):
        """列出有項目的最愛。"""
        fav_data = {
            "7203": {
                "code": "7203",
                "name": "トヨタ",
                "tags": ["dividend"],
                "added_at": "2026-04-25T10:00:00",
                "note": "高配當",
            }
        }

        with patch("api.services.favorite_service.load", return_value=fav_data), \
             patch("api.services.favorite_service.list_favorites", return_value=list(fav_data.values())):
            response = test_client.get("/api/v1/favorites")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["code"] == "7203"
            assert data[0]["tags"] == ["dividend"]

    def test_list_favorites_by_tag(self, test_client, mock_requests):
        """按 tag 過濾最愛。"""
        fav_data = {
            "7203": {
                "code": "7203",
                "name": "トヨタ",
                "tags": ["dividend"],
                "added_at": "2026-04-25T10:00:00",
                "note": "",
            },
            "9984": {
                "code": "9984",
                "name": "ソフトバンク",
                "tags": ["speculative"],
                "added_at": "2026-04-25T10:01:00",
                "note": "",
            },
        }

        dividend_only = [fav_data["7203"]]

        with patch("api.services.favorite_service.list_favorites", return_value=dividend_only):
            response = test_client.get("/api/v1/favorites?tag=dividend")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["code"] == "7203"

    def test_add_favorite_success(self, test_client, mock_requests):
        """成功加入最愛。"""
        with patch("capystock.scraper.fetch_name", return_value="トヨタ"), \
             patch("api.services.favorite_service.add") as mock_add:
            mock_add.return_value = {
                "code": "7203",
                "name": "トヨタ",
                "tags": ["dividend"],
                "added_at": "2026-04-25T10:00:00",
                "note": "",
            }

            response = test_client.post(
                "/api/v1/favorites",
                json={"code": "7203", "tag": "dividend", "note": "高配當"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == "7203"
            assert data["tags"] == ["dividend"]

    def test_add_favorite_with_note(self, test_client, mock_requests):
        """加入最愛並設定備註。"""
        with patch("capystock.scraper.fetch_name", return_value="トヨタ"), \
             patch("api.services.favorite_service.add") as mock_add, \
             patch("api.services.favorite_service.set_note") as mock_set_note:

            entry = {
                "code": "7203",
                "name": "トヨタ",
                "tags": ["dividend"],
                "added_at": "2026-04-25T10:00:00",
                "note": "高配當+健全",
            }
            mock_add.return_value = entry
            mock_set_note.return_value = entry

            response = test_client.post(
                "/api/v1/favorites",
                json={"code": "7203", "tag": "dividend", "note": "高配當+健全"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["note"] == "高配當+健全"

    def test_add_multiple_tags(self, test_client, mock_requests):
        """同一檔加多個 tag。"""
        with patch("capystock.scraper.fetch_name", return_value="ソフトバンク"), \
             patch("api.services.favorite_service.add") as mock_add:

            mock_add.return_value = {
                "code": "9984",
                "name": "ソフトバンク",
                "tags": ["dividend", "speculative"],
                "added_at": "2026-04-25T10:00:00",
                "note": "",
            }

            response = test_client.post(
                "/api/v1/favorites",
                json={"code": "9984", "tag": "speculative"},
            )
            assert response.status_code == 200
            data = response.json()
            assert sorted(data["tags"]) == ["dividend", "speculative"]

    def test_update_favorite_note(self, test_client, mock_requests):
        """更新最愛備註。"""
        fav_data = {
            "7203": {
                "code": "7203",
                "name": "トヨタ",
                "tags": ["dividend"],
                "added_at": "2026-04-25T10:00:00",
                "note": "",
            }
        }

        with patch("api.services.favorite_service.load", return_value=fav_data), \
             patch("api.services.favorite_service._save") as mock_save:

            response = test_client.patch(
                "/api/v1/favorites/7203",
                json={"note": "高配當+健全"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["note"] == "高配當+健全"
            assert data["tags"] == ["dividend"]  # tag 未改

    def test_update_favorite_tags(self, test_client, mock_requests):
        """更新最愛 tags。"""
        fav_data = {
            "9984": {
                "code": "9984",
                "name": "ソフトバンク",
                "tags": ["speculative"],
                "added_at": "2026-04-25T10:00:00",
                "note": "",
            }
        }

        with patch("api.services.favorite_service.load", return_value=fav_data), \
             patch("api.services.favorite_service._save") as mock_save:

            response = test_client.patch(
                "/api/v1/favorites/9984",
                json={"tags": ["dividend", "speculative"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert sorted(data["tags"]) == ["dividend", "speculative"]

    def test_update_favorite_nonexistent(self, test_client, mock_requests):
        """更新不存在的最愛。"""
        with patch("api.services.favorite_service.load", return_value={}):
            response = test_client.patch(
                "/api/v1/favorites/9999",
                json={"note": "test"},
            )
            assert response.status_code == 404

    def test_delete_favorite_entire_entry(self, test_client, mock_requests):
        """刪除整個最愛項目。"""
        with patch("api.services.favorite_service.remove", return_value=True) as mock_remove:
            response = test_client.delete("/api/v1/favorites/7203")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "removed"
            assert data["code"] == "7203"
            assert data["tag"] is None
            mock_remove.assert_called_once_with("7203", tag=None)

    def test_delete_favorite_specific_tag(self, test_client, mock_requests):
        """只刪除特定 tag。"""
        with patch("api.services.favorite_service.remove", return_value=True) as mock_remove:
            response = test_client.delete("/api/v1/favorites/9984?tag=speculative")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "removed"
            assert data["code"] == "9984"
            assert data["tag"] == "speculative"
            mock_remove.assert_called_once_with("9984", tag="speculative")

    def test_delete_favorite_nonexistent(self, test_client, mock_requests):
        """刪除不存在的最愛。"""
        with patch("api.services.favorite_service.remove", return_value=False):
            response = test_client.delete("/api/v1/favorites/9999")
            assert response.status_code == 404

    def test_delete_favorite_nonexistent_tag(self, test_client, mock_requests):
        """刪除不存在的 tag。"""
        with patch("api.services.favorite_service.remove", return_value=False):
            response = test_client.delete("/api/v1/favorites/7203?tag=nonexistent")
            assert response.status_code == 404
