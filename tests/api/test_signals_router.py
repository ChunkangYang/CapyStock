"""訊號 API 測試。"""
from unittest.mock import patch, MagicMock
from datetime import date
import pytest

from api.schemas.common import SignalResult, SignalConditions, Alert


class TestSignalsEndpoints:
    """Signals endpoints 測試。"""

    @staticmethod
    def mock_signal_result():
        """返回 mock SignalResult。"""
        return SignalResult(
            code="7203",
            name="トヨタ",
            latest_price=2500.0,
            latest_date=date(2024, 1, 2),
            start_price=2400.0,
            price_vs_start_pct=0.0417,
            price_vs_recent_low_pct=0.05,
            conditions=SignalConditions(
                cond_inst_sell=False,
                cond_margin_surge=False,
                cond_price_rise=True,
                matched=1,
            ),
            stop_loss_triggered=False,
            accumulation_signal=False,
            flow_recent=[100.0, 50.0],
            margin_trend_note="",
            notes=["缺投資部門別資料"],
            alerts=[],
        )

    def test_list_signals(self, test_client, mock_requests):
        """列出全部訊號。"""
        mock_result = self.mock_signal_result()
        with patch("api.services.signal_service.analyze_watchlist", return_value=[mock_result]):
            response = test_client.get("/api/v1/signals")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["code"] == "7203"

    def test_get_signal_single(self, test_client, mock_requests):
        """取得單檔訊號。"""
        mock_result = self.mock_signal_result()
        with patch("api.services.signal_service.analyze_one", return_value=mock_result):
            response = test_client.get("/api/v1/signals/7203")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == "7203"
            assert data["latest_price"] == 2500.0

    def test_get_signal_error(self, test_client, mock_requests):
        """訊號分析失敗。"""
        with patch("api.services.signal_service.analyze_one", side_effect=Exception("Error")):
            response = test_client.get("/api/v1/signals/9999")
            assert response.status_code == 500

    def test_get_price_history(self, test_client, mock_requests):
        """取得股價歷史。"""
        from api.schemas.common import PriceBar
        mock_prices = [
            PriceBar(date=date(2024, 1, 1), open=100.0, high=102.0, low=99.0, close=101.0, volume=1000.0),
            PriceBar(date=date(2024, 1, 2), open=101.0, high=103.0, low=100.0, close=102.0, volume=1100.0),
        ]
        with patch("api.services.signal_service.get_price_history", return_value=mock_prices):
            response = test_client.get("/api/v1/signals/7203/price?days=90")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["close"] == 101.0

    def test_get_flow_history(self, test_client, mock_requests):
        """取得投資部門別資料。"""
        from api.schemas.common import FlowRow
        mock_flows = [
            FlowRow(date=date(2024, 1, 1), foreign_net=100.0, institution_net=200.0, individual_net=-300.0),
        ]
        with patch("api.services.signal_service.get_flow_history", return_value=mock_flows):
            response = test_client.get("/api/v1/signals/7203/flow?days=30")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1

    def test_get_margin_history(self, test_client, mock_requests):
        """取得信用殘歷史。"""
        from api.schemas.common import MarginRow
        mock_margins = [
            MarginRow(week=date(2024, 1, 1), margin_long=1000.0, margin_short=500.0, ratio=0.5),
        ]
        with patch("api.services.signal_service.get_margin_history", return_value=mock_margins):
            response = test_client.get("/api/v1/signals/7203/margin?weeks=12")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1

    def test_get_edinet_events(self, test_client, mock_requests):
        """取得 EDINET 事件。"""
        mock_events = [
            {
                "sec_code": "7203",
                "submit_date": "2024-01-01",
                "doc_type_code": "350",
                "filer_name": "SomeInvestor",
                "pdf_url": "https://example.com/pdf",
            }
        ]
        with patch("api.services.signal_service.get_edinet_events", return_value=mock_events):
            response = test_client.get("/api/v1/signals/7203/edinet?days=30")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
