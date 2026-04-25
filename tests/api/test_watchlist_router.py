"""追蹤清單 API 測試。"""
from unittest.mock import patch, MagicMock
import pytest


class TestWatchlistEndpoints:
    """Watchlist endpoints 測試。"""

    def test_list_watchlist_empty(self, test_client, mock_requests):
        """列出空追蹤清單。"""
        with patch("capystock.storage.load_watchlist", return_value={}):
            response = test_client.get("/api/v1/watchlist")
            assert response.status_code == 200
            assert response.json() == []

    def test_list_watchlist_with_entries(self, test_client, mock_requests):
        """列出有項目的追蹤清單。"""
        wl = {
            "7203": {
                "code": "7203",
                "name": "トヨタ",
                "start_price": 2500.0,
                "added_date": "2024-01-01",
            }
        }

        with patch("capystock.storage.load_watchlist", return_value=wl):
            response = test_client.get("/api/v1/watchlist")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["code"] == "7203"

    def test_add_watchlist_success(self, test_client, mock_requests):
        """成功加入追蹤股票。"""
        with patch("capystock.scraper.fetch_name", return_value="トヨタ"), \
             patch("capystock.storage.add_watch") as mock_add:
            response = test_client.post(
                "/api/v1/watchlist",
                json={"code": "7203", "start_price": 2500.0},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == "7203"
            assert data["name"] == "トヨタ"
            assert data["start_price"] == 2500.0
            mock_add.assert_called_once()

    def test_remove_watchlist_success(self, test_client, mock_requests):
        """成功移除追蹤股票。"""
        with patch("capystock.storage.remove_watch", return_value=True):
            response = test_client.delete("/api/v1/watchlist/7203")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "removed"
            assert data["code"] == "7203"

    def test_remove_watchlist_not_found(self, test_client, mock_requests):
        """移除不存在的股票。"""
        with patch("capystock.storage.remove_watch", return_value=False):
            response = test_client.delete("/api/v1/watchlist/9999")
            assert response.status_code == 404
