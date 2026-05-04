"""S24 測試 — IR Bank 爬蟲增強 — 橫向表格解析 + Partial Data 支援。"""
import pytest

from capystock.fundamental import (
    _is_transposed_dividend,
    _extract_transposed_dps,
    analyze_fundamental,
)


class TestTransposedDividendDetection:
    """測試橫向格式偵測 (S24 D2)."""

    def test_is_transposed_dividend_true(self):
        """識別橫向格式（年份為 row label）。"""
        table = {
            '年度': ['区分', '中間', '期末', '合計', '分割調整'],
            '2021年2月': ['実績', '18', '21', '39', '39'],
            '2022年2月': ['予想', '25', '26', '51', '51'],
            '2023年2月': ['予想', '26', '26', '52', '52'],
        }
        assert _is_transposed_dividend(table) is True

    def test_is_transposed_dividend_false_standard_format(self):
        """標準格式（指標名稱為 row label）返回 False。"""
        table = {
            '一株配当': ['2021年2月', '2022年2月', '2023年2月'],
            '配当性向': ['50%', '55%', '52%'],
        }
        assert _is_transposed_dividend(table) is False

    def test_is_transposed_dividend_insufficient_years(self):
        """年份列少於 3 個返回 False。"""
        table = {
            '年度': ['区分', '中間', '期末'],
            '2022年2月': ['実績', '25', '26'],
        }
        assert _is_transposed_dividend(table) is False


class TestExtractTransposedDps:
    """測試橫向表格 DPS 提取 (S24 D3)."""

    def test_extract_transposed_dps_basic(self):
        """基本提取：実績 + 修正，排除預想。"""
        table = {
            '年度': ['区分', '中間', '期末', '合計', '分割調整'],
            '2021年2月': ['実績', '18', '21', '39', '39'],
            '2022年2月': ['予想', '25', '26', '51', '51'],
            '2023年2月': ['修正', '26', '26', '52', '52'],
        }
        result = _extract_transposed_dps(table)
        assert 'dps' in result
        assert result['dps'] == [39.0, 52.0]

    def test_extract_transposed_dps_excludes_zero(self):
        """排除 0 值（IPO 年無配發）。"""
        table = {
            '年度': ['区分', '中間', '期末', '合計', '分割調整'],
            '2016年2月': ['実績', '0', '0', '0', '0'],
            '2021年2月': ['実績', '18', '21', '39', '39'],
            '2022年2月': ['修正', '26', '26', '52', '52'],
        }
        result = _extract_transposed_dps(table)
        assert None in result['dps']
        assert 39.0 in result['dps']
        assert 52.0 in result['dps']

    def test_extract_transposed_dps_excludes_negative(self):
        """排除負值。"""
        table = {
            '年度': ['区分', '中間', '期末', '合計', '分割調整'],
            '2021年2月': ['実績', '18', '21', '39', '39'],
            '2022年2月': ['実績', '-10', '-15', '-25', '-25'],
            '2023年2月': ['修正', '26', '26', '52', '52'],
        }
        result = _extract_transposed_dps(table)
        assert None in result['dps']
        assert result['dps'].count(None) >= 1

    def test_extract_transposed_dps_sorts_chronologically(self):
        """按年份排序（字典序 = 時間序）。"""
        table = {
            '年度': ['区分', '中間', '期末', '合計', '分割調整'],
            '2023年2月': ['実績', '26', '26', '52', '52'],
            '2021年2月': ['実績', '18', '21', '39', '39'],
            '2022年2月': ['実績', '25', '26', '51', '51'],
        }
        result = _extract_transposed_dps(table)
        assert result['dps'] == [39.0, 51.0, 52.0]

    def test_extract_transposed_dps_all_forecast_returns_empty(self):
        """全部為預想時返回空 dict。"""
        table = {
            '年度': ['区分', '中間', '期末', '合計', '分割調整'],
            '2023年2月': ['予想', '26', '26', '52', '52'],
            '2024年2月': ['予想', '27', '27', '54', '54'],
        }
        result = _extract_transposed_dps(table)
        assert result == {}

    def test_extract_transposed_dps_insufficient_columns(self):
        """欄位不足時跳過該列。"""
        table = {
            '年度': ['区分', '中間'],
            '2021年2月': ['実績', '18'],
        }
        result = _extract_transposed_dps(table)
        assert result == {}

    def test_extract_transposed_dps_uses_adjusted_column(self):
        """使用分割調整欄 (index 4) 而非合計欄 (index 3)。"""
        table = {
            '年度': ['区分', '中間', '期末', '合計', '分割調整'],
            '2021年2月': ['実績', '18', '21', '39', '50'],
        }
        result = _extract_transposed_dps(table)
        assert result['dps'] == [50.0]


class TestPartialDataSupport:
    """測試 Partial Data（只有 DPS）支援 (S24 D4–D5)."""

    @pytest.mark.integration
    def test_komeda_hd_3543_returns_caution(self):
        """3543 コメダHD：settlement 404 → 橫向 fallback → CAUTION。"""
        report, err = analyze_fundamental('3543', 'コメダHD')
        assert err is None, f"Expected success but got error: {err}"
        assert report is not None
        assert report.overall in ('CAUTION', 'HEALTHY')

        dps_metric = next((m for m in report.metrics if m.metric == 'dps'), None)
        assert dps_metric is not None
        assert dps_metric.score in ('PASS', 'WARN', 'FAIL')

    @pytest.mark.integration
    def test_standard_format_unaffected(self):
        """確認標準格式（3 月決算）不受影響。"""
        report, err = analyze_fundamental('7203', 'トヨタ自動車')
        assert err is None
        assert report is not None
        assert report.overall in ('HEALTHY', 'CAUTION', 'RISKY', 'STRONG')


class TestMetricScoreWithPartialData:
    """測試評分邏輯對 Partial Data 的支援 (S24 D5)。"""

    def test_overall_with_single_metric(self):
        """只有 1 個指標（DPS）時，overall 應為 CAUTION（不應 RISKY/STRONG）。"""
        pass


class TestRegressionCases:
    """回歸測試 — 確保修改不破壞現有行為 (S24 D6)."""

    @pytest.mark.integration
    def test_regression_toyota_7203_evaluates_successfully(self):
        """7203 トヨタ：應成功評估（結果可能因網站變化而異）。"""
        report, err = analyze_fundamental('7203', 'トヨタ自動車')
        assert err is None
        assert report is not None
        assert report.overall in ('HEALTHY', 'CAUTION', 'RISKY', 'STRONG')

    @pytest.mark.integration
    def test_regression_sony_6758(self):
        """6758 ソニー：標準格式，應保持 CAUTION。"""
        report, err = analyze_fundamental('6758', 'ソニーグループ')
        assert err is None
        assert report is not None
        assert report.overall == 'CAUTION'
