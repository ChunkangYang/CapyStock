"""股息服務單元測試。"""
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from api.services import dividend_service
from api.schemas.common import FundamentalReport as FundamentalReportSchema


class TestGetFundamentalReport:
    """test get_fundamental_report()。"""

    def test_successful_analysis(self, mock_requests):
        """成功取得基本面報告。"""
        # Mock 回傳的 fundamental.FundamentalReport
        mock_report = MagicMock()
        mock_report.code = "7203"
        mock_report.name = "トヨタ"
        mock_report.overall = "STRONG"
        mock_report.metrics = [
            MagicMock(metric="sales", score="PASS", note="成長中"),
            MagicMock(metric="eps", score="PASS", note="EPS 上升"),
            MagicMock(metric="op_margin", score="PASS", note="10% 以上"),
            MagicMock(metric="equity_ratio", score="PASS", note="60% 以上"),
            MagicMock(metric="op_cf", score="PASS", note="全部為正"),
            MagicMock(metric="cash", score="PASS", note="現金增加"),
            MagicMock(metric="dps", score="PASS", note="無減配"),
            MagicMock(metric="payout", score="PASS", note="30-50%"),
        ]

        with patch("capystock.scraper.fetch_name", return_value="トヨタ"), \
             patch("capystock.fundamental.analyze_fundamental", return_value=(mock_report, None)):
            result = dividend_service.get_fundamental_report("7203")
            assert result is not None
            assert isinstance(result, FundamentalReportSchema)
            assert result.code == "7203"
            assert result.overall == "STRONG"
            assert len(result.metrics) == 8

    def test_analysis_failure(self, mock_requests):
        """分析失敗回傳 None。"""
        with patch("capystock.scraper.fetch_name", return_value="Unknown"), \
             patch("capystock.fundamental.analyze_fundamental", return_value=(None, "Error")):
            result = dividend_service.get_fundamental_report("9999")
            assert result is None


class TestGetDividendHistory:
    """test get_dividend_history()。"""

    def test_with_cache_data(self, tmp_data_dir, mock_requests):
        """有快取資料時返回。"""
        # 創建 mock 快取檔案
        cache_df = pd.DataFrame({
            "year_idx": [-2, -1, 0],
            "dps": [50.0, 100.0, 150.0],
            "eps": [500.0, 600.0, 700.0],
            "payout": [0.10, 0.15, 0.20],
        })

        with patch("capystock.fundamental._cache_path") as mock_path:
            # Mock 檔案讀取
            mock_path.return_value = tmp_data_dir / "test.csv"
            cache_df.to_csv(str(mock_path.return_value), index=False)

            result = dividend_service.get_dividend_history("7203")
            assert "dps_series" in result
            assert len(result["dps_series"]) == 3

    def test_no_cache_data(self, mock_requests):
        """無快取檔案回傳空字典。"""
        with patch("capystock.fundamental._cache_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/path.csv")
            result = dividend_service.get_dividend_history("9999")
            assert result["dps_series"] == []
            assert result["eps_series"] == []
            assert result["payout_series"] == []
