"""訊號服務單元測試。"""
import pandas as pd
import pytest
from datetime import datetime, date
from unittest.mock import patch, MagicMock

from api.services import signal_service
from api.schemas.common import SignalResult


class TestGetPriceHistory:
    """test get_price_history()."""

    def test_fetch_price_success(self, mock_requests):
        """成功取得股價。"""
        mock_df = pd.DataFrame({
            "date": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000.0, 1100.0],
        })

        with patch("capystock.scraper.fetch_price", return_value=(mock_df, "kabutan")):
            result = signal_service.get_price_history("7203", days=90)
            assert len(result) == 2
            assert result[0].close == 101.0
            assert result[1].close == 102.0

    def test_empty_dataframe(self, mock_requests):
        """空 DataFrame 回傳空列表。"""
        with patch("capystock.scraper.fetch_price", return_value=(None, "none")):
            result = signal_service.get_price_history("9999", days=90)
            assert result == []


class TestGetFlowHistory:
    """test get_flow_history()."""

    def test_flow_with_data(self, mock_requests):
        """成功取得投資部門別資料。"""
        mock_df = pd.DataFrame({
            "date": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            "foreign_net": [100.0, 50.0],
            "institution_net": [200.0, 150.0],
            "individual_net": [-300.0, -200.0],
        })

        with patch("capystock.scraper.fetch_flow", return_value=mock_df):
            result = signal_service.get_flow_history("7203", days=30)
            assert len(result) == 2
            assert result[0].foreign_net == 100.0
            assert result[0].institution_net == 200.0

    def test_flow_missing(self, mock_requests):
        """無資料回傳空列表。"""
        with patch("capystock.scraper.fetch_flow", return_value=None):
            result = signal_service.get_flow_history("9999", days=30)
            assert result == []


class TestAnalyzeOne:
    """test analyze_one()。"""

    def test_analyze_with_watchlist_price(self, mock_requests):
        """分析時帶入 start_price。"""
        mock_price = pd.DataFrame({
            "date": [datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)],
            "open": [100.0, 101.0, 102.0],
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0],
            "close": [101.0, 102.0, 103.0],
            "volume": [1000.0, 1100.0, 1200.0],
        })

        with patch("capystock.scraper.fetch_name", return_value="トヨタ"), \
             patch("capystock.scraper.fetch_price", return_value=(mock_price, "kabutan")), \
             patch("capystock.scraper.fetch_margin", return_value=None), \
             patch("capystock.scraper.fetch_flow", return_value=None):
            result = signal_service.analyze_one("7203", start_price=2500.0)
            assert isinstance(result, SignalResult)
            assert result.code == "7203"
            assert result.name == "トヨタ"
            assert result.start_price == 2500.0

    def test_analyze_no_price_data(self, mock_requests):
        """無股價資料仍回傳結果（但條件不符）。"""
        with patch("capystock.scraper.fetch_name", return_value="Unknown"), \
             patch("capystock.scraper.fetch_price", return_value=(None, "none")), \
             patch("capystock.scraper.fetch_margin", return_value=None), \
             patch("capystock.scraper.fetch_flow", return_value=None):
            result = signal_service.analyze_one("9999", start_price=1000.0)
            assert isinstance(result, SignalResult)
            assert result.code == "9999"
            assert result.latest_price is None


class TestAnalyzeWatchlist:
    """test analyze_watchlist()。"""

    def test_empty_watchlist(self, mock_requests):
        """空追蹤清單回傳空結果。"""
        with patch("capystock.storage.load_watchlist", return_value={}):
            result = signal_service.analyze_watchlist()
            assert result == []

    def test_watchlist_with_entries(self, mock_requests):
        """多筆追蹤清單分析。"""
        mock_price = pd.DataFrame({
            "date": [datetime(2024, 1, 1)],
            "open": [100.0],
            "high": [102.0],
            "low": [99.0],
            "close": [101.0],
            "volume": [1000.0],
        })

        wl = {
            "7203": {"code": "7203", "start_price": 2500.0, "name": "トヨタ"},
            "9984": {"code": "9984", "start_price": 1000.0, "name": "SBG"},
        }

        with patch("capystock.storage.load_watchlist", return_value=wl), \
             patch("capystock.scraper.fetch_name", return_value="Stock"), \
             patch("capystock.scraper.fetch_price", return_value=(mock_price, "kabutan")), \
             patch("capystock.scraper.fetch_margin", return_value=None), \
             patch("capystock.scraper.fetch_flow", return_value=None):
            result = signal_service.analyze_watchlist()
            assert len(result) == 2
