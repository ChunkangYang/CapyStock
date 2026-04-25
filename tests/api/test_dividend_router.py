"""基本面 API 測試。"""
from unittest.mock import patch, MagicMock
import pytest


class TestDividendEndpoints:
    """Dividend endpoints 測試。"""

    @staticmethod
    def mock_fundamental_report():
        """返回 mock FundamentalReport。"""
        from api.schemas.common import FundamentalReport, FundamentalMetric
        return FundamentalReport(
            code="7203",
            name="トヨタ",
            overall="STRONG",
            metrics=[
                FundamentalMetric(metric="sales", score="PASS", note="成長中"),
                FundamentalMetric(metric="eps", score="PASS", note="EPS 上升"),
                FundamentalMetric(metric="op_margin", score="PASS", note="10% 以上"),
                FundamentalMetric(metric="equity_ratio", score="PASS", note="60% 以上"),
                FundamentalMetric(metric="op_cf", score="PASS", note="全部為正"),
                FundamentalMetric(metric="cash", score="PASS", note="現金增加"),
                FundamentalMetric(metric="dps", score="PASS", note="無減配"),
                FundamentalMetric(metric="payout", score="PASS", note="30-50%"),
            ],
        )

    def test_get_fundamental_success(self, test_client, mock_requests):
        """成功取得基本面報告。"""
        mock_report = self.mock_fundamental_report()
        with patch("api.services.dividend_service.get_fundamental_report", return_value=mock_report):
            response = test_client.get("/api/v1/dividend/7203")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == "7203"
            assert data["overall"] == "STRONG"
            assert len(data["metrics"]) == 8

    def test_get_fundamental_not_found(self, test_client, mock_requests):
        """無法取得基本面資料。"""
        with patch("api.services.dividend_service.get_fundamental_report", return_value=None):
            response = test_client.get("/api/v1/dividend/9999")
            assert response.status_code == 404

    def test_get_dividend_series(self, test_client, mock_requests):
        """取得配當時序資料。"""
        mock_series = {
            "dps_series": [50.0, 100.0, 150.0],
            "eps_series": [500.0, 600.0, 700.0],
            "payout_series": [10.0, 15.0, 20.0],
        }
        with patch("api.services.dividend_service.get_dividend_history", return_value=mock_series):
            response = test_client.get("/api/v1/dividend/7203/series")
            assert response.status_code == 200
            data = response.json()
            assert len(data["dps_series"]) == 3
            assert len(data["eps_series"]) == 3
