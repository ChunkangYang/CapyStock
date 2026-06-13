"""即時報價服務（quote_service）單元測試。

mock yfinance.Ticker，驗證：
  (a) 正常回價
  (b) TTL 內第二次呼叫不再建 Ticker（mock 只被叫一次）
  (c) 失敗回 None
"""
import sys
import types

import pytest

from api.services import quote_service


class _FastInfo(dict):
    """fast_info 既支援 .get 也支援屬性存取。"""
    @property
    def last_price(self):
        return self.get("last_price")


def _install_fake_yfinance(monkeypatch, last_price, counter):
    """裝一個假的 yfinance module，Ticker 被建立時 counter['n'] += 1。"""
    fake = types.ModuleType("yfinance")

    class FakeTicker:
        def __init__(self, symbol):
            counter["n"] += 1
            self.symbol = symbol

        @property
        def fast_info(self):
            return _FastInfo({"last_price": last_price})

    fake.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake)


@pytest.fixture(autouse=True)
def _clear_cache():
    quote_service._quote_cache.clear()
    yield
    quote_service._quote_cache.clear()


def test_quote_returns_price(monkeypatch):
    counter = {"n": 0}
    _install_fake_yfinance(monkeypatch, 3210.0, counter)
    q = quote_service.get_quote("7203")
    assert q is not None
    assert q["price"] == 3210.0
    assert q["code"] == "7203"
    assert q["source"] == "yfinance"
    assert counter["n"] == 1


def test_quote_ttl_cache_no_second_ticker(monkeypatch):
    counter = {"n": 0}
    _install_fake_yfinance(monkeypatch, 3210.0, counter)
    quote_service.get_quote("7203")
    second = quote_service.get_quote("7203")  # TTL 內 → 走 cache
    assert second["price"] == 3210.0
    assert counter["n"] == 1  # Ticker 沒有被第二次建立


def test_quote_returns_none_on_failure(monkeypatch):
    counter = {"n": 0}
    _install_fake_yfinance(monkeypatch, None, counter)  # last_price=None
    assert quote_service.get_quote("9999") is None


def test_quote_returns_none_when_yfinance_raises(monkeypatch):
    fake = types.ModuleType("yfinance")

    class BoomTicker:
        def __init__(self, symbol):
            raise RuntimeError("network down")

    fake.Ticker = BoomTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    assert quote_service.get_quote("7203") is None
