"""模擬交易 API 測試。"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from api.schemas.simulation import (
    CandidateEntry,
    Simulation,
    SimulationConfig,
    EntryRule,
    ExitRule,
    PositionSizing,
    CostModel,
)


@pytest.fixture
def base_config():
    """基本模擬配置。"""
    base_date = date(2026, 1, 1)
    return SimulationConfig(
        kind="backtest",
        initial_capital=100000.0,
        start_date=base_date,
        end_date=base_date + timedelta(days=9),
        candidates=[CandidateEntry(code="7203", name="Toyota")],
        entry_rule=EntryRule(),
        exit_rule=ExitRule(),
        position_sizing=PositionSizing(),
        cost_model=CostModel(),
    )


class TestSimulationRouter:
    """模擬交易路由測試。"""

    def test_create_simulation(self, test_client, base_config):
        """POST /simulation — 建立模擬。"""
        response = test_client.post(
            "/api/v1/simulation",
            params={"name": "Test Sim"},
            json=base_config.model_dump(mode='json'),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] is not None
        assert data["name"] == "Test Sim"
        assert data["status"] == "draft"

    def test_list_simulations(self, test_client, base_config):
        """GET /simulation — 列出模擬。"""
        # 先建立一些
        test_client.post(
            "/api/v1/simulation",
            params={"name": "Sim 1"},
            json=base_config.model_dump(mode='json'),
        )
        test_client.post(
            "/api/v1/simulation",
            params={"name": "Sim 2"},
            json=base_config.model_dump(mode='json'),
        )

        response = test_client.get("/api/v1/simulation")
        assert response.status_code == 200
        sims = response.json()
        assert isinstance(sims, list)
        assert len(sims) >= 2

    def test_get_simulation(self, test_client, base_config):
        """GET /simulation/{id} — 取得模擬詳情。"""
        create_response = test_client.post(
            "/api/v1/simulation",
            params={"name": "Get Test"},
            json=base_config.model_dump(mode='json'),
        )
        sim_id = create_response.json()["id"]

        response = test_client.get(f"/api/v1/simulation/{sim_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sim_id
        assert data["name"] == "Get Test"

    def test_get_nonexistent_simulation(self, test_client):
        """GET /simulation/{id} — 取得不存在的模擬應回 404。"""
        response = test_client.get("/api/v1/simulation/nonexistent-id")
        assert response.status_code == 404

    def test_update_simulation_draft(self, test_client, base_config):
        """PATCH /simulation/{id} — 更新設定（draft 狀態）。"""
        create_response = test_client.post(
            "/api/v1/simulation",
            params={"name": "Update Test"},
            json=base_config.model_dump(mode='json'),
        )
        sim_id = create_response.json()["id"]

        new_config = base_config.model_copy()
        new_config.initial_capital = 200000.0

        response = test_client.patch(
            f"/api/v1/simulation/{sim_id}",
            json=new_config.model_dump(mode='json'),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["config"]["initial_capital"] == 200000.0

    def test_add_candidate(self, test_client, base_config):
        """POST /simulation/{id}/add-candidate — 新增候選。"""
        create_response = test_client.post(
            "/api/v1/simulation",
            params={"name": "Candidate Test"},
            json=base_config.model_dump(mode='json'),
        )
        sim_id = create_response.json()["id"]

        response = test_client.post(
            f"/api/v1/simulation/{sim_id}/add-candidate",
            params={
                "code": "9984",
                "name": "SoftBank",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["config"]["candidates"]) == 2
        assert data["config"]["candidates"][1]["code"] == "9984"

    def test_delete_simulation(self, test_client, base_config):
        """DELETE /simulation/{id} — 刪除模擬。"""
        create_response = test_client.post(
            "/api/v1/simulation",
            params={"name": "Delete Test"},
            json=base_config.model_dump(mode='json'),
        )
        sim_id = create_response.json()["id"]

        response = test_client.delete(f"/api/v1/simulation/{sim_id}")
        assert response.status_code == 200

        # 確認已刪除
        get_response = test_client.get(f"/api/v1/simulation/{sim_id}")
        assert get_response.status_code == 404

    def test_get_report(self, test_client, base_config):
        """GET /simulation/{id}/report — 取得報告。"""
        create_response = test_client.post(
            "/api/v1/simulation",
            params={"name": "Report Test"},
            json=base_config.model_dump(mode='json'),
        )
        sim_id = create_response.json()["id"]

        response = test_client.get(f"/api/v1/simulation/{sim_id}/report")
        assert response.status_code == 200
        report = response.json()
        assert report["id"] == sim_id
        assert "total_return_pct" in report
        assert "max_drawdown_pct" in report

    def test_run_simulation_backtest(self, test_client, base_config, monkeypatch):
        """POST /simulation/{id}/run — 執行 backtest。"""
        # Mock signal_service
        mock_signal = MagicMock()

        def mock_get_price_history(code, days):
            from api.schemas.common import PriceBar

            base_date = date(2026, 1, 1)
            prices = []
            for i in range(10):
                prices.append(
                    PriceBar(
                        date=base_date + timedelta(days=i),
                        open=100.0,
                        high=101.0,
                        low=99.0,
                        close=100.0 + i,
                        volume=1000.0,
                    )
                )
            return prices

        mock_signal.get_price_history = mock_get_price_history

        with patch(
            "api.services.simulation_service.signal_service", mock_signal
        ):
            create_response = test_client.post(
                "/api/v1/simulation",
                params={"name": "Run Backtest"},
                json=base_config.model_dump(mode='json'),
            )
            sim_id = create_response.json()["id"]

            response = test_client.post(f"/api/v1/simulation/{sim_id}/run")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"


class TestFullSimulationFlow:
    """完整模擬流程測試。"""

    def test_complete_backtest_flow(self, test_client, base_config, monkeypatch):
        """完整 backtest 流程：建立 → run → report → 刪除。"""
        # Mock signal service
        mock_signal = MagicMock()

        def mock_get_price_history(code, days):
            from api.schemas.common import PriceBar

            base_date = date(2026, 1, 1)
            prices = []
            for i in range(10):
                prices.append(
                    PriceBar(
                        date=base_date + timedelta(days=i),
                        open=100.0,
                        high=101.0,
                        low=99.0,
                        close=100.0 + i,
                        volume=1000.0,
                    )
                )
            return prices

        mock_signal.get_price_history = mock_get_price_history

        with patch(
            "api.services.simulation_service.signal_service", mock_signal
        ):
            # 1. 建立
            create_response = test_client.post(
                "/api/v1/simulation",
                params={"name": "Complete Flow"},
                json=base_config.model_dump(mode='json'),
            )
            assert create_response.status_code == 200
            sim_id = create_response.json()["id"]

            # 2. 執行
            run_response = test_client.post(f"/api/v1/simulation/{sim_id}/run")
            assert run_response.status_code == 200
            assert run_response.json()["status"] == "completed"

            # 3. 取得報告
            report_response = test_client.get(f"/api/v1/simulation/{sim_id}/report")
            assert report_response.status_code == 200
            report = report_response.json()
            assert report["status"] == "completed"

            # 4. 刪除
            delete_response = test_client.delete(f"/api/v1/simulation/{sim_id}")
            assert delete_response.status_code == 200

            # 5. 確認已刪除
            final_get = test_client.get(f"/api/v1/simulation/{sim_id}")
            assert final_get.status_code == 404


class TestErrorHandling:
    """錯誤處理測試。"""

    def test_invalid_config(self, test_client):
        """送無效配置應回 400。"""
        response = test_client.post(
            "/api/v1/simulation",
            params={"name": "Invalid"},
            json={"invalid": "config"},
        )

        assert response.status_code == 422  # Pydantic validation error

    def test_close_position_nonexistent(self, test_client, base_config):
        """平倉不存在的持倉應回 404。"""
        create_response = test_client.post(
            "/api/v1/simulation",
            params={"name": "Close Test"},
            json=base_config.model_dump(mode='json'),
        )
        sim_id = create_response.json()["id"]

        response = test_client.post(
            f"/api/v1/simulation/{sim_id}/close-position",
            params={
                "code": "9999",
                "exit_price": 100.0,
            },
        )

        assert response.status_code == 404
