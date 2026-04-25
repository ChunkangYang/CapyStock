"""測試共用 fixture。"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def tmp_data_dir():
    """臨時資料目錄（避免污染真實 data/）。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_client():
    """FastAPI TestClient。"""
    return TestClient(app)


@pytest.fixture
def mock_requests(monkeypatch):
    """Mock requests 防止外部 HTTP 呼叫。"""
    def mock_get(*args, **kwargs):
        raise RuntimeError("外部 HTTP 請求被禁止（使用 mock fixture）")

    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr("capystock.scraper.requests.get", mock_get)
    monkeypatch.setattr("capystock.fundamental.requests.get", mock_get)
    monkeypatch.setattr("capystock.edinet.requests.get", mock_get)
